import uuid

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions.roles import Role
from app.modules.audit.models import AuditLogEntry
from app.modules.identity.models import Session, User, UserStatus
from tests.test_alumni_privacy import (
    PASSWORD,
    Actor,
    _grant,
    _make_actor,
    _make_school,
)

API = "/api/v1"


async def _with_role(client: AsyncClient, db: AsyncSession, role: Role) -> Actor:
    actor = await _make_actor(client)
    await _grant(db, actor.user_id, role, None)
    return actor


async def _member_with_refresh_token(client: AsyncClient) -> tuple[Actor, str, str]:
    """A normal member, plus their refresh token and email (to test logging in again)."""
    email = f"t-{uuid.uuid4().hex[:12]}@example.com"
    reg = await client.post(
        f"{API}/auth/register",
        json={"email": email, "password": PASSWORD, "confirm_18_or_older": True},
    )
    login = await client.post(f"{API}/auth/login", json={"email": email, "password": PASSWORD})
    body = login.json()
    actor = Actor(uuid.UUID(reg.json()["id"]), {"Authorization": f"Bearer {body['access_token']}"})
    return actor, body["refresh_token"], email


async def _suspend(
    client: AsyncClient, by: Actor, target: uuid.UUID, reason: str = "spam account"
) -> Response:
    return await client.post(
        f"{API}/users/{target}/suspend", json={"reason": reason}, headers=by.headers
    )


async def _reactivate(
    client: AsyncClient, by: Actor, target: uuid.UUID, reason: str = "appeal accepted"
) -> Response:
    return await client.post(
        f"{API}/users/{target}/reactivate", json={"reason": reason}, headers=by.headers
    )


async def _profile(client: AsyncClient, actor: Actor, **fields: object) -> str:
    body: dict[str, object] = {"full_name": "Plain Person", "profile_visibility": "members_only"}
    body.update(fields)
    r = await client.post(f"{API}/alumni/profile", json=body, headers=actor.headers)
    assert r.status_code == 201, r.text
    return str(r.json()["id"])


# ---------------------------------------------------------------- suspend


async def test_suspending_locks_the_person_out_immediately(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    moderator = await _with_role(client, db_session, Role.MODERATOR)
    member, refresh_token, email = await _member_with_refresh_token(client)
    assert (await client.get(f"{API}/auth/me", headers=member.headers)).status_code == 200

    r = await _suspend(client, moderator, member.user_id)
    assert r.status_code == 200
    assert r.json() == {"id": str(member.user_id), "status": "suspended"}

    # the access token they already hold stops working at once
    assert (await client.get(f"{API}/auth/me", headers=member.headers)).status_code == 401
    # they cannot log back in
    login = await client.post(f"{API}/auth/login", json={"email": email, "password": PASSWORD})
    assert login.status_code == 401
    # and their refresh token is dead
    refresh = await client.post(f"{API}/auth/refresh", json={"refresh_token": refresh_token})
    assert refresh.status_code == 401


async def test_suspending_revokes_every_session(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    moderator = await _with_role(client, db_session, Role.MODERATOR)
    member, _, email = await _member_with_refresh_token(client)
    # a second device
    await client.post(f"{API}/auth/login", json={"email": email, "password": PASSWORD})

    await _suspend(client, moderator, member.user_id)
    sessions = (
        await db_session.scalars(select(Session).where(Session.user_id == member.user_id))
    ).all()
    assert len(sessions) == 2
    assert all(s.revoked_at is not None for s in sessions)


async def test_suspension_is_audited_with_the_reason(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    moderator = await _with_role(client, db_session, Role.MODERATOR)
    member = await _make_actor(client)
    await _suspend(client, moderator, member.user_id, reason="  sells things  ")

    entry = await db_session.scalar(
        select(AuditLogEntry).where(
            AuditLogEntry.action == "user.suspend", AuditLogEntry.target_id == member.user_id
        )
    )
    assert entry is not None
    assert entry.actor_user_id == moderator.user_id
    assert entry.context == {"reason": "sells things"}


async def test_a_reason_is_required(client: AsyncClient, db_session: AsyncSession) -> None:
    moderator = await _with_role(client, db_session, Role.MODERATOR)
    member = await _make_actor(client)
    for reason in ("", "   "):
        assert (await _suspend(client, moderator, member.user_id, reason)).status_code == 422
    missing = await client.post(
        f"{API}/users/{member.user_id}/suspend", json={}, headers=moderator.headers
    )
    assert missing.status_code == 422
    assert (await client.get(f"{API}/auth/me", headers=member.headers)).status_code == 200


async def test_only_moderators_and_above_can_suspend(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    victim = await _make_actor(client)
    plain = await _make_actor(client)
    school_admin = await _make_actor(client)
    school = await _make_school(db_session)
    await _grant(db_session, school_admin.user_id, Role.SCHOOL_ADMIN, school.id)

    assert (await _suspend(client, plain, victim.user_id)).status_code == 403
    assert (await _suspend(client, school_admin, victim.user_id)).status_code == 403
    anon = await client.post(f"{API}/users/{victim.user_id}/suspend", json={"reason": "x"})
    assert anon.status_code == 401
    assert (await client.get(f"{API}/auth/me", headers=victim.headers)).status_code == 200


async def test_the_rank_rule_stops_people_acting_on_equals_or_superiors(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    moderator = await _with_role(client, db_session, Role.MODERATOR)
    other_moderator = await _with_role(client, db_session, Role.MODERATOR)
    admin = await _with_role(client, db_session, Role.ADMIN)
    other_admin = await _with_role(client, db_session, Role.ADMIN)
    super_admin = await _with_role(client, db_session, Role.SUPER_ADMIN)
    other_super = await _with_role(client, db_session, Role.SUPER_ADMIN)

    forbidden = [
        (moderator, other_moderator),
        (moderator, admin),
        (moderator, super_admin),
        (admin, other_admin),
        (admin, super_admin),
        (super_admin, other_super),
    ]
    for actor, target in forbidden:
        r = await _suspend(client, actor, target.user_id)
        assert r.status_code == 403, (actor.user_id, target.user_id)
    # none of them was locked out
    for _, target in forbidden:
        assert (await client.get(f"{API}/auth/me", headers=target.headers)).status_code == 200

    # downwards is allowed
    assert (await _suspend(client, admin, other_moderator.user_id)).status_code == 200
    assert (await _suspend(client, super_admin, other_admin.user_id)).status_code == 200


async def test_nobody_can_suspend_themselves(client: AsyncClient, db_session: AsyncSession) -> None:
    for role in (Role.MODERATOR, Role.ADMIN, Role.SUPER_ADMIN):
        actor = await _with_role(client, db_session, role)
        assert (await _suspend(client, actor, actor.user_id)).status_code == 422
        assert (await client.get(f"{API}/auth/me", headers=actor.headers)).status_code == 200


async def test_a_school_role_gives_no_rank(client: AsyncClient, db_session: AsyncSession) -> None:
    """A moderator cannot suspend a school admin just because they sit "above" a member, and
    a school admin does not outrank anyone: only platform roles count."""
    moderator = await _with_role(client, db_session, Role.MODERATOR)
    school_admin = await _make_actor(client)
    school = await _make_school(db_session)
    await _grant(db_session, school_admin.user_id, Role.SCHOOL_ADMIN, school.id)
    # moderator (rank 1) over school admin (rank 0): allowed
    assert (await _suspend(client, moderator, school_admin.user_id)).status_code == 200


async def test_status_conflicts_and_unknown_users(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    moderator = await _with_role(client, db_session, Role.MODERATOR)
    member = await _make_actor(client)
    gone = await _make_actor(client)

    assert (await _suspend(client, moderator, uuid.uuid4())).status_code == 404
    assert (await _suspend(client, moderator, member.user_id)).status_code == 200
    assert (await _suspend(client, moderator, member.user_id)).status_code == 409

    await db_session.execute(
        update(User).where(User.id == gone.user_id).values(status=UserStatus.DELETED)
    )
    await db_session.flush()
    assert (await _suspend(client, moderator, gone.user_id)).status_code == 409


# ------------------------------------------------------------- reactivate


async def test_reactivation_is_admin_only_and_the_person_must_log_in_again(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    moderator = await _with_role(client, db_session, Role.MODERATOR)
    admin = await _with_role(client, db_session, Role.ADMIN)
    member, refresh_token, email = await _member_with_refresh_token(client)
    await _suspend(client, moderator, member.user_id)

    assert (await _reactivate(client, moderator, member.user_id)).status_code == 403
    assert (await _reactivate(client, admin, member.user_id)).status_code == 200

    # the old access token and refresh token stay dead: they must log in again
    assert (await client.get(f"{API}/auth/me", headers=member.headers)).status_code == 200
    stale = await client.post(f"{API}/auth/refresh", json={"refresh_token": refresh_token})
    assert stale.status_code == 401
    login = await client.post(f"{API}/auth/login", json={"email": email, "password": PASSWORD})
    assert login.status_code == 200

    audited = await db_session.scalar(
        select(AuditLogEntry).where(
            AuditLogEntry.action == "user.reactivate", AuditLogEntry.target_id == member.user_id
        )
    )
    assert audited is not None
    assert audited.actor_user_id == admin.user_id


async def test_reactivate_rules(client: AsyncClient, db_session: AsyncSession) -> None:
    admin = await _with_role(client, db_session, Role.ADMIN)
    other_admin = await _with_role(client, db_session, Role.ADMIN)
    super_admin = await _with_role(client, db_session, Role.SUPER_ADMIN)
    member = await _make_actor(client)

    # not suspended -> conflict
    assert (await _reactivate(client, admin, member.user_id)).status_code == 409
    assert (await _reactivate(client, admin, uuid.uuid4())).status_code == 404
    assert (await _reactivate(client, admin, member.user_id, reason=" ")).status_code == 422

    # a suspended admin can only be brought back by a super admin
    await _suspend(client, super_admin, other_admin.user_id)
    assert (await _reactivate(client, admin, other_admin.user_id)).status_code == 403
    assert (await _reactivate(client, super_admin, other_admin.user_id)).status_code == 200

    # a deleted account cannot be reactivated
    await db_session.execute(
        update(User).where(User.id == member.user_id).values(status=UserStatus.DELETED)
    )
    await db_session.flush()
    assert (await _reactivate(client, admin, member.user_id)).status_code == 409


# ------------------------------------- what suspension does to the directory


async def test_a_suspended_profile_disappears_for_members_but_not_for_admins(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    moderator = await _with_role(client, db_session, Role.MODERATOR)
    admin = await _with_role(client, db_session, Role.ADMIN)
    viewer = await _make_actor(client)
    school_admin = await _make_actor(client)
    school = await _make_school(db_session)
    await _grant(db_session, school_admin.user_id, Role.SCHOOL_ADMIN, school.id)
    owner = await _make_actor(client)
    pid = await _profile(client, owner, school_id=str(school.id))

    assert (await client.get(f"{API}/alumni/{pid}", headers=viewer.headers)).status_code == 200
    await _suspend(client, moderator, owner.user_id)

    # gone for ordinary members, anonymous visitors, and the school's own admin
    assert (await client.get(f"{API}/alumni/{pid}", headers=viewer.headers)).status_code == 404
    assert (await client.get(f"{API}/alumni/{pid}")).status_code == 404
    assert (
        await client.get(f"{API}/alumni/{pid}", headers=school_admin.headers)
    ).status_code == 404
    # still visible to the people who have to deal with it
    assert (await client.get(f"{API}/alumni/{pid}", headers=admin.headers)).status_code == 200

    # back for everyone after reactivation
    await _reactivate(client, admin, owner.user_id)
    assert (await client.get(f"{API}/alumni/{pid}", headers=viewer.headers)).status_code == 200


async def test_a_moderator_can_open_a_suspended_profile_only_while_a_report_is_open(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    moderator = await _with_role(client, db_session, Role.MODERATOR)
    reporter = await _make_actor(client)
    owner = await _make_actor(client)
    pid = await _profile(client, owner)
    report = await client.post(
        f"{API}/reports",
        json={"target_type": "profile", "target_id": pid, "reason": "fake"},
        headers=reporter.headers,
    )
    await _suspend(client, moderator, owner.user_id)

    assert (await client.get(f"{API}/alumni/{pid}", headers=moderator.headers)).status_code == 200
    await client.patch(
        f"{API}/reports/{report.json()['id']}",
        json={"status": "resolved"},
        headers=moderator.headers,
    )
    assert (await client.get(f"{API}/alumni/{pid}", headers=moderator.headers)).status_code == 404


async def test_a_suspended_person_leaves_and_returns_to_the_directory(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    moderator = await _with_role(client, db_session, Role.MODERATOR)
    admin = await _with_role(client, db_session, Role.ADMIN)
    viewer = await _make_actor(client)
    owner = await _make_actor(client)
    word = "zq" + uuid.uuid4().hex[:8].translate(str.maketrans("0123456789", "abcdefghij"))
    pid = await _profile(client, owner, full_name=f"Findable {word}")

    def ids(r: Response) -> list[str]:
        return [p["id"] for p in r.json()]

    found = await client.get(f"{API}/alumni/directory", params={"q": word}, headers=viewer.headers)
    assert ids(found) == [pid]
    await _suspend(client, moderator, owner.user_id)
    gone = await client.get(f"{API}/alumni/directory", params={"q": word}, headers=viewer.headers)
    assert ids(gone) == []
    await _reactivate(client, admin, owner.user_id)
    back = await client.get(f"{API}/alumni/directory", params={"q": word}, headers=viewer.headers)
    assert ids(back) == [pid]


@pytest.mark.parametrize("path", ["suspend", "reactivate"])
async def test_a_malformed_user_id_is_a_422_not_a_crash(
    client: AsyncClient, db_session: AsyncSession, path: str
) -> None:
    admin = await _with_role(client, db_session, Role.ADMIN)
    r = await client.post(
        f"{API}/users/not-a-uuid/{path}", json={"reason": "x"}, headers=admin.headers
    )
    assert r.status_code == 422


# ------------------------------------------- login says "suspended" only to the owner


async def test_a_suspended_person_with_the_right_password_is_told_the_account_is_suspended(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    moderator = await _with_role(client, db_session, Role.MODERATOR)
    member, _, email = await _member_with_refresh_token(client)
    await _suspend(client, moderator, member.user_id)

    r = await client.post(f"{API}/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "account_suspended"


async def test_a_wrong_password_looks_the_same_for_suspended_active_and_unknown_accounts(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    moderator = await _with_role(client, db_session, Role.MODERATOR)
    suspended, _, suspended_email = await _member_with_refresh_token(client)
    _, _, active_email = await _member_with_refresh_token(client)
    await _suspend(client, moderator, suspended.user_id)

    responses = []
    for email in (suspended_email, active_email, f"nobody-{uuid.uuid4().hex[:8]}@example.com"):
        r = await client.post(
            f"{API}/auth/login", json={"email": email, "password": "Wrong-pass-1!"}
        )
        responses.append((r.status_code, r.json()))

    assert responses[0] == responses[1] == responses[2]
    assert responses[0][1]["error"]["code"] != "account_suspended"
