import uuid

from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions.roles import Role
from app.modules.audit.models import AuditLogEntry
from app.modules.connections.models import Connection
from tests.test_alumni_privacy import _grant, _make_actor, _make_profile, _make_school

API = "/api/v1"


async def _file_report(
    client: AsyncClient, actor_headers: dict[str, str], profile_id: str, reason: str = "spam"
) -> dict[str, object]:
    r = await client.post(
        f"{API}/reports",
        json={"target_type": "profile", "target_id": profile_id, "reason": reason},
        headers=actor_headers,
    )
    assert r.status_code == 201, r.text
    body: dict[str, object] = r.json()
    return body


async def _moderator(client: AsyncClient, db: AsyncSession):  # type: ignore[no-untyped-def]
    mod = await _make_actor(client)
    await _grant(db, mod.user_id, Role.MODERATOR, None)
    return mod


# ---------------------------------------------------------------- reports


async def test_reporting_a_nonexistent_profile_is_422(client: AsyncClient) -> None:
    reporter = await _make_actor(client)
    r = await client.post(
        f"{API}/reports",
        json={"target_type": "profile", "target_id": str(uuid.uuid4()), "reason": "spam"},
        headers=reporter.headers,
    )
    assert r.status_code == 422, r.text


async def test_filing_a_report_needs_login(client: AsyncClient) -> None:
    r = await client.post(
        f"{API}/reports",
        json={"target_type": "profile", "target_id": str(uuid.uuid4()), "reason": "x"},
    )
    assert r.status_code == 401, r.text


async def test_blank_reason_is_rejected(client: AsyncClient) -> None:
    owner = await _make_actor(client)
    reporter = await _make_actor(client)
    pid = await _make_profile(client, owner)
    r = await client.post(
        f"{API}/reports",
        json={"target_type": "profile", "target_id": pid, "reason": "   "},
        headers=reporter.headers,
    )
    assert r.status_code == 422, r.text


async def test_you_cannot_report_your_own_profile(client: AsyncClient) -> None:
    owner = await _make_actor(client)
    pid = await _make_profile(client, owner)
    r = await client.post(
        f"{API}/reports",
        json={"target_type": "profile", "target_id": pid, "reason": "me"},
        headers=owner.headers,
    )
    assert r.status_code == 422, r.text


async def test_a_second_open_report_from_the_same_person_is_409(client: AsyncClient) -> None:
    owner = await _make_actor(client)
    reporter = await _make_actor(client)
    pid = await _make_profile(client, owner)
    await _file_report(client, reporter.headers, pid)
    r = await client.post(
        f"{API}/reports",
        json={"target_type": "profile", "target_id": pid, "reason": "again"},
        headers=reporter.headers,
    )
    assert r.status_code == 409, r.text


async def test_plain_alumni_cannot_list_or_review_reports(client: AsyncClient) -> None:
    owner = await _make_actor(client)
    reporter = await _make_actor(client)
    pid = await _make_profile(client, owner)
    report = await _file_report(client, reporter.headers, pid)

    denied = await client.get(f"{API}/reports", headers=reporter.headers)
    assert denied.status_code == 403, denied.text
    r = await client.patch(
        f"{API}/reports/{report['id']}", json={"status": "resolved"}, headers=reporter.headers
    )
    assert r.status_code == 403, r.text


async def test_moderator_lists_and_reviews_reports(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    owner = await _make_actor(client)
    reporter = await _make_actor(client)
    mod = await _moderator(client, db_session)
    pid = await _make_profile(client, owner)
    report = await _file_report(client, reporter.headers, pid)

    listed = await client.get(f"{API}/reports", headers=mod.headers)
    assert listed.status_code == 200, listed.text
    assert report["id"] in [x["id"] for x in listed.json()]
    only_open = await client.get(f"{API}/reports?status=resolved", headers=mod.headers)
    assert report["id"] not in [x["id"] for x in only_open.json()]

    reviewing = await client.patch(
        f"{API}/reports/{report['id']}", json={"status": "reviewing"}, headers=mod.headers
    )
    assert reviewing.status_code == 200, reviewing.text
    assert reviewing.json()["reviewed_by"] == str(mod.user_id)
    assert reviewing.json()["resolved_at"] is None

    resolved = await client.patch(
        f"{API}/reports/{report['id']}", json={"status": "resolved"}, headers=mod.headers
    )
    assert resolved.json()["status"] == "resolved"
    assert resolved.json()["resolved_at"] is not None

    audited = await db_session.scalar(
        select(func.count())
        .select_from(AuditLogEntry)
        .where(AuditLogEntry.action == "report.review")
    )
    assert audited == 2


async def test_reviewing_an_unknown_report_is_404(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    mod = await _moderator(client, db_session)
    r = await client.patch(
        f"{API}/reports/{uuid.uuid4()}", json={"status": "resolved"}, headers=mod.headers
    )
    assert r.status_code == 404, r.text


# ------------------------------------------- time-limited moderator visibility


async def test_moderator_access_to_a_private_profile_lasts_only_while_the_report_is_live(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    owner = await _make_actor(client)
    reporter = await _make_actor(client)
    mod = await _moderator(client, db_session)
    pid = await _make_profile(client, owner, visibility="private")

    # no report: a moderator is just another member
    assert (await client.get(f"{API}/alumni/{pid}", headers=mod.headers)).status_code == 404

    report = await _file_report(client, reporter.headers, pid)
    assert (await client.get(f"{API}/alumni/{pid}", headers=mod.headers)).status_code == 200

    await client.patch(
        f"{API}/reports/{report['id']}", json={"status": "reviewing"}, headers=mod.headers
    )
    assert (await client.get(f"{API}/alumni/{pid}", headers=mod.headers)).status_code == 200

    await client.patch(
        f"{API}/reports/{report['id']}", json={"status": "resolved"}, headers=mod.headers
    )
    assert (await client.get(f"{API}/alumni/{pid}", headers=mod.headers)).status_code == 404


async def test_a_dismissed_report_also_ends_moderator_access(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    owner = await _make_actor(client)
    reporter = await _make_actor(client)
    mod = await _moderator(client, db_session)
    pid = await _make_profile(client, owner, visibility="private")
    report = await _file_report(client, reporter.headers, pid)
    assert (await client.get(f"{API}/alumni/{pid}", headers=mod.headers)).status_code == 200

    await client.patch(
        f"{API}/reports/{report['id']}", json={"status": "dismissed"}, headers=mod.headers
    )
    assert (await client.get(f"{API}/alumni/{pid}", headers=mod.headers)).status_code == 404


async def test_a_moderator_cannot_open_a_profile_by_reporting_it_themselves(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    owner = await _make_actor(client)
    mod = await _moderator(client, db_session)
    pid = await _make_profile(client, owner, visibility="private")

    await _file_report(client, mod.headers, pid, reason="I just want to look")
    assert (await client.get(f"{API}/alumni/{pid}", headers=mod.headers)).status_code == 404


async def test_a_report_gives_a_plain_member_no_access(client: AsyncClient) -> None:
    owner = await _make_actor(client)
    reporter = await _make_actor(client)
    other = await _make_actor(client)
    pid = await _make_profile(client, owner, visibility="private")
    await _file_report(client, reporter.headers, pid)
    assert (await client.get(f"{API}/alumni/{pid}", headers=other.headers)).status_code == 404
    # not even the reporter
    assert (await client.get(f"{API}/alumni/{pid}", headers=reporter.headers)).status_code == 404


async def test_school_admin_is_not_a_moderator_and_gets_no_report_based_access(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    owner = await _make_actor(client)
    reporter = await _make_actor(client)
    school_admin = await _make_actor(client)
    owners_school = await _make_school(db_session)
    other_school = await _make_school(db_session)
    await _grant(db_session, school_admin.user_id, Role.SCHOOL_ADMIN, other_school.id)
    pid = await _make_profile(client, owner, visibility="private", school_id=owners_school.id)
    await _file_report(client, reporter.headers, pid)

    assert (
        await client.get(f"{API}/alumni/{pid}", headers=school_admin.headers)
    ).status_code == 404
    assert (await client.get(f"{API}/reports", headers=school_admin.headers)).status_code == 403


async def test_report_access_never_lets_a_moderator_verify_a_profile(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    owner = await _make_actor(client)
    reporter = await _make_actor(client)
    mod = await _moderator(client, db_session)
    school = await _make_school(db_session)
    pid = await _make_profile(client, owner, visibility="private", school_id=school.id)
    await _file_report(client, reporter.headers, pid)

    r = await client.patch(
        f"{API}/alumni/{pid}/verify", json={"verified": True}, headers=mod.headers
    )
    assert r.status_code == 403, r.text


# ---------------------------------------------------------------- blocking


async def _request(client: AsyncClient, frm, to) -> dict[str, object]:  # type: ignore[no-untyped-def]
    r = await client.post(
        f"{API}/connections", json={"addressee_id": str(to.user_id)}, headers=frm.headers
    )
    assert r.status_code == 201, r.text
    body: dict[str, object] = r.json()
    return body


async def _block(client: AsyncClient, blocker, target):  # type: ignore[no-untyped-def]
    return await client.post(
        f"{API}/connections/block", json={"user_id": str(target.user_id)}, headers=blocker.headers
    )


async def test_block_flow_end_to_end(client: AsyncClient, db_session: AsyncSession) -> None:
    a = await _make_actor(client)
    b = await _make_actor(client)
    pending = await _request(client, a, b)

    blocked = await _block(client, a, b)
    assert blocked.status_code == 201, blocked.text
    assert blocked.json()["status"] == "blocked"
    assert blocked.json()["id"] == pending["id"]  # reused, not duplicated
    rows = await db_session.scalar(select(func.count()).select_from(Connection))
    assert rows == 1

    # blocker sees it in their blocked list; the blocked person sees nothing
    mine = await client.get(f"{API}/connections/blocked", headers=a.headers)
    assert [x["id"] for x in mine.json()] == [pending["id"]]
    assert (await client.get(f"{API}/connections/blocked", headers=b.headers)).json() == []

    # hidden from the normal list for both
    assert (await client.get(f"{API}/connections", headers=a.headers)).json() == []
    assert (await client.get(f"{API}/connections", headers=b.headers)).json() == []

    # the blocked person cannot send a new request
    again = await client.post(
        f"{API}/connections", json={"addressee_id": str(a.user_id)}, headers=b.headers
    )
    assert again.status_code == 403, again.text

    # only the blocker can unblock
    other = await client.post(f"{API}/connections/{pending['id']}/unblock", headers=b.headers)
    assert other.status_code == 403, other.text

    # the blocked person cannot wipe the block through the old remove/accept/decline routes
    for method, path in (
        ("DELETE", f"{API}/connections/{pending['id']}"),
        ("PATCH", f"{API}/connections/{pending['id']}/accept"),
        ("PATCH", f"{API}/connections/{pending['id']}/decline"),
    ):
        r = await client.request(method, path, headers=b.headers)
        assert r.status_code == 404, (method, path, r.status_code)
    still = await client.get(f"{API}/connections/blocked", headers=a.headers)
    assert len(still.json()) == 1

    # the blocker unblocks: status is removed, and a fresh request works
    lifted = await client.post(f"{API}/connections/{pending['id']}/unblock", headers=a.headers)
    assert lifted.status_code == 200, lifted.text
    assert lifted.json()["status"] == "removed"
    assert (await client.get(f"{API}/connections/blocked", headers=a.headers)).json() == []
    fresh = await client.post(
        f"{API}/connections", json={"addressee_id": str(a.user_id)}, headers=b.headers
    )
    assert fresh.status_code == 201, fresh.text
    assert fresh.json()["status"] == "pending"


async def test_blocking_someone_you_have_no_connection_with_creates_a_blocked_row(
    client: AsyncClient,
) -> None:
    a = await _make_actor(client)
    b = await _make_actor(client)
    r = await _block(client, a, b)
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "blocked"
    assert r.json()["requester_id"] == str(a.user_id)


async def test_blocking_an_accepted_connection_reuses_the_row(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    a = await _make_actor(client)
    b = await _make_actor(client)
    conn = await _request(client, a, b)
    await client.patch(f"{API}/connections/{conn['id']}/accept", headers=b.headers)

    # B blocks A (the other direction from how the row was created)
    r = await _block(client, b, a)
    assert r.status_code == 201, r.text
    assert r.json()["id"] == conn["id"]
    assert await db_session.scalar(select(func.count()).select_from(Connection)) == 1
    assert len((await client.get(f"{API}/connections/blocked", headers=b.headers)).json()) == 1
    assert (await client.get(f"{API}/connections/blocked", headers=a.headers)).json() == []


async def test_self_block_is_422(client: AsyncClient) -> None:
    a = await _make_actor(client)
    assert (await _block(client, a, a)).status_code == 422


async def test_double_block_is_409(client: AsyncClient) -> None:
    a = await _make_actor(client)
    b = await _make_actor(client)
    assert (await _block(client, a, b)).status_code == 201
    assert (await _block(client, a, b)).status_code == 409


async def test_the_blocked_person_cannot_take_over_the_block(client: AsyncClient) -> None:
    a = await _make_actor(client)
    b = await _make_actor(client)
    first = await _block(client, a, b)
    assert (await _block(client, b, a)).status_code == 409
    # the block is still A's: A can lift it, B cannot
    assert (
        await client.post(f"{API}/connections/{first.json()['id']}/unblock", headers=b.headers)
    ).status_code == 403
    assert (
        await client.post(f"{API}/connections/{first.json()['id']}/unblock", headers=a.headers)
    ).status_code == 200


async def test_blocking_an_unknown_user_is_404(client: AsyncClient) -> None:
    a = await _make_actor(client)
    r = await client.post(
        f"{API}/connections/block", json={"user_id": str(uuid.uuid4())}, headers=a.headers
    )
    assert r.status_code == 404, r.text


async def test_unblocking_a_row_that_is_not_blocked_is_409_and_a_strangers_row_is_404(
    client: AsyncClient,
) -> None:
    a = await _make_actor(client)
    b = await _make_actor(client)
    stranger = await _make_actor(client)
    conn = await _request(client, a, b)
    assert (
        await client.post(f"{API}/connections/{conn['id']}/unblock", headers=a.headers)
    ).status_code == 409
    assert (
        await client.post(f"{API}/connections/{conn['id']}/unblock", headers=stranger.headers)
    ).status_code == 404
