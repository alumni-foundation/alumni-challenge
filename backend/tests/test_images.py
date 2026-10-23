import io

import pytest
from PIL import Image
from PIL.PngImagePlugin import PngInfo

from app.core.errors.exceptions import PayloadTooLargeError, UnsupportedMediaError, ValidationError
from app.modules.files.images import process_image
from app.modules.files.models import FilePurpose
from app.modules.files.policies import POLICIES

AVATAR = POLICIES[FilePurpose.AVATAR]
POSTER = POLICIES[FilePurpose.EVENT_POSTER]

# Stand-ins for "something an attacker hid after the picture". Harmless text on purpose.
APPENDED_MARKER = b"APPENDED-PAYLOAD-MARKER-7f3a91"


def _encode(image: Image.Image, fmt: str, **options: object) -> bytes:
    out = io.BytesIO()
    image.save(out, format=fmt, **options)
    return out.getvalue()


def _photo(size: tuple[int, int] = (400, 300)) -> Image.Image:
    image = Image.new("RGB", size, (10, 120, 200))
    image.paste((250, 250, 20), (0, 0, size[0] // 2, size[1] // 2))
    return image


def _reopen(data: bytes) -> Image.Image:
    image = Image.open(io.BytesIO(data))
    image.load()
    return image


# ----------------------------------------------------------------- what survives


def test_exif_including_gps_and_the_camera_name_is_removed() -> None:
    image = _photo()
    exif = image.getexif()
    exif[0x010F] = "SecretCameraMaker"
    gps = exif.get_ifd(0x8825)
    gps[1] = "S"
    gps[2] = (1.0, 16.0, 40.0)
    original = _encode(image, "JPEG", exif=exif.tobytes())
    assert b"SecretCameraMaker" in original  # the test input really carries it

    result = process_image(original, AVATAR)

    assert b"SecretCameraMaker" not in result.data
    assert b"Exif" not in result.data
    assert len(_reopen(result.data).getexif()) == 0


def test_the_cameras_rotation_is_applied_before_the_exif_is_dropped() -> None:
    image = _photo((400, 300))
    exif = image.getexif()
    exif[0x0112] = 6  # "rotate 90 degrees to display"
    original = _encode(image, "JPEG", exif=exif.tobytes())

    result = process_image(original, AVATAR)

    assert (result.width, result.height) == (300, 400)


@pytest.mark.parametrize(
    "junk",
    [APPENDED_MARKER, b"PK\x03\x04 pretend zip " * 5, b"\x00\x00ZERO-PADDED-TAIL-MARKER\x00\x00"],
)
@pytest.mark.parametrize("fmt", ["JPEG", "PNG"])
def test_bytes_appended_after_the_picture_do_not_survive(fmt: str, junk: bytes) -> None:
    original = _encode(_photo(), fmt) + junk
    assert junk in original

    result = process_image(original, AVATAR)

    assert junk not in result.data
    _reopen(result.data)


def test_a_comment_hidden_inside_a_jpeg_does_not_survive() -> None:
    original = _encode(_photo(), "JPEG", comment=b"HIDDEN-COMMENT-PAYLOAD")
    assert b"HIDDEN-COMMENT-PAYLOAD" in original

    result = process_image(original, AVATAR)

    assert b"HIDDEN-COMMENT-PAYLOAD" not in result.data


def test_png_text_chunks_and_colour_profiles_do_not_survive() -> None:
    info = PngInfo()
    info.add_text("Comment", "HIDDEN-TEXT-CHUNK")
    original = _encode(_photo(), "PNG", pnginfo=info, icc_profile=b"FAKE-ICC-PROFILE" * 8)
    assert b"HIDDEN-TEXT-CHUNK" in original

    result = process_image(original, AVATAR)

    assert b"HIDDEN-TEXT-CHUNK" not in result.data
    assert b"FAKE-ICC-PROFILE" not in result.data
    assert "icc_profile" not in _reopen(result.data).info


def test_the_result_is_always_newly_encoded_never_the_upload_itself() -> None:
    original = _encode(_photo(), "JPEG", quality=95)

    result = process_image(original, AVATAR)

    assert result.data != original


# ------------------------------------------------------- what the type is decided from


@pytest.mark.parametrize("fmt", ["JPEG", "PNG", "WEBP"])
def test_jpeg_png_and_webp_are_accepted_by_content(fmt: str) -> None:
    result = process_image(_encode(_photo(), fmt), AVATAR)

    assert result.content_type == "image/jpeg"
    assert result.extension == "jpg"
    assert _reopen(result.data).format == "JPEG"


def test_a_picture_with_transparency_stays_a_png() -> None:
    logo = Image.new("RGBA", (200, 200), (0, 0, 0, 0))
    logo.paste((200, 30, 30, 255), (50, 50, 150, 150))

    result = process_image(_encode(logo, "PNG"), AVATAR)

    assert (result.content_type, result.extension) == ("image/png", "png")
    reopened = _reopen(result.data)
    assert reopened.mode == "RGBA"
    assert reopened.getpixel((5, 5))[3] == 0  # type: ignore[index]


def test_a_palette_png_with_transparency_stays_a_png() -> None:
    palette = Image.new("P", (50, 50), 0)
    result = process_image(_encode(palette, "PNG", transparency=0), AVATAR)

    assert result.content_type == "image/png"


@pytest.mark.parametrize(
    "content",
    [
        pytest.param(b"", id="empty"),
        pytest.param(b"just some text", id="text"),
        pytest.param(b"<html><body>not a picture</body></html>", id="html"),
        pytest.param(b'<svg xmlns="http://www.w3.org/2000/svg"></svg>', id="svg"),
        pytest.param(b"%PDF-1.4\n%fake pdf", id="pdf"),
        pytest.param(b"MZ\x90\x00\x03" + b"\x00" * 100, id="windows-executable-header"),
        pytest.param(b"\x7fELF" + b"\x00" * 100, id="linux-executable-header"),
    ],
)
def test_things_that_are_not_pictures_are_refused(content: bytes) -> None:
    with pytest.raises(UnsupportedMediaError):
        process_image(content, AVATAR)


@pytest.mark.parametrize("fmt", ["GIF", "BMP", "TIFF", "ICO"])
def test_real_pictures_in_other_formats_are_refused(fmt: str) -> None:
    image = _photo((64, 64)) if fmt != "GIF" else _photo((64, 64)).convert("P")
    with pytest.raises(UnsupportedMediaError):
        process_image(_encode(image, fmt), AVATAR)


def test_a_truncated_picture_is_refused() -> None:
    whole = _encode(_photo((600, 600)), "JPEG")

    with pytest.raises(UnsupportedMediaError):
        process_image(whole[: len(whole) // 3], AVATAR)


def test_an_animated_picture_is_refused() -> None:
    first, second = _photo((64, 64)), Image.new("RGB", (64, 64), (200, 0, 0))
    animated = _encode(first, "WEBP", save_all=True, append_images=[second], duration=100)

    with pytest.raises(UnsupportedMediaError):
        process_image(animated, AVATAR)


# ---------------------------------------------------------------------- size limits


def test_a_file_over_the_policy_size_is_refused_before_it_is_decoded() -> None:
    with pytest.raises(PayloadTooLargeError):
        process_image(b"\x00" * (AVATAR.max_bytes + 1), AVATAR)


def test_a_picture_with_too_many_pixels_is_refused_even_though_the_file_is_small() -> None:
    bomb = _encode(Image.new("L", (8000, 8000), 0), "PNG")
    assert len(bomb) < AVATAR.max_bytes  # small on disk, huge once decoded

    with pytest.raises(ValidationError) as caught:
        process_image(bomb, AVATAR)

    assert caught.value.code == "image_too_large"


def test_a_picture_just_inside_the_pixel_cap_is_accepted() -> None:
    result = process_image(_encode(Image.new("RGB", (5000, 5000), (1, 2, 3)), "PNG"), POSTER)

    assert max(result.width, result.height) <= POSTER.max_dimension


def test_a_large_picture_is_shrunk_to_the_policy_without_changing_its_shape() -> None:
    result = process_image(_encode(_photo((3000, 2000)), "JPEG"), AVATAR)

    assert (result.width, result.height) == (1024, 683)


def test_a_small_picture_is_not_enlarged() -> None:
    result = process_image(_encode(_photo((200, 100)), "JPEG"), AVATAR)

    assert (result.width, result.height) == (200, 100)


def test_each_policy_has_its_own_dimension_limit() -> None:
    image = _encode(_photo((3000, 2000)), "JPEG")

    assert process_image(image, AVATAR).width == 1024
    assert process_image(image, POSTER).width == 2048
