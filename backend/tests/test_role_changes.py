import asyncio
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.core.errors.exceptions import AppError, ConflictError, ForbiddenError
from app.core.permissions.roles import Role
from app.modules.audit.models import AuditLogEntry
from app.modules.identity.models import User
from app.modules.memberships import role_changes
from app.modules.memberships.models import Membership, MembershipStatus
from tests.test_alumni_privacy import Actor, _grant, _make_actor, _make_school

API = "/api/v1"
PASSWORD = "correct-horse-battery"


async def _actor_with(client: AsyncClient, db: AsyncSession, role: Role) -> Actor:
    actor = await _make_actor(client)
    await _grant(db, actor.user_id, role, None)
    return actor


def _grant_platform(client: AsyncClient, actor: Actor, target: Actor, role: Role) -> Any:
    return client.post(
        f"{API}/users/{target.user_id}/platform-roles",
        json={"role": role.value},
        headers=actor.headers,
    )


def _revoke_platform(client: AsyncClient, actor: Actor, target: Actor, role: Role) -> Any:
    return client.delete(
        f"{API}/users/{target.user_id}/platform-roles/{role.value}", headers=actor.headers
    )


async def _active_roles(db: AsyncSession, user_id: uuid.UUID) -> set[Role]:
    rows = await db.scalars(
        select(Membership.role).where(
            Membership.user_id == user_id, Membership.status == MembershipStatus.ACTIVE
        )
    )
    return set(rows)


# ------------------------------------------------------------ platform roles: the rank rule


async def test_a_super_admin_can_grant_every_platform_role(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    boss = await _actor_with(client, db_session, Role.SUPER_ADMIN)
    for role in (Role.ADMIN, Role.MODERATOR, Role.SUPER_ADMIN):
        target = await _make_actor(client)
        r = await _grant_platform(client, boss, target, role)
        assert r.status_code == 201, (role, r.text)
        assert await _active_roles(db_session, target.user_id) == {role}


async def test_an_admin_can_grant_moderator_and_nothing_higher(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    admin = await _actor_with(client, db_session, Role.ADMIN)
    person = await _make_actor(client)

    assert (await _grant_platform(client, admin, person, Role.MODERATOR)).status_code == 201
    for role in (Role.ADMIN, Role.SUPER_ADMIN):
        other = await _make_actor(client)
        r = await _grant_platform(client, admin, other, role)
        assert r.status_code == 403, (role, r.text)
        assert await _active_roles(db_session, other.user_id) == set()


async def test_an_admin_cannot_change_the_roles_of_another_admin(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    admin = await _actor_with(client, db_session, Role.ADMIN)
    peer = await _actor_with(client, db_session, Role.ADMIN)

    granted = await _grant_platform(client, admin, peer, Role.MODERATOR)
    revoked = await _revoke_platform(client, admin, peer, Role.ADMIN)

    assert granted.status_code == 403, granted.text
    assert revoked.status_code == 403, revoked.text
    assert await _active_roles(db_session, peer.user_id) == {Role.ADMIN}


async def test_moderators_alumni_and_anonymous_callers_cannot_change_platform_roles(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    moderator = await _actor_with(client, db_session, Role.MODERATOR)
    alum = await _make_actor(client)
    target = await _make_actor(client)

    for actor in (moderator, alum):
        assert (await _grant_platform(client, actor, target, Role.MODERATOR)).status_code == 403
        assert (await _revoke_platform(client, actor, target, Role.MODERATOR)).status_code == 403
    anonymous = await client.post(
        f"{API}/users/{target.user_id}/platform-roles", json={"role": "moderator"}
    )
    assert anonymous.status_code == 401
    assert await _active_roles(db_session, target.user_id) == set()


async def test_nobody_changes_their_own_roles_not_even_a_super_admin(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    boss = await _actor_with(client, db_session, Role.SUPER_ADMIN)
    admin = await _actor_with(client, db_session, Role.ADMIN)

    assert (await _grant_platform(client, boss, boss, Role.ADMIN)).status_code == 422
    assert (await _revoke_platform(client, boss, boss, Role.SUPER_ADMIN)).status_code == 422
    assert (await _grant_platform(client, admin, admin, Role.MODERATOR)).status_code == 422
    assert await _active_roles(db_session, boss.user_id) == {Role.SUPER_ADMIN}


async def test_revoking_removes_access_at_once_and_regranting_restores_it(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    boss = await _actor_with(client, db_session, Role.SUPER_ADMIN)
    admin = await _actor_with(client, db_session, Role.ADMIN)
    assert (await client.get(f"{API}/audit-log", headers=admin.headers)).status_code == 200

    assert (await _revoke_platform(client, boss, admin, Role.ADMIN)).status_code == 204
    assert (await client.get(f"{API}/audit-log", headers=admin.headers)).status_code == 403

    assert (await _grant_platform(client, boss, admin, Role.ADMIN)).status_code == 201
    assert (await client.get(f"{API}/audit-log", headers=admin.headers)).status_code == 200
    rows = await db_session.scalar(
        select(func.count())
        .select_from(Membership)
        .where(Membership.user_id == admin.user_id, Membership.role == Role.ADMIN)
    )
    assert rows == 1, "re-granting should reuse the revoked row, not add another"


async def test_granting_a_role_someone_already_holds_is_a_conflict(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    boss = await _actor_with(client, db_session, Role.SUPER_ADMIN)
    target = await _actor_with(client, db_session, Role.MODERATOR)

    assert (await _grant_platform(client, boss, target, Role.MODERATOR)).status_code == 409
    missing = await _make_actor(client)
    assert (await _revoke_platform(client, boss, missing, Role.MODERATOR)).status_code == 404


async def test_organization_roles_cannot_be_granted_through_the_platform_endpoint(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    boss = await _actor_with(client, db_session, Role.SUPER_ADMIN)
    target = await _make_actor(client)

    r = await _grant_platform(client, boss, target, Role.SCHOOL_ADMIN)

    assert r.status_code == 422
    assert await _active_roles(db_session, target.user_id) == set()


async def test_every_platform_role_change_is_audited(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    boss = await _actor_with(client, db_session, Role.SUPER_ADMIN)
    target = await _make_actor(client)

    await _grant_platform(client, boss, target, Role.MODERATOR)
    await _revoke_platform(client, boss, target, Role.MODERATOR)

    entries = list(
        await db_session.scalars(
            select(AuditLogEntry).where(
                AuditLogEntry.actor_user_id == boss.user_id,
                AuditLogEntry.action.in_(("membership.assign", "membership.revoke")),
            )
        )
    )
    by_action = {e.action: e for e in entries}
    assert set(by_action) == {"membership.assign", "membership.revoke"}
    for entry in entries:
        assert entry.context["role"] == "moderator"
        assert entry.context["target_user_id"] == str(target.user_id)
        assert entry.context["scope"] == "platform"


# ------------------------------------------------------------ the last super admin


async def test_an_admin_cannot_revoke_a_super_admin(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    admin = await _actor_with(client, db_session, Role.ADMIN)
    boss = await _actor_with(client, db_session, Role.SUPER_ADMIN)

    r = await _revoke_platform(client, admin, boss, Role.SUPER_ADMIN)

    assert r.status_code == 403
    assert Role.SUPER_ADMIN in await _active_roles(db_session, boss.user_id)


async def test_one_super_admin_can_revoke_another_and_one_always_remains(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    first = await _actor_with(client, db_session, Role.SUPER_ADMIN)
    second = await _actor_with(client, db_session, Role.SUPER_ADMIN)

    assert (await _revoke_platform(client, first, second, Role.SUPER_ADMIN)).status_code == 204

    assert Role.SUPER_ADMIN in await _active_roles(db_session, first.user_id)
    assert Role.SUPER_ADMIN not in await _active_roles(db_session, second.user_id)
    # The one left cannot remove themselves, and the one removed has no power left.
    assert (await _revoke_platform(client, first, first, Role.SUPER_ADMIN)).status_code == 422
    assert (await _revoke_platform(client, second, first, Role.SUPER_ADMIN)).status_code == 403


async def test_the_guard_itself_refuses_to_leave_no_super_admin(db_session: AsyncSession) -> None:
    sole = User(email=f"sole-{uuid.uuid4().hex[:8]}@example.com", password_hash="x")
    db_session.add(sole)
    await db_session.flush()
    await _grant(db_session, sole.id, Role.SUPER_ADMIN, None)

    with pytest.raises(ConflictError, match="last super admin"):
        await role_changes._lock_super_admins_and_check_one_remains(
            db_session, actor_id=sole.id, target_user_id=sole.id
        )


async def test_the_guard_needs_the_caller_to_still_be_a_super_admin(
    db_session: AsyncSession,
) -> None:
    holder = User(email=f"h-{uuid.uuid4().hex[:8]}@example.com", password_hash="x")
    other = User(email=f"o-{uuid.uuid4().hex[:8]}@example.com", password_hash="x")
    db_session.add_all([holder, other])
    await db_session.flush()
    await _grant(db_session, holder.id, Role.SUPER_ADMIN, None)

    with pytest.raises(ForbiddenError):
        await role_changes._lock_super_admins_and_check_one_remains(
            db_session, actor_id=other.id, target_user_id=holder.id
        )


@asynccontextmanager
async def _committing_session() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """Real, independent, committing sessions on the test database (the usual fixture is
    one shared transaction, which cannot show two callers racing)."""
    engine = create_async_engine(str(get_settings().database_url), poolclass=NullPool)
    try:
        yield async_sessionmaker(engine, expire_on_commit=False)
    finally:
        await engine.dispose()


async def test_two_super_admins_revoking_each_other_at_once_never_leave_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with _committing_session() as factory:
        async with factory() as setup:
            users = [
                User(email=f"race-{uuid.uuid4().hex[:8]}@example.com", password_hash="x")
                for _ in range(2)
            ]
            setup.add_all(users)
            await setup.flush()
            setup.add_all(
                Membership(user_id=u.id, organization_id=None, role=Role.SUPER_ADMIN) for u in users
            )
            await setup.commit()
            first_id, second_id = users[0].id, users[1].id

        # Hold both callers after they have read their rank, so both believe they are still
        # a super admin when they reach the revoke. Without locking, both would succeed.
        barrier = asyncio.Barrier(2)
        real_get_user_roles = role_changes.get_user_roles

        async def synchronised(db: AsyncSession, **kwargs: Any) -> set[Role]:
            roles = await real_get_user_roles(db, **kwargs)
            await barrier.wait()
            return roles

        monkeypatch.setattr(role_changes, "get_user_roles", synchronised)

        async def revoke(actor_id: uuid.UUID, target_id: uuid.UUID) -> AppError | None:
            async with factory() as session:
                actor = await session.get(User, actor_id)
                assert actor is not None
                try:
                    await role_changes.revoke_platform_role(
                        session, actor=actor, target_user_id=target_id, role=Role.SUPER_ADMIN
                    )
                    await session.commit()
                except AppError as exc:
                    await session.rollback()
                    return exc
                return None

        try:
            outcomes = await asyncio.wait_for(
                asyncio.gather(revoke(first_id, second_id), revoke(second_id, first_id)),
                timeout=30,
            )
            async with factory() as check:
                remaining = await check.scalar(
                    select(func.count())
                    .select_from(Membership)
                    .where(
                        Membership.user_id.in_((first_id, second_id)),
                        Membership.role == Role.SUPER_ADMIN,
                        Membership.status == MembershipStatus.ACTIVE,
                    )
                )
            assert remaining == 1, f"expected exactly one super admin left, got {remaining}"
            assert sum(o is None for o in outcomes) == 1, outcomes
        finally:
            async with factory() as cleanup:
                ids = (first_id, second_id)
                await cleanup.execute(
                    delete(AuditLogEntry).where(AuditLogEntry.actor_user_id.in_(ids))
                )
                await cleanup.execute(delete(User).where(User.id.in_(ids)))
                await cleanup.commit()


# ------------------------------------------------------------ organization roles


async def _school_with_admin(client: AsyncClient, db: AsyncSession) -> tuple[Any, Actor]:
    school = await _make_school(db)
    admin = await _make_actor(client)
    await _grant(db, admin.user_id, Role.SCHOOL_ADMIN, school.id)
    return school, admin


async def _membership_id(db: AsyncSession, user_id: uuid.UUID, role: Role) -> uuid.UUID:
    found = await db.scalar(
        select(Membership.id).where(Membership.user_id == user_id, Membership.role == role)
    )
    assert found is not None
    return found


def _revoke_org(client: AsyncClient, actor: Actor, org_id: uuid.UUID, membership_id: Any) -> Any:
    return client.delete(
        f"{API}/organizations/{org_id}/memberships/{membership_id}", headers=actor.headers
    )


async def test_a_school_admin_can_remove_their_own_managers(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    school, admin = await _school_with_admin(client, db_session)
    manager = await _make_actor(client)
    await _grant(db_session, manager.user_id, Role.EVENT_MANAGER, school.id)
    membership_id = await _membership_id(db_session, manager.user_id, Role.EVENT_MANAGER)

    r = await _revoke_org(client, admin, school.id, membership_id)

    assert r.status_code == 204, r.text
    assert await _active_roles(db_session, manager.user_id) == set()
    entry = await db_session.scalar(
        select(AuditLogEntry).where(
            AuditLogEntry.action == "membership.revoke",
            AuditLogEntry.actor_user_id == admin.user_id,
        )
    )
    assert entry is not None
    assert entry.context["organization_id"] == str(school.id)
    assert entry.context["role"] == "event_manager"
    # An org-scoped audit entry is visible to that school's own admin.
    visible = await client.get(f"{API}/audit-log", headers=admin.headers)
    assert "membership.revoke" in [e["action"] for e in visible.json()]


async def test_only_a_platform_admin_can_remove_an_organization_admin(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    school, admin = await _school_with_admin(client, db_session)
    colleague = await _make_actor(client)
    await _grant(db_session, colleague.user_id, Role.SCHOOL_ADMIN, school.id)
    membership_id = await _membership_id(db_session, colleague.user_id, Role.SCHOOL_ADMIN)

    refused = await _revoke_org(client, admin, school.id, membership_id)
    assert refused.status_code == 403, refused.text
    assert await _active_roles(db_session, colleague.user_id) == {Role.SCHOOL_ADMIN}

    platform = await _actor_with(client, db_session, Role.ADMIN)
    allowed = await _revoke_org(client, platform, school.id, membership_id)
    assert allowed.status_code == 204, allowed.text


async def test_a_school_admin_cannot_remove_anyone_from_another_school(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    school_a, admin_a = await _school_with_admin(client, db_session)
    school_b = await _make_school(db_session)
    manager_b = await _make_actor(client)
    await _grant(db_session, manager_b.user_id, Role.EVENT_MANAGER, school_b.id)
    membership_b = await _membership_id(db_session, manager_b.user_id, Role.EVENT_MANAGER)

    through_b = await _revoke_org(client, admin_a, school_b.id, membership_b)
    through_a = await _revoke_org(client, admin_a, school_a.id, membership_b)

    assert through_b.status_code == 403, through_b.text
    assert through_a.status_code == 404, through_a.text
    assert await _active_roles(db_session, manager_b.user_id) == {Role.EVENT_MANAGER}


async def test_nobody_can_remove_their_own_organization_role(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    school, admin = await _school_with_admin(client, db_session)
    own = await _membership_id(db_session, admin.user_id, Role.SCHOOL_ADMIN)

    r = await _revoke_org(client, admin, school.id, own)

    assert r.status_code == 422
    assert await _active_roles(db_session, admin.user_id) == {Role.SCHOOL_ADMIN}


async def test_a_manager_cannot_remove_other_people(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    school, _ = await _school_with_admin(client, db_session)
    manager = await _make_actor(client)
    peer = await _make_actor(client)
    await _grant(db_session, manager.user_id, Role.EVENT_MANAGER, school.id)
    await _grant(db_session, peer.user_id, Role.SPORTS_MANAGER, school.id)
    peer_membership = await _membership_id(db_session, peer.user_id, Role.SPORTS_MANAGER)

    r = await _revoke_org(client, manager, school.id, peer_membership)

    assert r.status_code == 403


async def test_removing_a_role_twice_is_not_found(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    school, admin = await _school_with_admin(client, db_session)
    manager = await _make_actor(client)
    await _grant(db_session, manager.user_id, Role.SPORTS_MANAGER, school.id)
    membership_id = await _membership_id(db_session, manager.user_id, Role.SPORTS_MANAGER)

    assert (await _revoke_org(client, admin, school.id, membership_id)).status_code == 204
    assert (await _revoke_org(client, admin, school.id, membership_id)).status_code == 404


async def test_nobody_can_grant_themselves_an_organization_role(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    school, admin = await _school_with_admin(client, db_session)

    r = await client.post(
        f"{API}/organizations/{school.id}/memberships",
        json={"user_id": str(admin.user_id), "role": "event_manager"},
        headers=admin.headers,
    )

    assert r.status_code == 422, r.text
    assert await _active_roles(db_session, admin.user_id) == {Role.SCHOOL_ADMIN}
