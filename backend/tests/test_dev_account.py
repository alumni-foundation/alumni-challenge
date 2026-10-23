import uuid
from types import SimpleNamespace

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import cli
from app.core.permissions.roles import Role
from app.modules.alumni.models import AlumniProfile, VerificationStatus
from app.modules.identity.models import User
from app.modules.memberships.models import Membership, MembershipStatus
from app.modules.organizations.models import Organization, OrganizationType

API = "/api/v1"
PASSWORD = "dev-password-123"


def _email() -> str:
    return f"dev-{uuid.uuid4().hex[:10]}@example.com"


async def _orgs(db: AsyncSession) -> tuple[Organization, Organization]:
    school = await db.scalar(select(Organization).where(Organization.slug == cli.DEV_SCHOOL_SLUG))
    partner = await db.scalar(select(Organization).where(Organization.slug == cli.DEV_PARTNER_SLUG))
    assert school is not None
    assert partner is not None
    return school, partner


async def _grants(db: AsyncSession, user_id: uuid.UUID) -> set[tuple[Role, uuid.UUID | None]]:
    rows = await db.execute(
        select(Membership.role, Membership.organization_id).where(
            Membership.user_id == user_id, Membership.status == MembershipStatus.ACTIVE
        )
    )
    return {(role, org_id) for role, org_id in rows.all()}


async def _login(client: AsyncClient, email: str) -> dict[str, str]:
    r = await client.post(f"{API}/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def test_the_dev_account_gets_every_role(db_session: AsyncSession) -> None:
    user, created = await cli.ensure_dev_account(db_session, email=_email(), password=PASSWORD)
    assert created is True
    school, partner = await _orgs(db_session)
    assert school.type == OrganizationType.SCHOOL
    assert partner.type == OrganizationType.PARTNER

    assert await _grants(db_session, user.id) == {
        (Role.SUPER_ADMIN, None),
        (Role.ADMIN, None),
        (Role.MODERATOR, None),
        (Role.SCHOOL_ADMIN, school.id),
        (Role.EVENT_MANAGER, school.id),
        (Role.SPORTS_MANAGER, school.id),
        (Role.PARTNER_ADMIN, partner.id),
    }


async def test_the_dev_account_is_ready_to_use(db_session: AsyncSession) -> None:
    user, _ = await cli.ensure_dev_account(db_session, email=_email(), password=PASSWORD)
    assert user.email_verified_at is not None  # no "please verify your email" in the way
    profile = await db_session.scalar(select(AlumniProfile).where(AlumniProfile.user_id == user.id))
    assert profile is not None
    assert profile.verification_status == VerificationStatus.VERIFIED
    school, _ = await _orgs(db_session)
    assert profile.school_id == school.id


async def test_logging_in_shows_every_role_to_the_app(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    email = _email()
    await cli.ensure_dev_account(db_session, email=email, password=PASSWORD)
    school, partner = await _orgs(db_session)

    headers = await _login(client, email)
    r = await client.get(f"{API}/auth/me/roles", headers=headers)
    assert r.status_code == 200
    seen = {(m["role"], m["organization_id"]) for m in r.json()}
    assert seen == {
        ("super_admin", None),
        ("admin", None),
        ("moderator", None),
        ("school_admin", str(school.id)),
        ("event_manager", str(school.id)),
        ("sports_manager", str(school.id)),
        ("partner_admin", str(partner.id)),
    }
    me = await client.get(f"{API}/auth/me", headers=headers)
    assert me.json()["email_verified_at"] is not None


async def test_the_roles_really_open_each_area(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    email = _email()
    await cli.ensure_dev_account(db_session, email=email, password=PASSWORD)
    school, partner = await _orgs(db_session)
    headers = await _login(client, email)

    # moderator / admin area
    assert (await client.get(f"{API}/reports", headers=headers)).status_code == 200
    assert (await client.get(f"{API}/audit-log", headers=headers)).status_code == 200
    created = await client.post(
        f"{API}/organizations",
        json={"type": "school", "name": "Made By Dev", "slug": f"dev-{uuid.uuid4().hex[:8]}"},
        headers=headers,
    )
    assert created.status_code == 201
    # school admin area
    edit_school = await client.patch(
        f"{API}/organizations/{school.id}", json={"description": "Edited"}, headers=headers
    )
    assert edit_school.status_code == 200
    # partner admin area
    edit_partner = await client.patch(
        f"{API}/organizations/{partner.id}", json={"description": "Edited"}, headers=headers
    )
    assert edit_partner.status_code == 200
    # member view
    assert (await client.get(f"{API}/alumni/profile/me", headers=headers)).status_code == 200


async def test_running_it_again_changes_nothing(db_session: AsyncSession) -> None:
    email = _email()
    user, created = await cli.ensure_dev_account(db_session, email=email, password=PASSWORD)
    first = await _grants(db_session, user.id)
    first_verified = user.email_verified_at

    again, created_again = await cli.ensure_dev_account(db_session, email=email, password=None)
    assert created is True
    assert created_again is False
    assert again.id == user.id
    assert await _grants(db_session, user.id) == first
    assert again.email_verified_at == first_verified

    total = await db_session.scalar(
        select(func.count()).select_from(Membership).where(Membership.user_id == user.id)
    )
    assert total == 7
    profiles = await db_session.scalar(
        select(func.count()).select_from(AlumniProfile).where(AlumniProfile.user_id == user.id)
    )
    assert profiles == 1
    orgs = await db_session.scalar(
        select(func.count())
        .select_from(Organization)
        .where(Organization.slug.in_([cli.DEV_SCHOOL_SLUG, cli.DEV_PARTNER_SLUG]))
    )
    assert orgs == 2


async def test_a_revoked_role_is_switched_back_on(db_session: AsyncSession) -> None:
    email = _email()
    user, _ = await cli.ensure_dev_account(db_session, email=email, password=PASSWORD)
    moderator = await db_session.scalar(
        select(Membership).where(Membership.user_id == user.id, Membership.role == Role.MODERATOR)
    )
    assert moderator is not None
    moderator.status = MembershipStatus.REVOKED
    await db_session.flush()

    await cli.ensure_dev_account(db_session, email=email, password=None)
    assert (Role.MODERATOR, None) in await _grants(db_session, user.id)


@pytest.mark.parametrize("password", [None, "short"])
async def test_a_new_account_needs_a_proper_password(
    db_session: AsyncSession, password: str | None
) -> None:
    with pytest.raises(ValueError):
        await cli.ensure_dev_account(db_session, email=_email(), password=password)
    assert await db_session.scalar(select(func.count()).select_from(User)) is not None


@pytest.mark.parametrize("environment", ["production", "staging"])
async def test_it_refuses_to_run_outside_development(
    monkeypatch: pytest.MonkeyPatch, environment: str
) -> None:
    monkeypatch.setattr(cli, "get_settings", lambda: SimpleNamespace(environment=environment))

    def _must_not_touch_the_database() -> None:
        raise AssertionError("the command reached the database in a non-development environment")

    monkeypatch.setattr(cli, "async_session_factory", _must_not_touch_the_database)

    assert await cli._create_dev_account(_email(), PASSWORD) == 1
