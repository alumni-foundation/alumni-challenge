"""Admin tools: remove a school email domain, and the admin users list."""

import uuid

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions.roles import Role
from app.modules.alumni.models import SchoolEmailDomain
from app.modules.audit.models import AuditLogEntry
from app.modules.identity.models import User, UserStatus
from tests.test_alumni_privacy import _grant, _make_actor, _make_school

API = "/api/v1"


# ---------------------------------------------------------------- remove an email domain


async def _add_domain(client: AsyncClient, school_id: uuid.UUID, headers: dict[str, str]) -> dict:
    domain = f"d{uuid.uuid4().hex[:8]}.ac.ke"
    r = await client.post(
        f"{API}/organizations/{school_id}/email-domains", json={"domain": domain}, headers=headers
    )
    assert r.status_code == 201, r.text
    return r.json()


async def test_school_admin_removes_own_domain_and_it_is_audited(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    school = await _make_school(db_session)
    admin = await _make_actor(client)
    await _grant(db_session, admin.user_id, Role.SCHOOL_ADMIN, school.id)
    row = await _add_domain(client, school.id, admin.headers)
    url = f"{API}/organizations/{school.id}/email-domains/{row['id']}"

    r = await client.delete(url, headers=admin.headers)
    assert r.status_code == 204
    assert r.content == b""

    listed = await client.get(
        f"{API}/organizations/{school.id}/email-domains", headers=admin.headers
    )
    assert listed.json() == []
    assert await db_session.get(SchoolEmailDomain, uuid.UUID(row["id"])) is None

    entry = await db_session.scalar(
        select(AuditLogEntry).where(
            AuditLogEntry.actor_user_id == admin.user_id,
            AuditLogEntry.action == "organization.email_domain.remove",
        )
    )
    assert entry is not None
    assert entry.target_id == uuid.UUID(row["id"])
    assert entry.context == {"organization_id": str(school.id), "domain": row["domain"]}

    # Gone is gone: a second delete is a 404, and the domain can be registered again.
    assert (await client.delete(url, headers=admin.headers)).status_code == 404
    again = await client.post(
        f"{API}/organizations/{school.id}/email-domains",
        json={"domain": row["domain"]},
        headers=admin.headers,
    )
    assert again.status_code == 201


async def test_platform_admin_removes_any_schools_domain(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    school = await _make_school(db_session)
    owner = await _make_actor(client)
    await _grant(db_session, owner.user_id, Role.SCHOOL_ADMIN, school.id)
    row = await _add_domain(client, school.id, owner.headers)
    boss = await _make_actor(client)
    await _grant(db_session, boss.user_id, Role.ADMIN, None)

    r = await client.delete(
        f"{API}/organizations/{school.id}/email-domains/{row['id']}", headers=boss.headers
    )
    assert r.status_code == 204


async def test_remove_email_domain_permissions_and_wrong_organization(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    school = await _make_school(db_session)
    other_school = await _make_school(db_session)
    admin = await _make_actor(client)
    other_admin = await _make_actor(client)
    stranger = await _make_actor(client)
    boss = await _make_actor(client)
    await _grant(db_session, admin.user_id, Role.SCHOOL_ADMIN, school.id)
    await _grant(db_session, other_admin.user_id, Role.SCHOOL_ADMIN, other_school.id)
    await _grant(db_session, boss.user_id, Role.ADMIN, None)
    row = await _add_domain(client, school.id, admin.headers)
    url = f"{API}/organizations/{school.id}/email-domains/{row['id']}"

    # Another school's admin, an ordinary user and an anonymous caller are all refused.
    assert (await client.delete(url, headers=other_admin.headers)).status_code == 403
    assert (await client.delete(url, headers=stranger.headers)).status_code == 403
    assert (await client.delete(url)).status_code == 401

    # A domain that belongs to a different organization is a 404, even for a platform admin
    # and even for the admin of the organization named in the URL. Nothing is deleted.
    wrong = f"{API}/organizations/{other_school.id}/email-domains/{row['id']}"
    assert (await client.delete(wrong, headers=boss.headers)).status_code == 404
    assert (await client.delete(wrong, headers=other_admin.headers)).status_code == 404
    unknown = f"{API}/organizations/{school.id}/email-domains/{uuid.uuid4()}"
    assert (await client.delete(unknown, headers=admin.headers)).status_code == 404
    assert await db_session.get(SchoolEmailDomain, uuid.UUID(row["id"])) is not None


# ---------------------------------------------------------------- admin users list


async def _named_user(client: AsyncClient, db: AsyncSession, name: str, tag: str) -> uuid.UUID:
    """A registered user with an alumni profile called `name`, email containing `tag`."""
    actor = await _make_actor(client)
    user = await db.get(User, actor.user_id)
    assert user is not None
    user.email = f"{tag}-{uuid.uuid4().hex[:6]}@example.com"
    await db.flush()
    r = await client.post(
        f"{API}/alumni/profile",
        json={"full_name": name, "profession": "Engineer", "country": "Kenya"},
        headers=actor.headers,
    )
    assert r.status_code == 201, r.text
    return actor.user_id


async def test_users_list_is_for_platform_admins_only(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    school = await _make_school(db_session)
    ordinary = await _make_actor(client)
    moderator = await _make_actor(client)
    school_admin = await _make_actor(client)
    admin = await _make_actor(client)
    super_admin = await _make_actor(client)
    await _grant(db_session, moderator.user_id, Role.MODERATOR, None)
    await _grant(db_session, school_admin.user_id, Role.SCHOOL_ADMIN, school.id)
    await _grant(db_session, admin.user_id, Role.ADMIN, None)
    await _grant(db_session, super_admin.user_id, Role.SUPER_ADMIN, None)

    assert (await client.get(f"{API}/users")).status_code == 401
    for actor in (ordinary, moderator, school_admin):
        assert (await client.get(f"{API}/users", headers=actor.headers)).status_code == 403
    for actor in (admin, super_admin):
        ok = await client.get(f"{API}/users", headers=actor.headers)
        assert ok.status_code == 200
        assert int(ok.headers["X-Total-Count"]) >= 5


async def test_users_list_items_search_and_filters(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tag = f"ul{uuid.uuid4().hex[:6]}"
    boss = await _make_actor(client)
    await _grant(db_session, boss.user_id, Role.SUPER_ADMIN, None)
    school = await _make_school(db_session)
    ada_id = await _named_user(client, db_session, "Ada Lovelace", tag)
    bob_id = await _named_user(client, db_session, "Bob Builder", tag)
    gone_id = await _named_user(client, db_session, "Gone Person", tag)
    await _grant(db_session, ada_id, Role.MODERATOR, None)
    await _grant(db_session, ada_id, Role.SCHOOL_ADMIN, school.id)
    bob = await db_session.get(User, bob_id)
    gone = await db_session.get(User, gone_id)
    assert bob is not None and gone is not None
    bob.status = UserStatus.SUSPENDED
    gone.status = UserStatus.DELETED
    await db_session.flush()

    r = await client.get(f"{API}/users", params={"q": tag}, headers=boss.headers)
    assert r.status_code == 200
    rows = {row["id"]: row for row in r.json()}
    assert set(rows) == {str(ada_id), str(bob_id)}  # the deleted account is never listed
    assert r.headers["X-Total-Count"] == "2"

    ada = rows[str(ada_id)]
    assert set(ada) == {"id", "email", "full_name", "status", "roles", "created_at"}
    assert ada["full_name"] == "Ada Lovelace"
    assert ada["status"] == "active"
    assert ada["roles"] == ["moderator", "school_admin"]
    assert rows[str(bob_id)]["status"] == "suspended"
    assert rows[str(bob_id)]["roles"] == []

    # Search matches the name too, case-insensitively, and treats % and _ as plain text.
    by_name = await client.get(f"{API}/users", params={"q": "lovelace"}, headers=boss.headers)
    assert str(ada_id) in {row["id"] for row in by_name.json()}
    wildcard = await client.get(f"{API}/users", params={"q": f"{tag[:2]}%"}, headers=boss.headers)
    assert wildcard.json() == []

    # Status filter.
    only_suspended = await client.get(
        f"{API}/users", params={"q": tag, "status": "suspended"}, headers=boss.headers
    )
    assert [row["id"] for row in only_suspended.json()] == [str(bob_id)]
    only_active = await client.get(
        f"{API}/users", params={"q": tag, "status": "active"}, headers=boss.headers
    )
    assert [row["id"] for row in only_active.json()] == [str(ada_id)]
    assert (
        await client.get(f"{API}/users", params={"status": "deleted"}, headers=boss.headers)
    ).status_code == 422

    # Revoked roles are not shown.
    from app.modules.memberships.models import Membership, MembershipStatus

    moderator_row = await db_session.scalar(
        select(Membership).where(Membership.user_id == ada_id, Membership.role == Role.MODERATOR)
    )
    assert moderator_row is not None
    moderator_row.status = MembershipStatus.REVOKED
    await db_session.flush()
    again = await client.get(f"{API}/users", params={"q": "lovelace"}, headers=boss.headers)
    mine = next(row for row in again.json() if row["id"] == str(ada_id))
    assert mine["roles"] == ["school_admin"]


async def test_users_list_paging_and_limit_cap(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    tag = f"pg{uuid.uuid4().hex[:6]}"
    boss = await _make_actor(client)
    await _grant(db_session, boss.user_id, Role.ADMIN, None)
    for n in range(3):
        await _named_user(client, db_session, f"Pager {n}", tag)

    first = await client.get(
        f"{API}/users", params={"q": tag, "limit": 2, "offset": 0}, headers=boss.headers
    )
    second = await client.get(
        f"{API}/users", params={"q": tag, "limit": 2, "offset": 2}, headers=boss.headers
    )
    assert len(first.json()) == 2 and len(second.json()) == 1
    assert first.headers["X-Total-Count"] == second.headers["X-Total-Count"] == "3"
    ids = [row["id"] for row in first.json() + second.json()]
    assert len(set(ids)) == 3

    for bad in ({"limit": 101}, {"limit": 0}, {"offset": -1}):
        r = await client.get(f"{API}/users", params=bad, headers=boss.headers)
        assert r.status_code == 422
