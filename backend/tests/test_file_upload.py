import io
import os
import re
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from httpx import AsyncClient, Response
from PIL import Image
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions.roles import Role
from app.infrastructure.storage import LocalDiskStorage, get_storage
from app.main import app
from app.modules.files import service as files_service
from app.modules.files.models import File, FilePurpose
from app.modules.identity.models import User
from tests.test_alumni_privacy import Actor, _grant, _make_actor, _make_school

API = "/api/v1"
MIB = 1024 * 1024


@pytest.fixture
def storage(client: AsyncClient, tmp_path: Path) -> Iterator[LocalDiskStorage]:
    """Uploads go to a throwaway folder. Depends on `client` so the override is set after it
    and cleared with it."""
    local = LocalDiskStorage(tmp_path / "uploads")
    app.dependency_overrides[get_storage] = lambda: local
    yield local


def _stored_files(storage: LocalDiskStorage) -> list[Path]:
    root: Path = storage._root
    return [p for p in root.rglob("*") if p.is_file()] if root.exists() else []


def _encode(image: Image.Image, fmt: str, **options: Any) -> bytes:
    out = io.BytesIO()
    image.save(out, format=fmt, **options)
    return out.getvalue()


def _photo(size: tuple[int, int] = (400, 300)) -> Image.Image:
    image = Image.new("RGB", size, (10, 120, 200))
    image.paste((250, 250, 20), (0, 0, size[0] // 2, size[1] // 2))
    return image


def _upload(
    client: AsyncClient,
    actor: Actor | None,
    data: bytes,
    *,
    purpose: str = "avatar",
    organization_id: uuid.UUID | None = None,
    filename: str = "photo.jpg",
    content_type: str = "image/jpeg",
) -> Any:
    form: dict[str, str] = {"purpose": purpose}
    if organization_id is not None:
        form["organization_id"] = str(organization_id)
    return client.post(
        f"{API}/files",
        data=form,
        files={"file": (filename, data, content_type)},
        headers=actor.headers if actor else {},
    )


async def _rows(db: AsyncSession) -> int:
    return int(await db.scalar(select(func.count()).select_from(File)) or 0)


async def _school_admin(client: AsyncClient, db: AsyncSession) -> tuple[Any, Actor]:
    school = await _make_school(db)
    admin = await _make_actor(client)
    await _grant(db, admin.user_id, Role.SCHOOL_ADMIN, school.id)
    return school, admin


# ------------------------------------------------------------------- the happy path


async def test_a_member_can_upload_an_avatar(
    client: AsyncClient, db_session: AsyncSession, storage: LocalDiskStorage
) -> None:
    user = await _make_actor(client)

    r: Response = await _upload(client, user, _encode(_photo(), "JPEG"))

    assert r.status_code == 201, r.text
    body = r.json()
    assert body["purpose"] == "avatar"
    assert body["visibility"] == "private"
    assert body["mime_type"] == "image/jpeg"
    assert (body["width"], body["height"]) == (400, 300)
    assert "storage_key" not in body
    row = await db_session.get(File, uuid.UUID(body["id"]))
    assert row is not None and row.owner_user_id == user.user_id
    assert await storage.exists(row.storage_key)
    assert row.size_bytes == len(await storage.get(row.storage_key))


async def test_the_stored_file_is_the_rebuilt_picture_not_the_upload(
    client: AsyncClient, db_session: AsyncSession, storage: LocalDiskStorage
) -> None:
    user = await _make_actor(client)
    image = _photo()
    exif = image.getexif()
    exif[0x010F] = "SecretCameraMaker"
    gps = exif.get_ifd(0x8825)
    gps[1] = "S"
    gps[2] = (1.0, 16.0, 40.0)
    upload = _encode(image, "JPEG", exif=exif.tobytes()) + b"APPENDED-AFTER-THE-IMAGE"

    r = await _upload(client, user, upload)

    row = await db_session.get(File, uuid.UUID(r.json()["id"]))
    assert row is not None
    stored = await storage.get(row.storage_key)
    assert b"SecretCameraMaker" not in stored
    assert b"APPENDED-AFTER-THE-IMAGE" not in stored
    assert len(Image.open(io.BytesIO(stored)).getexif()) == 0


async def test_the_name_and_type_the_client_claims_are_ignored(
    client: AsyncClient, db_session: AsyncSession, storage: LocalDiskStorage
) -> None:
    user = await _make_actor(client)
    png = _encode(_photo(), "PNG")

    r = await _upload(
        client,
        user,
        png,
        filename="../../etc/evil.php",
        content_type="text/html",
    )

    assert r.status_code == 201, r.text
    row = await db_session.get(File, uuid.UUID(r.json()["id"]))
    assert row is not None
    assert row.mime_type == "image/jpeg"  # decided from the bytes, not "text/html"
    assert re.fullmatch(r"private/avatar/[0-9a-f]{32}\.jpg", row.storage_key), row.storage_key
    assert "evil" not in row.storage_key and "php" not in row.storage_key
    assert [p.suffix for p in _stored_files(storage)] == [".jpg"]


async def test_a_web_page_is_refused_whatever_it_claims_to_be(
    client: AsyncClient, db_session: AsyncSession, storage: LocalDiskStorage
) -> None:
    user = await _make_actor(client)

    r = await _upload(
        client,
        user,
        b"<html><body>hello</body></html>",
        filename="photo.png",
        content_type="image/png",
    )

    assert r.status_code == 415, r.text
    assert r.json()["error"]["code"] == "unsupported_media_type"
    assert await _rows(db_session) == 0
    assert _stored_files(storage) == []


async def test_each_upload_gets_its_own_unguessable_key(
    client: AsyncClient, db_session: AsyncSession, storage: LocalDiskStorage
) -> None:
    user = await _make_actor(client)
    data = _encode(_photo(), "JPEG")

    first = await _upload(client, user, data)
    second = await _upload(client, user, data)

    keys = {
        row.storage_key
        for row in await db_session.scalars(select(File).where(File.owner_user_id == user.user_id))
    }
    assert len(keys) == 2
    assert first.json()["id"] != second.json()["id"]


async def test_an_invalid_picture_leaves_nothing_behind(
    client: AsyncClient, db_session: AsyncSession, storage: LocalDiskStorage
) -> None:
    user = await _make_actor(client)
    whole = _encode(_photo((600, 600)), "JPEG")

    r = await _upload(client, user, whole[: len(whole) // 3])

    assert r.status_code == 415
    assert await _rows(db_session) == 0
    assert _stored_files(storage) == []


async def test_a_database_failure_after_storing_removes_the_stored_bytes(
    client: AsyncClient,
    db_session: AsyncSession,
    storage: LocalDiskStorage,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    actor = await _make_actor(client)
    user = await db_session.get(User, actor.user_id)
    assert user is not None

    async def _boom() -> None:
        raise RuntimeError("database went away")

    monkeypatch.setattr(db_session, "flush", _boom)
    with pytest.raises(RuntimeError):
        await files_service.upload_image(
            db_session,
            storage,
            user=user,
            purpose=FilePurpose.AVATAR,
            organization_id=None,
            data=_encode(_photo(), "JPEG"),
        )

    assert _stored_files(storage) == []


async def test_a_failed_commit_removes_the_stored_bytes(
    client: AsyncClient,
    db_session: AsyncSession,
    storage: LocalDiskStorage,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    actor = await _make_actor(client)

    async def _boom() -> None:
        raise RuntimeError("commit failed")

    monkeypatch.setattr(db_session, "commit", _boom)
    with pytest.raises(RuntimeError):
        await _upload(client, actor, _encode(_photo(), "JPEG"))

    assert _stored_files(storage) == []


# --------------------------------------------------------------------- who may upload


async def test_uploading_needs_a_login(client: AsyncClient, storage: LocalDiskStorage) -> None:
    r = await _upload(client, None, _encode(_photo(), "JPEG"))

    assert r.status_code == 401
    assert _stored_files(storage) == []


async def test_an_unknown_purpose_is_rejected(
    client: AsyncClient, storage: LocalDiskStorage
) -> None:
    user = await _make_actor(client)

    r = await _upload(client, user, _encode(_photo(), "JPEG"), purpose="passport_scan")

    assert r.status_code == 422


async def test_an_avatar_cannot_be_tied_to_an_organization(
    client: AsyncClient, db_session: AsyncSession, storage: LocalDiskStorage
) -> None:
    school = await _make_school(db_session)
    user = await _make_actor(client)

    r = await _upload(client, user, _encode(_photo(), "JPEG"), organization_id=school.id)

    assert r.status_code == 422


async def test_a_school_admin_can_upload_their_own_schools_logo_and_it_is_public(
    client: AsyncClient, db_session: AsyncSession, storage: LocalDiskStorage
) -> None:
    school, admin = await _school_admin(client, db_session)

    r = await _upload(
        client,
        admin,
        _encode(_photo(), "PNG"),
        purpose="organization_logo",
        organization_id=school.id,
    )

    assert r.status_code == 201, r.text
    assert r.json()["visibility"] == "public"
    assert r.json()["organization_id"] == str(school.id)
    row = await db_session.get(File, uuid.UUID(r.json()["id"]))
    assert row is not None and row.storage_key.startswith("public/organization_logo/")


async def test_a_school_admin_cannot_upload_a_logo_for_another_school(
    client: AsyncClient, db_session: AsyncSession, storage: LocalDiskStorage
) -> None:
    _, admin_a = await _school_admin(client, db_session)
    school_b = await _make_school(db_session)

    r = await _upload(
        client,
        admin_a,
        _encode(_photo(), "PNG"),
        purpose="organization_logo",
        organization_id=school_b.id,
    )

    assert r.status_code == 403, r.text
    assert await _rows(db_session) == 0
    assert _stored_files(storage) == []


async def test_a_nonexistent_organization_looks_the_same_as_one_you_have_no_rights_in(
    client: AsyncClient, db_session: AsyncSession, storage: LocalDiskStorage
) -> None:
    user = await _make_actor(client)
    other = await _make_school(db_session)

    nobody = await _upload(
        client,
        user,
        _encode(_photo(), "PNG"),
        purpose="organization_logo",
        organization_id=uuid.uuid4(),
    )
    elsewhere = await _upload(
        client,
        user,
        _encode(_photo(), "PNG"),
        purpose="organization_logo",
        organization_id=other.id,
    )

    assert nobody.status_code == elsewhere.status_code == 403
    assert nobody.json() == elsewhere.json()


async def test_ordinary_members_and_managers_cannot_upload_a_logo(
    client: AsyncClient, db_session: AsyncSession, storage: LocalDiskStorage
) -> None:
    school, _ = await _school_admin(client, db_session)
    alum = await _make_actor(client)
    manager = await _make_actor(client)
    await _grant(db_session, manager.user_id, Role.EVENT_MANAGER, school.id)

    for actor in (alum, manager):
        r = await _upload(
            client,
            actor,
            _encode(_photo(), "PNG"),
            purpose="organization_logo",
            organization_id=school.id,
        )
        assert r.status_code == 403, r.text


async def test_a_logo_always_needs_an_organization(
    client: AsyncClient, db_session: AsyncSession, storage: LocalDiskStorage
) -> None:
    boss = await _make_actor(client)
    await _grant(db_session, boss.user_id, Role.SUPER_ADMIN, None)

    r = await _upload(client, boss, _encode(_photo(), "PNG"), purpose="organization_logo")

    assert r.status_code == 422


async def test_an_event_manager_can_upload_a_poster_for_their_organization(
    client: AsyncClient, db_session: AsyncSession, storage: LocalDiskStorage
) -> None:
    school, _ = await _school_admin(client, db_session)
    manager = await _make_actor(client)
    await _grant(db_session, manager.user_id, Role.EVENT_MANAGER, school.id)

    r = await _upload(
        client,
        manager,
        _encode(_photo((3000, 2000)), "JPEG"),
        purpose="event_poster",
        organization_id=school.id,
    )

    assert r.status_code == 201, r.text
    assert r.json()["visibility"] == "public"
    assert r.json()["width"] == 2048  # the poster policy's own, larger, limit


async def test_a_platform_admin_can_upload_a_poster_for_the_platform_itself(
    client: AsyncClient, db_session: AsyncSession, storage: LocalDiskStorage
) -> None:
    admin = await _make_actor(client)
    await _grant(db_session, admin.user_id, Role.ADMIN, None)
    manager = await _make_actor(client)
    school = await _make_school(db_session)
    await _grant(db_session, manager.user_id, Role.EVENT_MANAGER, school.id)
    data = _encode(_photo(), "JPEG")

    allowed = await _upload(client, admin, data, purpose="event_poster")
    refused = await _upload(client, manager, data, purpose="event_poster")

    assert allowed.status_code == 201, allowed.text
    assert refused.status_code == 422, refused.text


# ------------------------------------------------------------------------- the limits


async def test_the_upload_route_alone_takes_a_body_larger_than_the_global_limit(
    client: AsyncClient, db_session: AsyncSession, storage: LocalDiskStorage
) -> None:
    school, _ = await _school_admin(client, db_session)
    manager = await _make_actor(client)
    await _grant(db_session, manager.user_id, Role.EVENT_MANAGER, school.id)
    noise = Image.frombytes("RGB", (1200, 1200), os.urandom(1200 * 1200 * 3))
    big = _encode(noise, "PNG")
    assert 2 * MIB < len(big) < 5 * MIB  # over the global limit, inside the poster's own

    uploaded = await _upload(
        client, manager, big, purpose="event_poster", organization_id=school.id
    )
    elsewhere = await client.post(
        f"{API}/auth/login", content=b"x" * (3 * MIB), headers={"Content-Type": "text/plain"}
    )

    assert uploaded.status_code == 201, uploaded.text
    assert elsewhere.status_code == 413


async def test_a_body_over_the_upload_limit_is_refused_outright(
    client: AsyncClient, storage: LocalDiskStorage
) -> None:
    user = await _make_actor(client)

    r = await _upload(client, user, b"\x00" * (7 * MIB))

    assert r.status_code == 413
    assert r.json()["error"]["code"] == "payload_too_large"
    assert _stored_files(storage) == []


async def test_each_purpose_has_its_own_size_limit(
    client: AsyncClient, db_session: AsyncSession, storage: LocalDiskStorage
) -> None:
    user = await _make_actor(client)

    r = await _upload(client, user, b"\x00" * (3 * MIB))  # inside 6 MiB, over an avatar's 2 MiB

    assert r.status_code == 413
    assert "2 MB" in r.json()["error"]["message"]
    assert await _rows(db_session) == 0


async def test_a_picture_with_too_many_pixels_is_refused(
    client: AsyncClient, db_session: AsyncSession, storage: LocalDiskStorage
) -> None:
    user = await _make_actor(client)
    bomb = _encode(Image.new("L", (8000, 8000), 0), "PNG")
    assert len(bomb) < 2 * MIB

    r = await _upload(client, user, bomb, content_type="image/png")

    assert r.status_code == 422
    assert r.json()["error"]["code"] == "image_too_large"
    assert _stored_files(storage) == []


async def test_there_is_a_cap_on_how_many_files_one_person_can_keep(
    client: AsyncClient,
    db_session: AsyncSession,
    storage: LocalDiskStorage,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(files_service, "MAX_FILES_PER_USER", 2)
    user = await _make_actor(client)
    other = await _make_actor(client)
    data = _encode(_photo(), "JPEG")

    assert (await _upload(client, user, data)).status_code == 201
    assert (await _upload(client, user, data)).status_code == 201
    capped = await _upload(client, user, data)

    assert capped.status_code == 422
    assert capped.json()["error"]["code"] == "file_limit_reached"
    assert len(_stored_files(storage)) == 2
    assert (await _upload(client, other, data)).status_code == 201


async def test_uploads_are_rate_limited_per_person(
    client: AsyncClient,
    db_session: AsyncSession,
    storage: LocalDiskStorage,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(files_service, "UPLOADS_PER_HOUR", 2)
    user = await _make_actor(client)
    other = await _make_actor(client)
    data = _encode(_photo(), "JPEG")

    assert (await _upload(client, user, data)).status_code == 201
    assert (await _upload(client, user, data)).status_code == 201
    limited = await _upload(client, user, data)

    assert limited.status_code == 429
    assert (await _upload(client, other, data)).status_code == 201


async def test_a_refused_upload_does_not_use_up_the_work_of_decoding(
    client: AsyncClient,
    db_session: AsyncSession,
    storage: LocalDiskStorage,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Permission, rate limit and cap are all checked before any image is opened."""
    monkeypatch.setattr(files_service, "MAX_FILES_PER_USER", 0)

    def _must_not_decode(*_: object) -> None:
        raise AssertionError("an image was decoded for a request that should have been refused")

    monkeypatch.setattr(files_service, "process_image", _must_not_decode)
    user = await _make_actor(client)

    r = await _upload(client, user, _encode(_photo(), "JPEG"))

    assert r.status_code == 422
