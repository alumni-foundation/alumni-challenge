"""
`account_status` on the profile response: only platform admins, and a moderator while someone
else's report on that person is open or reviewing, are told. The key is absent for everyone else,
the owner included (an absent key leaves nothing to probe).
"""

from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions.roles import Role
from tests.test_account_status import _profile, _suspend, _with_role
from tests.test_alumni_privacy import Actor, _grant, _make_actor, _make_school

pytestmark = pytest.mark.asyncio

API = "/api/v1"


async def _report(client: AsyncClient, reporter: Actor, profile_id: str) -> str:
    r = await client.post(
        f"{API}/reports",
        json={"target_type": "profile", "target_id": profile_id, "reason": "looks fake"},
        headers=reporter.headers,
    )
    assert r.status_code == 201, r.text
    return str(r.json()["id"])


async def _set_report(client: AsyncClient, by: Actor, report_id: str, status: str) -> None:
    r = await client.patch(
        f"{API}/reports/{report_id}", json={"status": status}, headers=by.headers
    )
    assert r.status_code == 200, r.text


async def _view(client: AsyncClient, profile_id: str, viewer: Actor | None) -> Any:
    return await client.get(f"{API}/alumni/{profile_id}", headers=viewer.headers if viewer else {})


def _has_flag(response: Any) -> bool:
    assert response.status_code == 200, response.text
    return "account_status" in response.json()


async def _scene(
    client: AsyncClient, db: AsyncSession, *, visibility: str = "public"
) -> tuple[Actor, str]:
    owner = await _make_actor(client)
    return owner, await _profile(client, owner, profile_visibility=visibility)


# ------------------------------------------------------------- who is never told


async def test_the_owner_is_not_told_their_own_status(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    owner, pid = await _scene(client, db_session)

    assert not _has_flag(await _view(client, pid, owner))
    mine = await client.get(f"{API}/alumni/profile/me", headers=owner.headers)
    assert not _has_flag(mine)


async def test_anonymous_visitors_members_and_staff_without_platform_rank_are_not_told(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    owner, pid = await _scene(client, db_session)
    school = await _make_school(db_session)
    school_admin = await _make_actor(client)
    await _grant(db_session, school_admin.user_id, Role.SCHOOL_ADMIN, school.id)
    event_manager = await _with_role(client, db_session, Role.EVENT_MANAGER)
    member = await _make_actor(client)

    for viewer in (None, member, school_admin, event_manager):
        assert not _has_flag(await _view(client, pid, viewer)), viewer


async def test_a_suspended_owner_is_still_not_revealed_to_ordinary_viewers(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    owner, pid = await _scene(client, db_session)
    admin = await _with_role(client, db_session, Role.ADMIN)
    await _suspend(client, admin, owner.user_id)
    member = await _make_actor(client)

    # The profile is simply gone for them: nothing to read the flag from.
    assert (await _view(client, pid, member)).status_code == 404
    assert (await _view(client, pid, None)).status_code == 404


# ------------------------------------------------------------------ platform admins


async def test_platform_admins_are_always_told_active_or_suspended(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    owner, pid = await _scene(client, db_session)
    admin = await _with_role(client, db_session, Role.ADMIN)
    super_admin = await _with_role(client, db_session, Role.SUPER_ADMIN)

    for viewer in (admin, super_admin):
        got = await _view(client, pid, viewer)
        assert got.status_code == 200 and got.json()["account_status"] == "active"

    await _suspend(client, admin, owner.user_id)
    for viewer in (admin, super_admin):
        got = await _view(client, pid, viewer)
        assert got.status_code == 200 and got.json()["account_status"] == "suspended"


async def test_a_platform_admin_looking_at_their_own_profile_is_told(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    admin = await _with_role(client, db_session, Role.ADMIN)
    pid = await _profile(client, admin, profile_visibility="public")

    got = await _view(client, pid, admin)

    assert got.json()["account_status"] == "active"  # the platform-admin rule, not an owner rule


# ---------------------------------------------------------------------- moderators


async def test_a_moderator_is_told_only_while_someone_elses_report_is_open_or_reviewing(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    owner, pid = await _scene(client, db_session)
    moderator = await _with_role(client, db_session, Role.MODERATOR)
    reporter = await _make_actor(client)

    assert not _has_flag(await _view(client, pid, moderator))  # no report: sees, not told

    report = await _report(client, reporter, pid)
    assert (await _view(client, pid, moderator)).json()["account_status"] == "active"  # open

    await _set_report(client, moderator, report, "reviewing")
    assert (await _view(client, pid, moderator)).json()["account_status"] == "active"

    await _set_report(client, moderator, report, "resolved")
    assert not _has_flag(await _view(client, pid, moderator))  # ended with the report


async def test_a_dismissed_report_ends_it_too(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    owner, pid = await _scene(client, db_session)
    moderator = await _with_role(client, db_session, Role.MODERATOR)
    report = await _report(client, await _make_actor(client), pid)
    assert _has_flag(await _view(client, pid, moderator))

    await _set_report(client, moderator, report, "dismissed")

    assert not _has_flag(await _view(client, pid, moderator))


async def test_a_moderators_own_report_does_not_count(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    owner, pid = await _scene(client, db_session)
    moderator = await _with_role(client, db_session, Role.MODERATOR)
    await _report(client, moderator, pid)

    assert not _has_flag(await _view(client, pid, moderator))


async def test_a_report_on_someone_else_does_not_tell_the_moderator_about_this_person(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _, reported = await _scene(client, db_session)
    _, other = await _scene(client, db_session)
    moderator = await _with_role(client, db_session, Role.MODERATOR)
    await _report(client, await _make_actor(client), reported)

    assert _has_flag(await _view(client, reported, moderator))
    assert not _has_flag(await _view(client, other, moderator))


async def test_a_moderator_is_told_a_reported_person_is_suspended_and_loses_it_with_the_report(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    owner, pid = await _scene(client, db_session, visibility="members_only")
    moderator = await _with_role(client, db_session, Role.MODERATOR)
    admin = await _with_role(client, db_session, Role.ADMIN)
    report = await _report(client, await _make_actor(client), pid)
    await _suspend(client, admin, owner.user_id)

    got = await _view(client, pid, moderator)
    assert got.status_code == 200 and got.json()["account_status"] == "suspended"

    await _set_report(client, moderator, report, "resolved")
    assert (await _view(client, pid, moderator)).status_code == 404  # no profile, no flag


async def test_a_moderator_who_is_the_owner_is_not_told_through_the_moderator_rule(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    moderator = await _with_role(client, db_session, Role.MODERATOR)
    pid = await _profile(client, moderator, profile_visibility="public")
    await _report(client, await _make_actor(client), pid)

    assert not _has_flag(await _view(client, pid, moderator))


# ------------------------------------------------- other routes that return a profile


async def test_every_other_profile_route_leaves_the_key_out_for_the_owner(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    owner, _ = await _scene(client, db_session)
    skills = await client.put(
        f"{API}/alumni/profile/skills", json={"names": ["golf"]}, headers=owner.headers
    )
    patched = await client.patch(
        f"{API}/alumni/profile", json={"bio": "hello"}, headers=owner.headers
    )

    assert skills.status_code == 200 and "account_status" not in skills.json()
    assert patched.status_code == 200 and "account_status" not in patched.json()
