import uuid
from typing import Any

from httpx import AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions.roles import Role
from app.modules.alumni.models import (
    AlumniProfile,
    ProfileVisibility,
    VerificationMethod,
    VerificationStatus,
)
from app.modules.identity.models import User, UserStatus
from app.modules.memberships.models import Membership, MembershipStatus
from app.modules.organizations.models import Organization, OrganizationType
from tests.test_alumni_privacy import Actor, _grant, _make_actor, _make_profile, _make_school

API = "/api/v1"


async def _school_with_admin(client: AsyncClient, db: AsyncSession) -> tuple[Organization, Actor]:
    school = await _make_school(db)
    admin = await _make_actor(client)
    await _grant(db, admin.user_id, Role.SCHOOL_ADMIN, school.id)
    return school, admin


async def _alum(
    client: AsyncClient,
    db: AsyncSession,
    school: Organization,
    *,
    name: str = "Test Alum",
    visibility: ProfileVisibility = ProfileVisibility.MEMBERS_ONLY,
    verified: bool = False,
    year: int | None = None,
) -> tuple[Actor, uuid.UUID]:
    actor = await _make_actor(client)
    profile_id = uuid.UUID(
        await _make_profile(client, actor, visibility=visibility.value, school_id=school.id)
    )
    profile = await db.get(AlumniProfile, profile_id)
    assert profile is not None
    profile.full_name = name
    profile.graduation_year = year
    if verified:
        profile.verification_status = VerificationStatus.VERIFIED
        profile.verification_method = VerificationMethod.ADMIN
    await db.flush()
    return actor, profile_id


def _get(client: AsyncClient, actor: Actor, path: str, **params: Any) -> Any:
    return client.get(f"{API}{path}", params=params, headers=actor.headers)


# --------------------------------------------------------------------------- members


async def test_a_school_admin_lists_the_people_who_hold_a_role_in_their_school(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    school, admin = await _school_with_admin(client, db_session)
    manager = await _make_actor(client)
    await _grant(db_session, manager.user_id, Role.EVENT_MANAGER, school.id)
    ordinary, _ = await _alum(client, db_session, school)  # alumni are not "members" here

    r = await _get(client, admin, f"/organizations/{school.id}/members")

    assert r.status_code == 200, r.text
    assert {(m["user_id"], m["role"]) for m in r.json()} == {
        (str(admin.user_id), "school_admin"),
        (str(manager.user_id), "event_manager"),
    }
    assert str(ordinary.user_id) not in r.text
    assert r.headers["X-Total-Count"] == "2"
    first = r.json()[0]
    assert set(first) == {
        "membership_id", "user_id", "email", "full_name", "role", "status",
        "account_status", "since",
    }  # fmt: skip


async def test_a_members_list_never_contains_another_organizations_people(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    school_a, admin_a = await _school_with_admin(client, db_session)
    school_b, admin_b = await _school_with_admin(client, db_session)
    manager_b = await _make_actor(client)
    await _grant(db_session, manager_b.user_id, Role.EVENT_MANAGER, school_b.id)
    # A platform role has no organization at all and must not show up either.
    platform = await _make_actor(client)
    await _grant(db_session, platform.user_id, Role.MODERATOR, None)

    listing_a = await _get(client, admin_a, f"/organizations/{school_a.id}/members")

    assert listing_a.status_code == 200
    ids = {m["user_id"] for m in listing_a.json()}
    assert ids == {str(admin_a.user_id)}
    for outsider in (admin_b, manager_b, platform):
        assert str(outsider.user_id) not in listing_a.text


async def test_a_school_admin_cannot_list_another_schools_members(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _, admin_a = await _school_with_admin(client, db_session)
    school_b, admin_b = await _school_with_admin(client, db_session)

    r = await _get(client, admin_a, f"/organizations/{school_b.id}/members")

    assert r.status_code == 403
    assert str(admin_b.user_id) not in r.text
    assert "X-Total-Count" not in r.headers


async def test_who_may_open_the_members_list(client: AsyncClient, db_session: AsyncSession) -> None:
    school, _ = await _school_with_admin(client, db_session)
    partner = Organization(
        type=OrganizationType.PARTNER, name="p", slug=f"p-{uuid.uuid4().hex[:8]}"
    )
    db_session.add(partner)
    await db_session.flush()
    partner_admin = await _make_actor(client)
    await _grant(db_session, partner_admin.user_id, Role.PARTNER_ADMIN, partner.id)
    manager = await _make_actor(client)
    await _grant(db_session, manager.user_id, Role.EVENT_MANAGER, school.id)
    alum, _ = await _alum(client, db_session, school)
    platform_admin = await _make_actor(client)
    await _grant(db_session, platform_admin.user_id, Role.ADMIN, None)
    moderator = await _make_actor(client)
    await _grant(db_session, moderator.user_id, Role.MODERATOR, None)

    path = f"/organizations/{school.id}/members"
    assert (await _get(client, platform_admin, path)).status_code == 200
    assert (await _get(client, partner_admin, path)).status_code == 403
    for refused in (manager, alum, moderator):
        assert (await _get(client, refused, path)).status_code == 403
    assert (await client.get(f"{API}{path}")).status_code == 401

    own = await _get(client, partner_admin, f"/organizations/{partner.id}/members")
    assert own.status_code == 200
    assert [m["user_id"] for m in own.json()] == [str(partner_admin.user_id)]


async def test_the_members_list_filters_by_role_and_hides_revoked_roles_by_default(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    school, admin = await _school_with_admin(client, db_session)
    manager = await _make_actor(client)
    sports = await _make_actor(client)
    await _grant(db_session, manager.user_id, Role.EVENT_MANAGER, school.id)
    await _grant(db_session, sports.user_id, Role.SPORTS_MANAGER, school.id)
    revoked = await db_session.scalar(
        select(Membership).where(Membership.user_id == sports.user_id)
    )
    assert revoked is not None
    revoked.status = MembershipStatus.REVOKED
    await db_session.flush()
    path = f"/organizations/{school.id}/members"

    default = await _get(client, admin, path)
    assert {m["role"] for m in default.json()} == {"school_admin", "event_manager"}

    only = await _get(client, admin, path, role="event_manager")
    assert [m["user_id"] for m in only.json()] == [str(manager.user_id)]
    assert only.headers["X-Total-Count"] == "1"

    everything = await _get(client, admin, path, include_revoked="true")
    assert {(m["role"], m["status"]) for m in everything.json()} >= {("sports_manager", "revoked")}


async def test_the_members_list_is_paged_with_a_total(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    school, admin = await _school_with_admin(client, db_session)
    for _ in range(4):
        person = await _make_actor(client)
        await _grant(db_session, person.user_id, Role.EVENT_MANAGER, school.id)
    path = f"/organizations/{school.id}/members"

    first = await _get(client, admin, path, limit=2, offset=0)
    second = await _get(client, admin, path, limit=2, offset=2)
    last = await _get(client, admin, path, limit=2, offset=4)

    assert first.headers["X-Total-Count"] == "5"
    seen = [m["membership_id"] for r in (first, second, last) for m in r.json()]
    assert len(seen) == 5 and len(set(seen)) == 5
    assert len(last.json()) == 1


# ---------------------------------------------------------------------------- roster


async def test_the_roster_lists_only_this_schools_alumni(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    school_a, admin_a = await _school_with_admin(client, db_session)
    school_b, _ = await _school_with_admin(client, db_session)
    mine, _ = await _alum(client, db_session, school_a, name="Alice Mine")
    theirs, _ = await _alum(client, db_session, school_b, name="Bob Theirs")

    r = await _get(client, admin_a, f"/organizations/{school_a.id}/roster")

    assert r.status_code == 200, r.text
    assert [row["user_id"] for row in r.json()] == [str(mine.user_id)]
    assert str(theirs.user_id) not in r.text
    assert "Bob Theirs" not in r.text
    assert r.headers["X-Total-Count"] == "1"


async def test_a_school_admin_cannot_read_another_schools_roster(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _, admin_a = await _school_with_admin(client, db_session)
    school_b, _ = await _school_with_admin(client, db_session)
    theirs, _ = await _alum(client, db_session, school_b, name="Bob Theirs")

    r = await _get(client, admin_a, f"/organizations/{school_b.id}/roster")
    filtered = await _get(
        client, admin_a, f"/organizations/{school_b.id}/roster", verification="unverified"
    )

    for refused in (r, filtered):
        assert refused.status_code == 403
        assert "Bob Theirs" not in refused.text
        assert str(theirs.user_id) not in refused.text


async def test_the_waiting_for_verification_filter(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    school, admin = await _school_with_admin(client, db_session)
    waiting, _ = await _alum(client, db_session, school, name="Waiting One")
    done, _ = await _alum(client, db_session, school, name="Done One", verified=True)
    path = f"/organizations/{school.id}/roster"

    unverified = await _get(client, admin, path, verification="unverified")
    verified = await _get(client, admin, path, verification="verified")
    everyone = await _get(client, admin, path)

    assert [r["user_id"] for r in unverified.json()] == [str(waiting.user_id)]
    assert unverified.headers["X-Total-Count"] == "1"
    assert [r["user_id"] for r in verified.json()] == [str(done.user_id)]
    assert verified.json()[0]["verification_method"] == "admin"
    assert len(everyone.json()) == 2
    assert everyone.headers["X-Total-Count"] == "2"


async def test_the_roster_filters_by_graduation_year_and_pages(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    school, admin = await _school_with_admin(client, db_session)
    for name, year in (("A One", 2010), ("B Two", 2010), ("C Three", 2011)):
        await _alum(client, db_session, school, name=name, year=year)
    path = f"/organizations/{school.id}/roster"

    year_2010 = await _get(client, admin, path, graduation_year=2010)
    assert [r["full_name"] for r in year_2010.json()] == ["A One", "B Two"]

    page = await _get(client, admin, path, limit=2, offset=2)
    assert [r["full_name"] for r in page.json()] == ["C Three"]
    assert page.headers["X-Total-Count"] == "3"


async def test_the_roster_shows_a_private_profile_but_only_the_fields_needed_to_verify(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    school, admin = await _school_with_admin(client, db_session)
    hidden, _ = await _alum(
        client, db_session, school, name="Very Private", visibility=ProfileVisibility.PRIVATE
    )

    r = await _get(client, admin, f"/organizations/{school.id}/roster")

    row = r.json()[0]
    assert row["user_id"] == str(hidden.user_id)
    assert set(row) == {
        "profile_id", "user_id", "full_name", "graduation_year", "country",
        "verification_status", "verification_method", "email_verified", "joined_at",
    }  # fmt: skip
    for secret in ("Secret Corp", "Engineer", "@example.com"):
        assert secret not in r.text


async def test_suspended_accounts_are_left_out_of_the_roster(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    school, admin = await _school_with_admin(client, db_session)
    gone, _ = await _alum(client, db_session, school, name="Suspended Sam")
    user = await db_session.get(User, gone.user_id)
    assert user is not None
    user.status = UserStatus.SUSPENDED
    await db_session.flush()

    r = await _get(client, admin, f"/organizations/{school.id}/roster")

    assert r.json() == []
    assert r.headers["X-Total-Count"] == "0"


async def test_who_may_open_the_roster(client: AsyncClient, db_session: AsyncSession) -> None:
    school, _ = await _school_with_admin(client, db_session)
    manager = await _make_actor(client)
    await _grant(db_session, manager.user_id, Role.EVENT_MANAGER, school.id)
    alum, _ = await _alum(client, db_session, school)
    platform_admin = await _make_actor(client)
    await _grant(db_session, platform_admin.user_id, Role.ADMIN, None)
    moderator = await _make_actor(client)
    await _grant(db_session, moderator.user_id, Role.MODERATOR, None)
    path = f"/organizations/{school.id}/roster"

    assert (await _get(client, platform_admin, path)).status_code == 200
    for refused in (manager, alum, moderator):
        r: Response = await _get(client, refused, path)
        assert r.status_code == 403, (refused.user_id, r.text)
    assert (await client.get(f"{API}{path}")).status_code == 401


async def test_a_partner_has_no_roster(client: AsyncClient, db_session: AsyncSession) -> None:
    partner = Organization(
        type=OrganizationType.PARTNER, name="p", slug=f"p-{uuid.uuid4().hex[:8]}"
    )
    db_session.add(partner)
    await db_session.flush()
    platform_admin = await _make_actor(client)
    await _grant(db_session, platform_admin.user_id, Role.ADMIN, None)

    r = await _get(client, platform_admin, f"/organizations/{partner.id}/roster")

    assert r.status_code == 422
