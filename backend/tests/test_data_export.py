import json
import uuid

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.storage import LocalDiskStorage
from app.modules.files.models import File
from app.modules.identity.privacy import EXPORT_LIMIT_PER_HOUR
from tests._account_data import SECRET_BIO, build_person, email_of

API = "/api/v1"


async def test_you_get_a_downloadable_copy_of_your_own_data(
    client: AsyncClient, db_session: AsyncSession, storage: LocalDiskStorage
) -> None:
    person = await build_person(client, db_session)

    r = await client.get(f"{API}/auth/me/export", headers=person.actor.headers)

    assert r.status_code == 200, r.text
    assert (
        'attachment; filename="alumni-challenge-my-data.json"' in r.headers["content-disposition"]
    )
    assert r.headers["cache-control"] == "no-store"
    data = r.json()
    assert data["account"]["email"] == person.email
    assert data["account"]["id"] == str(person.actor.user_id)
    profile = data["profile"]
    assert profile["bio"] == SECRET_BIO
    assert profile["graduation_year"] == 2012
    assert profile["school_name"] == person.school.name
    assert profile["skills"] == ["beekeeping", "python"]
    assert profile["interests"] == ["golf"]
    assert profile["vouched_by_user_ids"] == [str(person.friend.user_id)]
    assert [(m["role"], m["organization_name"]) for m in data["roles"]] == [
        ("event_manager", person.school.name)
    ]
    assert [(c["direction"], c["other_user_id"]) for c in data["connections"]] == [
        ("sent", str(person.friend.user_id))
    ]
    assert [f["id"] for f in data["uploaded_files"]] == [person.avatar_file["id"]]
    assert [r_["reason"] for r_ in data["reports_you_filed"]] == ["spam"]
    assert any(a["action"] == "test.thing_i_did" for a in data["your_activity"])
    assert data["signed_in_devices"]


async def test_the_copy_never_contains_secrets_or_other_peoples_details(
    client: AsyncClient, db_session: AsyncSession, storage: LocalDiskStorage
) -> None:
    person = await build_person(client, db_session)
    friend_email = await email_of(db_session, person.friend)
    row = await db_session.get(File, uuid.UUID(person.avatar_file["id"]))
    assert row is not None

    r = await client.get(f"{API}/auth/me/export", headers=person.actor.headers)

    text = json.dumps(r.json())
    assert friend_email not in text  # the other person's address
    assert "Test Alum" not in json.dumps(r.json()["connections"])  # nor their name
    assert "$argon2" not in text and "password_hash" not in text
    assert row.storage_key not in text and "storage_key" not in text
    assert "token" not in text
    assert "refresh" not in text
    # What an admin did to me is not in "your activity", which lists only what I did.
    assert "test.thing_done_to_me" not in text
    assert "because" not in text


async def test_you_only_ever_get_your_own_data(
    client: AsyncClient, db_session: AsyncSession, storage: LocalDiskStorage
) -> None:
    person = await build_person(client, db_session)
    stranger = await build_person(client, db_session)

    mine = await client.get(f"{API}/auth/me/export", headers=person.actor.headers)
    theirs = await client.get(f"{API}/auth/me/export", headers=stranger.actor.headers)

    assert mine.json()["account"]["id"] == str(person.actor.user_id)
    assert theirs.json()["account"]["id"] == str(stranger.actor.user_id)
    assert stranger.email not in json.dumps(mine.json())
    assert person.email not in json.dumps(theirs.json())


async def test_an_export_needs_a_login(client: AsyncClient) -> None:
    r = await client.get(f"{API}/auth/me/export")

    assert r.status_code == 401


async def test_exports_are_rate_limited_per_person(
    client: AsyncClient, db_session: AsyncSession, storage: LocalDiskStorage
) -> None:
    person = await build_person(client, db_session)
    other = await build_person(client, db_session)

    for _ in range(EXPORT_LIMIT_PER_HOUR):
        assert (
            await client.get(f"{API}/auth/me/export", headers=person.actor.headers)
        ).status_code == 200
    blocked = await client.get(f"{API}/auth/me/export", headers=person.actor.headers)

    assert blocked.status_code == 429
    assert (
        await client.get(f"{API}/auth/me/export", headers=other.actor.headers)
    ).status_code == 200


async def test_an_account_with_no_profile_still_exports(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    from tests.test_alumni_privacy import _make_actor

    bare = await _make_actor(client)

    r = await client.get(f"{API}/auth/me/export", headers=bare.headers)

    assert r.status_code == 200
    assert r.json()["profile"] is None
    assert r.json()["connections"] == []
