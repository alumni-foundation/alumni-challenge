import hashlib
import uuid

from httpx import AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions.roles import Role
from app.modules.audit.models import AuditLogEntry
from app.modules.identity.models import User, UserStatus
from app.modules.organizations.lookup import LOOKUP_LIMIT_PER_HOUR
from tests.test_alumni_privacy import Actor, _grant, _make_actor, _make_profile, _make_school

API = "/api/v1"


async def _email_of(db: AsyncSession, actor: Actor) -> str:
    email = await db.scalar(select(User.email).where(User.id == actor.user_id))
    assert email is not None
    return email


async def _lookup(client: AsyncClient, admin: Actor, org_id: uuid.UUID, email: str) -> Response:
    return await client.post(
        f"{API}/organizations/{org_id}/user-lookup", json={"email": email}, headers=admin.headers
    )


async def _school_with_admin(client: AsyncClient, db: AsyncSession):  # type: ignore[no-untyped-def]
    school = await _make_school(db)
    admin = await _make_actor(client)
    await _grant(db, admin.user_id, Role.SCHOOL_ADMIN, school.id)
    return school, admin


async def test_a_school_admin_finds_an_alumnus_of_their_own_school(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    school, admin = await _school_with_admin(client, db_session)
    alum = await _make_actor(client)
    await _make_profile(client, alum, school_id=school.id)

    r = await _lookup(client, admin, school.id, await _email_of(db_session, alum))

    assert r.status_code == 200, r.text
    match = r.json()["match"]
    assert match["user_id"] == str(alum.user_id)
    assert match["full_name"] == "Test Alum"
    assert match["verification_status"] == "unverified"
    assert "email" not in match
    assert "company" not in match


async def test_the_address_is_matched_ignoring_case_and_spaces(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    school, admin = await _school_with_admin(client, db_session)
    alum = await _make_actor(client)
    await _make_profile(client, alum, school_id=school.id)

    r = await _lookup(client, admin, school.id, f"  {(await _email_of(db_session, alum)).upper()} ")

    assert r.json()["match"]["user_id"] == str(alum.user_id)


async def test_a_member_with_a_role_but_no_profile_is_found(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    school, admin = await _school_with_admin(client, db_session)
    manager = await _make_actor(client)
    await _grant(db_session, manager.user_id, Role.EVENT_MANAGER, school.id)

    r = await _lookup(client, admin, school.id, await _email_of(db_session, manager))

    match = r.json()["match"]
    assert match["roles_in_organization"] == ["event_manager"]
    assert match["full_name"] is None


async def test_someone_who_belongs_elsewhere_looks_exactly_like_nobody(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    school_a, admin_a = await _school_with_admin(client, db_session)
    school_b = await _make_school(db_session)
    other = await _make_actor(client)
    await _make_profile(client, other, school_id=school_b.id)  # real account, other school
    no_school = await _make_actor(client)  # real account, no school at all

    elsewhere = await _lookup(client, admin_a, school_a.id, await _email_of(db_session, other))
    unaffiliated = await _lookup(
        client, admin_a, school_a.id, await _email_of(db_session, no_school)
    )
    nobody = await _lookup(client, admin_a, school_a.id, f"nobody-{uuid.uuid4().hex}@example.com")

    assert elsewhere.status_code == unaffiliated.status_code == nobody.status_code == 200
    assert elsewhere.json() == unaffiliated.json() == nobody.json() == {"match": None}
    assert elsewhere.content == nobody.content


async def test_a_suspended_account_is_not_found(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    school, admin = await _school_with_admin(client, db_session)
    alum = await _make_actor(client)
    await _make_profile(client, alum, school_id=school.id)
    user = await db_session.get(User, alum.user_id)
    assert user is not None
    user.status = UserStatus.SUSPENDED
    await db_session.flush()

    r = await _lookup(client, admin, school.id, user.email)

    assert r.json() == {"match": None}


async def test_a_school_admin_cannot_look_up_people_through_another_school(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    school_a, admin_a = await _school_with_admin(client, db_session)
    school_b = await _make_school(db_session)
    member_b = await _make_actor(client)
    await _make_profile(client, member_b, school_id=school_b.id)

    r = await _lookup(client, admin_a, school_b.id, await _email_of(db_session, member_b))

    assert r.status_code == 403
    assert "match" not in r.text
    assert school_a.id != school_b.id


async def test_ordinary_alumni_and_anonymous_callers_are_refused(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    school = await _make_school(db_session)
    alum = await _make_actor(client)

    refused = await _lookup(client, alum, school.id, "someone@example.com")
    anonymous = await client.post(
        f"{API}/organizations/{school.id}/user-lookup", json={"email": "someone@example.com"}
    )

    assert refused.status_code == 403
    assert anonymous.status_code == 401


async def test_a_platform_admin_can_look_up_members_of_any_organization(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    school = await _make_school(db_session)
    alum = await _make_actor(client)
    await _make_profile(client, alum, school_id=school.id)
    admin = await _make_actor(client)
    await _grant(db_session, admin.user_id, Role.ADMIN, None)

    r = await _lookup(client, admin, school.id, await _email_of(db_session, alum))

    assert r.json()["match"]["user_id"] == str(alum.user_id)


async def test_lookups_are_rate_limited_per_admin_whether_or_not_they_match(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    school, admin = await _school_with_admin(client, db_session)
    other_school, other_admin = await _school_with_admin(client, db_session)

    for i in range(LOOKUP_LIMIT_PER_HOUR):
        r = await _lookup(client, admin, school.id, f"nobody-{i}@example.com")
        assert r.status_code == 200, (i, r.text)

    blocked = await _lookup(client, admin, school.id, "nobody-extra@example.com")
    assert blocked.status_code == 429, blocked.text
    # The limit belongs to the admin who spent it, not to everyone.
    fine = await _lookup(client, other_admin, other_school.id, "nobody@example.com")
    assert fine.status_code == 200, fine.text


async def test_every_lookup_is_audited_without_storing_the_address(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    school, admin = await _school_with_admin(client, db_session)
    alum = await _make_actor(client)
    await _make_profile(client, alum, school_id=school.id)
    found_email = await _email_of(db_session, alum)
    missing_email = f"nobody-{uuid.uuid4().hex}@example.com"

    await _lookup(client, admin, school.id, found_email)
    await _lookup(client, admin, school.id, missing_email)

    rows = list(
        await db_session.scalars(
            select(AuditLogEntry)
            .where(AuditLogEntry.action == "organization.user_lookup")
            .where(AuditLogEntry.actor_user_id == admin.user_id)
        )
    )
    # Both rows share one transaction timestamp, so identify them by fingerprint, not order.
    by_fingerprint = {row.context["email_fingerprint"]: row for row in rows}
    found_fp = hashlib.sha256(found_email.lower().encode()).hexdigest()[:16]
    missing_fp = hashlib.sha256(missing_email.lower().encode()).hexdigest()[:16]
    assert set(by_fingerprint) == {found_fp, missing_fp}
    assert by_fingerprint[found_fp].context["matched"] is True
    assert by_fingerprint[missing_fp].context["matched"] is False
    assert all(row.target_id == school.id for row in rows)
    assert all(row.context["organization_id"] == str(school.id) for row in rows)
    stored = " ".join(str(row.context) for row in rows)
    assert found_email not in stored
    assert missing_email not in stored
