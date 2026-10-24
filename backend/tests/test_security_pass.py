"""
Holes found in the pre-launch security pass, each pinned by a test: email case, sign-in timing,
logout across accounts, what verification says to people who cannot see a profile, who may
delete an organization's file, and connection requests to people who are not there.
"""

import uuid

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions.roles import Role
from app.modules.files.models import File
from app.modules.identity import service as identity_service
from app.modules.identity.models import User, UserStatus
from app.modules.memberships.models import Membership, MembershipStatus
from tests.test_alumni_privacy import PASSWORD, _grant, _make_actor, _make_profile
from tests.test_file_attach import _upload_logo
from tests.test_file_upload import _school_admin

API = "/api/v1"


async def _register(client: AsyncClient, email: str) -> Response:
    return await client.post(
        f"{API}/auth/register",
        json={"email": email, "password": PASSWORD, "confirm_18_or_older": True},
    )


# ------------------------------------------------------------------------ email case


async def test_an_email_is_stored_in_lower_case_and_signs_in_in_any_case(
    client: AsyncClient,
) -> None:
    local = f"Mixed.{uuid.uuid4().hex[:8]}"
    reg = await _register(client, f"{local}@Example.COM")
    assert reg.status_code == 201
    assert reg.json()["email"] == f"{local}@example.com".lower()

    for spelling in (f"{local}@example.com", f"{local.upper()}@EXAMPLE.com"):
        login = await client.post(
            f"{API}/auth/login", json={"email": spelling, "password": PASSWORD}
        )
        assert login.status_code == 200, spelling


async def test_two_spellings_of_one_email_are_one_account(client: AsyncClient) -> None:
    local = f"dup-{uuid.uuid4().hex[:8]}"
    first = await _register(client, f"{local}@example.com")
    assert first.status_code == 201
    second = await _register(client, f"{local.upper()}@example.com")
    assert second.status_code == 409


async def test_the_database_itself_refuses_an_email_with_capitals(
    db_session: AsyncSession,
) -> None:
    db_session.add(User(email=f"Cap-{uuid.uuid4().hex[:8]}@example.com", password_hash="x"))
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


# ------------------------------------------------------------------- sign-in timing


async def test_an_unknown_email_costs_the_same_password_work_as_a_known_one(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []
    real = identity_service.verify_password

    def spy(plain: str, hashed: str) -> bool:
        calls.append(hashed)
        return real(plain, hashed)

    monkeypatch.setattr(identity_service, "verify_password", spy)
    r = await client.post(
        f"{API}/auth/login",
        json={"email": f"nobody-{uuid.uuid4().hex[:8]}@example.com", "password": "Whatever-123"},
    )
    assert r.status_code == 401
    assert len(calls) == 1  # a hash was checked even though no such account exists


# ------------------------------------------------------------------------- logout


async def test_logout_cannot_end_someone_elses_session(client: AsyncClient) -> None:
    email = f"v-{uuid.uuid4().hex[:8]}@example.com"
    await _register(client, email)
    victim = (
        await client.post(f"{API}/auth/login", json={"email": email, "password": PASSWORD})
    ).json()
    attacker = await _make_actor(client)

    r = await client.post(
        f"{API}/auth/logout",
        json={"refresh_token": victim["refresh_token"]},
        headers=attacker.headers,
    )
    assert r.status_code == 204
    still = await client.post(
        f"{API}/auth/refresh", json={"refresh_token": victim["refresh_token"]}
    )
    assert still.status_code == 200


# --------------------------------------------------------------- verifying a profile


async def test_a_member_who_cannot_see_a_profile_learns_nothing_from_trying_to_verify_it(
    client: AsyncClient,
) -> None:
    owner = await _make_actor(client)
    private_id = await _make_profile(client, owner, visibility="private")
    stranger = await _make_actor(client)

    hidden = await client.patch(
        f"{API}/alumni/{private_id}/verify", json={"verified": True}, headers=stranger.headers
    )
    missing = await client.patch(
        f"{API}/alumni/{uuid.uuid4()}/verify", json={"verified": True}, headers=stranger.headers
    )
    assert hidden.status_code == missing.status_code == 404
    assert hidden.json() == missing.json()


async def test_trying_to_verify_a_visible_profile_without_rights_says_nothing_about_its_school(
    client: AsyncClient,
) -> None:
    owner = await _make_actor(client)
    profile_id = await _make_profile(client, owner, visibility="members_only")  # no school
    member = await _make_actor(client)

    r = await client.patch(
        f"{API}/alumni/{profile_id}/verify", json={"verified": True}, headers=member.headers
    )
    assert r.status_code == 403
    assert "school" not in r.json()["error"]["message"].lower()


# --------------------------------------------------------- an organization's files


async def test_someone_who_lost_their_role_cannot_delete_the_organizations_logo(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    school, admin = await _school_admin(client, db_session)
    logo = await _upload_logo(client, admin, school)
    set_logo = await client.put(
        f"{API}/organizations/{school.id}/logo",
        json={"file_id": logo["id"]},
        headers=admin.headers,
    )
    assert set_logo.status_code == 200

    membership = await db_session.scalar(
        select(Membership).where(Membership.user_id == admin.user_id)
    )
    assert membership is not None
    membership.status = MembershipStatus.REVOKED
    await db_session.flush()

    r = await client.delete(f"{API}/files/{logo['id']}", headers=admin.headers)
    assert r.status_code == 404
    assert await db_session.get(File, uuid.UUID(logo["id"])) is not None


async def test_a_current_admin_and_a_platform_admin_can_still_delete_the_logo_file(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    school, admin = await _school_admin(client, db_session)
    first = await _upload_logo(client, admin, school)
    assert (
        await client.delete(f"{API}/files/{first['id']}", headers=admin.headers)
    ).status_code == 204

    second = await _upload_logo(client, admin, school)
    root = await _make_actor(client)
    await _grant(db_session, root.user_id, Role.ADMIN, None)
    assert (
        await client.delete(f"{API}/files/{second['id']}", headers=root.headers)
    ).status_code == 204


# --------------------------------------------------------- connection requests


async def test_a_connection_request_to_nobody_is_not_found_not_a_crash(
    client: AsyncClient,
) -> None:
    actor = await _make_actor(client)
    r = await client.post(
        f"{API}/connections", json={"addressee_id": str(uuid.uuid4())}, headers=actor.headers
    )
    assert r.status_code == 404


async def test_a_connection_request_to_a_suspended_person_is_not_found(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    actor = await _make_actor(client)
    target = await _make_actor(client)
    user = await db_session.get(User, target.user_id)
    assert user is not None
    user.status = UserStatus.SUSPENDED
    await db_session.flush()

    r = await client.post(
        f"{API}/connections", json={"addressee_id": str(target.user_id)}, headers=actor.headers
    )
    assert r.status_code == 404
