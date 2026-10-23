import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from httpx import AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.permissions.roles import Role
from app.infrastructure.storage import LocalDiskStorage
from app.modules.files.models import File
from app.modules.files.urls import FILE_TOKEN_PURPOSE, signed_file_path
from app.modules.identity.security import create_purpose_token
from tests.test_alumni_privacy import Actor, _grant, _make_actor, _make_school
from tests.test_file_upload import (
    API,
    _encode,
    _photo,
    _school_admin,
    _stored_files,
    _upload,
)

settings = get_settings()


async def _avatar(client: AsyncClient, owner: Actor) -> dict[str, Any]:
    r = await _upload(client, owner, _encode(_photo(), "JPEG"))
    assert r.status_code == 201, r.text
    body: dict[str, Any] = r.json()
    return body


async def _logo(client: AsyncClient, db: AsyncSession) -> tuple[dict[str, Any], Actor]:
    school, admin = await _school_admin(client, db)
    r = await _upload(
        client,
        admin,
        _encode(_photo(), "PNG"),
        purpose="organization_logo",
        organization_id=school.id,
    )
    assert r.status_code == 201, r.text
    body: dict[str, Any] = r.json()
    return body, admin


def _token_for(file_id: str, *, purpose: str = FILE_TOKEN_PURPOSE, seconds: int = 300) -> str:
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "sub": file_id,
            "type": purpose,
            "iat": now,
            "exp": now + timedelta(seconds=seconds),
        },
        settings.secret_key.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )


def _content(client: AsyncClient, file_id: str, token: str | None = None) -> Any:
    params = {"token": token} if token is not None else {}
    return client.get(f"{API}/files/{file_id}/content", params=params)


# ------------------------------------------------------------------- public files


async def test_a_logo_has_one_permanent_address_anyone_can_load(
    client: AsyncClient, db_session: AsyncSession, storage: LocalDiskStorage
) -> None:
    logo, _ = await _logo(client, db_session)

    assert logo["url"] == f"{API}/files/{logo['id']}/content"
    assert "token" not in logo["url"]
    r: Response = await client.get(logo["url"])  # no login, no token

    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == logo["mime_type"]
    assert r.headers["cache-control"] == "public, max-age=31536000, immutable"
    assert r.headers["cross-origin-resource-policy"] == "cross-origin"
    assert r.headers["x-content-type-options"] == "nosniff"
    row = await db_session.get(File, uuid.UUID(logo["id"]))
    assert row is not None
    assert r.content == await storage.get(row.storage_key)


async def test_a_public_files_address_does_not_expire(
    client: AsyncClient, db_session: AsyncSession, storage: LocalDiskStorage
) -> None:
    logo, _ = await _logo(client, db_session)

    first = await client.get(logo["url"])
    second = await client.get(logo["url"])

    assert first.content == second.content
    assert first.status_code == second.status_code == 200


# ------------------------------------------------------------------ private files


async def test_a_private_file_cannot_be_fetched_without_a_signed_link(
    client: AsyncClient, db_session: AsyncSession, storage: LocalDiskStorage
) -> None:
    owner = await _make_actor(client)
    avatar = await _avatar(client, owner)

    plain = await _content(client, avatar["id"])
    even_for_the_owner = await client.get(
        f"{API}/files/{avatar['id']}/content", headers=owner.headers
    )

    assert plain.status_code == 404
    assert even_for_the_owner.status_code == 404


async def test_the_link_handed_back_on_upload_works_and_is_private_and_short_lived(
    client: AsyncClient, db_session: AsyncSession, storage: LocalDiskStorage
) -> None:
    owner = await _make_actor(client)
    avatar = await _avatar(client, owner)

    assert "?token=" in avatar["url"]
    r = await client.get(avatar["url"])

    assert r.status_code == 200
    assert r.headers["content-type"] == "image/jpeg"
    assert r.headers["cache-control"] == "private, max-age=300"
    assert r.headers["cross-origin-resource-policy"] == "cross-origin"
    token = avatar["url"].split("token=", 1)[1]
    claims = jwt.decode(token, options={"verify_signature": False})
    assert claims["sub"] == avatar["id"]
    assert claims["exp"] - claims["iat"] == 300


async def test_every_way_of_being_refused_looks_the_same(
    client: AsyncClient, db_session: AsyncSession, storage: LocalDiskStorage
) -> None:
    owner = await _make_actor(client)
    mine = await _avatar(client, owner)
    someone_elses = await _avatar(client, await _make_actor(client))
    missing = str(uuid.uuid4())

    attempts = {
        "no such file": _content(client, missing, _token_for(missing)),
        "no token": _content(client, mine["id"]),
        "garbage token": _content(client, mine["id"], "not-a-token"),
        "expired token": _content(client, mine["id"], _token_for(mine["id"], seconds=-60)),
        "another file's token": _content(client, mine["id"], _token_for(someone_elses["id"])),
        "wrong kind of token": _content(
            client, mine["id"], _token_for(mine["id"], purpose="email_verify")
        ),
        "token signed with another key": _content(
            client,
            mine["id"],
            jwt.encode(
                {"sub": mine["id"], "type": FILE_TOKEN_PURPOSE, "exp": 4102444800},
                "some-other-secret-key-0123456789abcdef",
                algorithm="HS256",
            ),
        ),
        "tampered token": _content(client, mine["id"], mine["url"].split("token=")[1][:-3] + "abc"),
    }
    results = {name: await call for name, call in attempts.items()}

    for name, r in results.items():
        assert r.status_code == 404, (name, r.status_code)
    bodies = {r.content for r in results.values()}
    assert len(bodies) == 1, "refusals differ, which would reveal which files exist"


async def test_a_users_token_cannot_be_replayed_as_a_file_link(
    client: AsyncClient, db_session: AsyncSession, storage: LocalDiskStorage
) -> None:
    owner = await _make_actor(client)
    avatar = await _avatar(client, owner)
    verification_token = create_purpose_token(
        owner.user_id, purpose="email_verify", expire_minutes=60
    )

    r = await _content(client, avatar["id"], verification_token)

    assert r.status_code == 404


async def test_a_file_whose_bytes_are_missing_is_not_found_not_an_error(
    client: AsyncClient, db_session: AsyncSession, storage: LocalDiskStorage
) -> None:
    logo, _ = await _logo(client, db_session)
    row = await db_session.get(File, uuid.UUID(logo["id"]))
    assert row is not None
    await storage.delete(row.storage_key)

    r = await client.get(logo["url"])

    assert r.status_code == 404


async def test_signed_links_are_new_every_time(
    client: AsyncClient, db_session: AsyncSession, storage: LocalDiskStorage
) -> None:
    owner = await _make_actor(client)
    avatar = await _avatar(client, owner)
    file_id = uuid.UUID(avatar["id"])

    assert signed_file_path(file_id).startswith(f"{API}/files/{file_id}/content?token=")
    refreshed = await client.get(f"{API}/files/{file_id}", headers=owner.headers)

    assert refreshed.status_code == 200
    assert (await client.get(refreshed.json()["url"])).status_code == 200


# ------------------------------------------------------------ details and deleting


async def test_only_the_owner_or_a_platform_admin_can_see_a_files_details(
    client: AsyncClient, db_session: AsyncSession, storage: LocalDiskStorage
) -> None:
    owner = await _make_actor(client)
    avatar = await _avatar(client, owner)
    stranger = await _make_actor(client)
    admin = await _make_actor(client)
    await _grant(db_session, admin.user_id, Role.ADMIN, None)
    moderator = await _make_actor(client)
    await _grant(db_session, moderator.user_id, Role.MODERATOR, None)
    path = f"{API}/files/{avatar['id']}"

    assert (await client.get(path, headers=owner.headers)).status_code == 200
    assert (await client.get(path, headers=admin.headers)).status_code == 200
    assert (await client.get(path, headers=stranger.headers)).status_code == 404
    assert (await client.get(path, headers=moderator.headers)).status_code == 404
    assert (await client.get(path)).status_code == 401


async def test_deleting_removes_the_row_and_the_bytes(
    client: AsyncClient, db_session: AsyncSession, storage: LocalDiskStorage
) -> None:
    owner = await _make_actor(client)
    avatar = await _avatar(client, owner)

    r = await client.delete(f"{API}/files/{avatar['id']}", headers=owner.headers)

    assert r.status_code == 204
    assert await db_session.scalar(select(File).where(File.id == uuid.UUID(avatar["id"]))) is None
    assert _stored_files(storage) == []
    assert (await client.get(avatar["url"])).status_code == 404


async def test_nobody_else_can_delete_a_file(
    client: AsyncClient, db_session: AsyncSession, storage: LocalDiskStorage
) -> None:
    school = await _make_school(db_session)
    owner = await _make_actor(client)
    avatar = await _avatar(client, owner)
    stranger = await _make_actor(client)
    school_admin = await _make_actor(client)
    await _grant(db_session, school_admin.user_id, Role.SCHOOL_ADMIN, school.id)
    path = f"{API}/files/{avatar['id']}"

    for actor in (stranger, school_admin):
        assert (await client.delete(path, headers=actor.headers)).status_code == 404
    assert (await client.delete(path)).status_code == 401
    assert len(_stored_files(storage)) == 1
    assert (await client.get(avatar["url"])).status_code == 200
