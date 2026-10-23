"""
Turning an uploaded picture into a safe one.

We never store what the user sent. The upload is opened to find out what it really is (the
file name and the Content-Type the client claims are never looked at), checked, decoded, and
then drawn again into a brand-new image that is encoded from scratch. Because the new file is
built from the pixels alone, nothing else survives: not the EXIF block (camera, time, GPS
location), not an embedded colour profile, not text chunks, and not any bytes appended after
the end of the image.
"""

import io
import warnings
from dataclasses import dataclass

from PIL import Image, ImageOps, UnidentifiedImageError

from app.core.errors.exceptions import PayloadTooLargeError, UnsupportedMediaError, ValidationError
from app.modules.files.policies import UploadPolicy

# Decided from the content, not from a name or header. No GIF (animation), SVG (it can carry
# script), BMP, TIFF or anything else.
_ALLOWED_FORMATS = frozenset({"JPEG", "PNG", "WEBP"})

_JPEG_QUALITY = 85


@dataclass(frozen=True)
class ProcessedImage:
    data: bytes
    content_type: str
    extension: str
    width: int
    height: int


def _has_transparency(image: Image.Image) -> bool:
    return image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info)


def process_image(data: bytes, policy: UploadPolicy) -> ProcessedImage:
    if len(data) > policy.max_bytes:
        raise PayloadTooLargeError(
            f"That file is too large. The limit is {policy.max_bytes // (1024 * 1024)} MB."
        )

    try:
        # A decompression-bomb warning is a refusal here, not something to log and carry on.
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            return _reencode(data, policy)
    except (PayloadTooLargeError, UnsupportedMediaError, ValidationError):
        raise
    except (UnidentifiedImageError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise UnsupportedMediaError("That file is not a picture we can use.") from None
    except (OSError, ValueError, SyntaxError, EOFError):
        # Truncated, corrupt or otherwise undecodable.
        raise UnsupportedMediaError("That file is not a picture we can use.") from None


def _reencode(data: bytes, policy: UploadPolicy) -> ProcessedImage:
    with Image.open(io.BytesIO(data)) as opened:
        if opened.format not in _ALLOWED_FORMATS:
            raise UnsupportedMediaError("Only JPEG, PNG and WebP pictures are accepted.")
        width, height = opened.size
        if width < 1 or height < 1 or width * height > policy.max_pixels:
            raise ValidationError(
                "That picture has too many pixels. Please use a smaller one.",
                code="image_too_large",
            )
        if getattr(opened, "n_frames", 1) > 1:
            raise UnsupportedMediaError("Animated pictures are not accepted.")

        opened.load()
        # Apply the camera's rotation now: it is about to be thrown away with the EXIF block.
        upright = ImageOps.exif_transpose(opened)
        keep_alpha = _has_transparency(upright)
        mode = "RGBA" if keep_alpha else "RGB"
        converted = upright.convert(mode)

    # Rebuilt from raw pixels: a new image object carries no metadata at all.
    clean = Image.frombytes(mode, converted.size, converted.tobytes())
    clean.thumbnail((policy.max_dimension, policy.max_dimension), Image.Resampling.LANCZOS)

    out = io.BytesIO()
    if keep_alpha:
        clean.save(out, format="PNG", optimize=True)
        content_type, extension = "image/png", "png"
    else:
        clean.save(out, format="JPEG", quality=_JPEG_QUALITY, optimize=True)
        content_type, extension = "image/jpeg", "jpg"
    return ProcessedImage(
        data=out.getvalue(),
        content_type=content_type,
        extension=extension,
        width=clean.width,
        height=clean.height,
    )
