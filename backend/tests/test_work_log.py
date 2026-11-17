"""Staff work log: who may write or read, whose entry is whose, the same-day lock, Nairobi dates."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions.roles import Role
from app.modules.alumni.models import AlumniProfile
from app.modules.work_log import service
from app.modules.work_log.models import WorkLogEntry
from tests.test_alumni_privacy import Actor, _grant, _make_actor, _make_school

API = "/api/v1/work-log"

# 21:30 UTC on 17 Nov is already 00:30 on 18 Nov in Nairobi (UTC+3, no daylight saving).
LATE_EVENING_UTC = datetime(2026, 11, 17, 21, 30, tzinfo=UTC)
NOON_UTC = datetime(2026, 11, 17, 12, 0, tzinfo=UTC)


def _freeze(monkeypatch: pytest.MonkeyPatch, moment: datetime) -> None:
    monkeypatch.setattr(service, "nairobi_now", lambda: moment.astimezone(service.NAIROBI))


async def _staff(client: AsyncClient, db: AsyncSession, role: Role | None) -> Actor:
    who = await _make_actor(client)
    if role is not None:
        org = None
        if role in (Role.SCHOOL_ADMIN, Role.PARTNER_ADMIN, Role.EVENT_MANAGER, Role.SPORTS_MANAGER):
            org = (await _make_school(db)).id
        await _grant(db, who.user_id, role, org)
    return who


async def _add(
    client: AsyncClient, who: Actor, text: str = "Call the school", kind: str = "planned"
) -> dict[str, Any]:
    r = await client.post(f"{API}/me", json={"kind": kind, "text": text}, headers=who.headers)
    assert r.status_code == 201, r.text
    body: dict[str, Any] = r.json()
    return body


# ---------------------------------------------------------------------- who may do what


async def test_signed_out_gets_401(client: AsyncClient) -> None:
    assert (await client.get(f"{API}/me")).status_code == 401
    assert (await client.get(f"{API}/team")).status_code == 401
    assert (await client.get(f"{API}/team/people")).status_code == 401


@pytest.mark.parametrize("role", [Role.ADMIN, Role.MODERATOR])
async def test_admins_and_moderators_keep_their_own_log(
    client: AsyncClient, db_session: AsyncSession, role: Role
) -> None:
    me = await _staff(client, db_session, role)

    made = await _add(client, me, "  Plan the gala  ")
    listed = await client.get(f"{API}/me", headers=me.headers)

    assert made["text"] == "Plan the gala"
    assert listed.status_code == 200
    assert [e["id"] for e in listed.json()] == [made["id"]]
    # And they can not read the team's.
    assert (await client.get(f"{API}/team", headers=me.headers)).status_code == 403
    assert (await client.get(f"{API}/team/people", headers=me.headers)).status_code == 403


@pytest.mark.parametrize(
    "role",
    [
        Role.SCHOOL_ADMIN,
        Role.PARTNER_ADMIN,
        Role.EVENT_MANAGER,
        Role.SPORTS_MANAGER,
        Role.ALUMNI,
        None,
    ],
)
async def test_everyone_else_is_turned_away_from_every_route(
    client: AsyncClient, db_session: AsyncSession, role: Role | None
) -> None:
    other = await _staff(client, db_session, Role.ADMIN)
    entry = await _add(client, other)
    who = await _staff(client, db_session, role)
    h = who.headers
    body = {"kind": "planned", "text": "x"}

    assert (await client.get(f"{API}/me", headers=h)).status_code == 403
    assert (await client.post(f"{API}/me", json=body, headers=h)).status_code == 403
    assert (
        await client.patch(f"{API}/me/{entry['id']}", json={"text": "x"}, headers=h)
    ).status_code == 403
    assert (await client.post(f"{API}/me/{entry['id']}/complete", headers=h)).status_code == 403
    assert (await client.delete(f"{API}/me/{entry['id']}", headers=h)).status_code == 403
    assert (await client.get(f"{API}/team", headers=h)).status_code == 403
    assert (await client.get(f"{API}/team/people", headers=h)).status_code == 403


async def test_a_super_admin_reads_everything_and_writes_nothing(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    boss = await _staff(client, db_session, Role.SUPER_ADMIN)
    staff = await _staff(client, db_session, Role.ADMIN)
    entry = await _add(client, staff, "Prepare the audit")
    h = boss.headers

    team = await client.get(f"{API}/team", headers=h)
    assert team.status_code == 200
    assert [e["id"] for e in team.json()] == [entry["id"]]
    # Every way of writing, including to someone else's entry, is refused and changes nothing.
    assert (
        await client.post(f"{API}/me", json={"kind": "done", "text": "x"}, headers=h)
    ).status_code == 403
    assert (await client.get(f"{API}/me", headers=h)).status_code == 403
    assert (
        await client.patch(f"{API}/me/{entry['id']}", json={"text": "hijack"}, headers=h)
    ).status_code == 403
    assert (await client.post(f"{API}/me/{entry['id']}/complete", headers=h)).status_code == 403
    assert (await client.delete(f"{API}/me/{entry['id']}", headers=h)).status_code == 403
    row = await db_session.get(WorkLogEntry, uuid.UUID(entry["id"]))
    assert row is not None and row.text == "Prepare the audit" and row.kind == "planned"


# ---------------------------------------------------------------------- ownership


async def test_nobody_can_touch_another_persons_entry(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    a = await _staff(client, db_session, Role.ADMIN)
    b = await _staff(client, db_session, Role.ADMIN)
    mine = await _add(client, a, "Mine alone")
    ghost = uuid.uuid4()

    attempts = [
        await client.patch(f"{API}/me/{mine['id']}", json={"text": "stolen"}, headers=b.headers),
        await client.post(f"{API}/me/{mine['id']}/complete", headers=b.headers),
        await client.delete(f"{API}/me/{mine['id']}", headers=b.headers),
    ]
    missing = await client.delete(f"{API}/me/{ghost}", headers=b.headers)

    for r in attempts:
        # Looks exactly like an entry that does not exist, so nothing leaks.
        assert r.status_code == 404
        assert r.json()["error"]["code"] == missing.json()["error"]["code"]
        assert mine["id"] not in r.text
    assert (await client.get(f"{API}/me", headers=b.headers)).json() == []
    db_session.expire_all()
    row = await db_session.get(WorkLogEntry, uuid.UUID(mine["id"]))
    assert row is not None
    assert (row.text, row.kind, row.completed_at) == ("Mine alone", "planned", None)


# ---------------------------------------------------------------------- the rules of an entry


async def test_a_line_added_as_done_has_a_completion_time_and_a_planned_one_does_not(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    me = await _staff(client, db_session, Role.MODERATOR)

    done = await _add(client, me, "Cleared the queue", "done")
    planned = await _add(client, me, "Review reports", "planned")

    assert done["completed_at"] is not None
    assert planned["completed_at"] is None
    assert planned["editable"] is True


async def test_marking_planned_done_sets_the_time_once(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    me = await _staff(client, db_session, Role.ADMIN)
    _freeze(monkeypatch, NOON_UTC)
    entry = await _add(client, me)
    _freeze(monkeypatch, NOON_UTC + timedelta(hours=2))

    first = await client.post(f"{API}/me/{entry['id']}/complete", headers=me.headers)
    _freeze(monkeypatch, NOON_UTC + timedelta(hours=5))
    again = await client.post(f"{API}/me/{entry['id']}/complete", headers=me.headers)

    assert first.status_code == 200 and again.status_code == 200
    assert first.json()["kind"] == "done"
    assert datetime.fromisoformat(first.json()["completed_at"]) == NOON_UTC + timedelta(hours=2)
    assert datetime.fromisoformat(again.json()["completed_at"]) == datetime.fromisoformat(
        first.json()["completed_at"]
    )


@pytest.mark.parametrize(
    "payload",
    [
        {"kind": "planned", "text": "   "},
        {"kind": "planned", "text": ""},
        {"kind": "planned", "text": "x" * 501},
        {"kind": "later", "text": "ok"},
        {"kind": "planned"},
        # The client never sends dates or times.
        {"kind": "planned", "text": "ok", "entry_date": "2020-01-01"},
        {"kind": "done", "text": "ok", "completed_at": "2020-01-01T00:00:00Z"},
    ],
)
async def test_bad_input_is_a_422(
    client: AsyncClient, db_session: AsyncSession, payload: dict[str, Any]
) -> None:
    me = await _staff(client, db_session, Role.ADMIN)
    r = await client.post(f"{API}/me", json=payload, headers=me.headers)
    assert r.status_code == 422


async def test_the_text_limits_are_exact_and_edits_follow_the_same_rules(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    me = await _staff(client, db_session, Role.ADMIN)
    longest = await _add(client, me, "x" * 500)

    ok = await client.patch(f"{API}/me/{longest['id']}", json={"text": " new "}, headers=me.headers)
    blank = await client.patch(f"{API}/me/{longest['id']}", json={"text": "  "}, headers=me.headers)
    dated = await client.patch(
        f"{API}/me/{longest['id']}",
        json={"text": "a", "entry_date": "2020-01-01"},
        headers=me.headers,
    )

    assert ok.status_code == 200 and ok.json()["text"] == "new"
    assert blank.status_code == 422 and dated.status_code == 422


# ---------------------------------------------------------------------- the clock


async def test_the_day_is_the_nairobi_day_not_the_utc_day(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    me = await _staff(client, db_session, Role.ADMIN)

    _freeze(monkeypatch, datetime(2026, 11, 17, 20, 59, tzinfo=UTC))  # 23:59 in Nairobi
    before = await _add(client, me, "Before midnight")
    _freeze(monkeypatch, LATE_EVENING_UTC)  # 00:30 next day in Nairobi, still 17 Nov in UTC
    after = await _add(client, me, "After midnight")

    assert before["entry_date"] == "2026-11-17"
    assert after["entry_date"] == "2026-11-18"
    # Stored as an instant, so the Nairobi wall clock is three hours ahead of UTC.
    assert datetime.fromisoformat(after["created_at"]) == LATE_EVENING_UTC
    assert datetime.fromisoformat(after["created_at"]).astimezone(service.NAIROBI).hour == 0


async def test_an_entry_is_locked_after_its_day_but_can_still_be_marked_done(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    me = await _staff(client, db_session, Role.ADMIN)
    _freeze(monkeypatch, NOON_UTC)
    entry = await _add(client, me, "Write the report")
    url = f"{API}/me/{entry['id']}"

    # Later the same day: still open for changes.
    _freeze(monkeypatch, datetime(2026, 11, 17, 20, 59, tzinfo=UTC))
    assert (
        await client.patch(url, json={"text": "Write the report v2"}, headers=me.headers)
    ).status_code == 200

    # Past midnight in Nairobi: locked, with a plain message.
    _freeze(monkeypatch, LATE_EVENING_UTC)
    edit = await client.patch(url, json={"text": "too late"}, headers=me.headers)
    gone = await client.delete(url, headers=me.headers)
    assert edit.status_code == 409 and gone.status_code == 409
    assert edit.json()["error"]["code"] == "work_log_entry_locked"
    assert edit.json()["error"]["message"] == service.LOCKED
    listed = (await client.get(f"{API}/me", headers=me.headers)).json()
    assert [(e["text"], e["editable"]) for e in listed] == [("Write the report v2", False)]

    # A plan from yesterday can still be ticked off today; the text stays locked.
    done = await client.post(f"{url}/complete", headers=me.headers)
    assert done.status_code == 200 and done.json()["kind"] == "done"
    assert done.json()["entry_date"] == "2026-11-17" and done.json()["editable"] is False
    assert (await client.patch(url, json={"text": "again"}, headers=me.headers)).status_code == 409


# ---------------------------------------------------------------------- lists


async def test_my_entries_are_newest_day_first_then_in_the_order_added(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    me = await _staff(client, db_session, Role.ADMIN)
    for day, text in [(10, "d10 first"), (10, "d10 second"), (12, "d12 first"), (11, "d11 first")]:
        _freeze(
            monkeypatch, datetime(2026, 11, day, 9, 0, tzinfo=UTC) + timedelta(minutes=len(text))
        )
        await _add(client, me, text)
    _freeze(monkeypatch, datetime(2026, 11, 13, 9, 0, tzinfo=UTC))

    listed = (await client.get(f"{API}/me", headers=me.headers)).json()
    narrowed = (
        await client.get(
            f"{API}/me", params={"from": "2026-11-11", "to": "2026-11-11"}, headers=me.headers
        )
    ).json()

    assert [e["text"] for e in listed] == ["d12 first", "d11 first", "d10 first", "d10 second"]
    assert [e["text"] for e in narrowed] == ["d11 first"]


async def test_my_entries_default_to_a_recent_window_and_reject_silly_ranges(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    me = await _staff(client, db_session, Role.ADMIN)
    _freeze(monkeypatch, datetime(2026, 6, 1, 9, 0, tzinfo=UTC))
    await _add(client, me, "Long ago")
    _freeze(monkeypatch, NOON_UTC)
    await _add(client, me, "Today")

    default = (await client.get(f"{API}/me", headers=me.headers)).json()
    backwards = await client.get(
        f"{API}/me", params={"from": "2026-11-17", "to": "2026-11-01"}, headers=me.headers
    )
    huge = await client.get(f"{API}/me", params={"from": "2020-01-01"}, headers=me.headers)
    bad_date = await client.get(f"{API}/me", params={"from": "tomorrow"}, headers=me.headers)

    assert [e["text"] for e in default] == ["Today"]
    assert backwards.status_code == 422 and huge.status_code == 422 and bad_date.status_code == 422


async def test_the_team_view_names_people_filters_and_pages(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    boss = await _staff(client, db_session, Role.SUPER_ADMIN)
    ann = await _staff(client, db_session, Role.ADMIN)
    bob = await _staff(client, db_session, Role.MODERATOR)
    db_session.add(AlumniProfile(user_id=ann.user_id, full_name="Ann Wanjiru"))
    await db_session.flush()
    for day in (14, 15, 16):
        _freeze(monkeypatch, datetime(2026, 11, day, 9, 0, tzinfo=UTC))
        await _add(client, ann, f"ann {day}")
    _freeze(monkeypatch, datetime(2026, 11, 15, 10, 0, tzinfo=UTC))
    await _add(client, bob, "bob 15", "done")
    get = lambda **q: client.get(f"{API}/team", params=q, headers=boss.headers)  # noqa: E731

    everything = (await get()).json()
    only_bob = (await get(user_id=str(bob.user_id))).json()
    window = (await get(**{"from": "2026-11-15", "to": "2026-11-15"})).json()
    page = (await get(limit=2, offset=2)).json()

    assert [e["text"] for e in everything] == ["ann 16", "bob 15", "ann 15", "ann 14"]
    ann_row = next(e for e in everything if e["text"] == "ann 16")
    bob_row = next(e for e in everything if e["text"] == "bob 15")
    assert ann_row["author_name"] == "Ann Wanjiru"
    # Staff usually have no alumni profile: the email stands in, and the entry is not dropped.
    assert bob_row["author_name"] == bob_row["author_email"] != ""
    assert [e["text"] for e in only_bob] == ["bob 15"]
    assert {e["text"] for e in window} == {"bob 15", "ann 15"}
    assert [e["text"] for e in page] == ["ann 15", "ann 14"]


@pytest.mark.parametrize(
    "params",
    [{"limit": 0}, {"limit": 201}, {"offset": -1}, {"from": "2026-11-17", "to": "2026-11-01"}],
)
async def test_team_paging_and_dates_are_bounded(
    client: AsyncClient, db_session: AsyncSession, params: dict[str, Any]
) -> None:
    boss = await _staff(client, db_session, Role.SUPER_ADMIN)
    r = await client.get(f"{API}/team", params=params, headers=boss.headers)
    assert r.status_code == 422


async def test_the_people_list_has_admins_and_moderators_only(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    boss = await _staff(client, db_session, Role.SUPER_ADMIN)
    admin = await _staff(client, db_session, Role.ADMIN)
    mod = await _staff(client, db_session, Role.MODERATOR)
    school = await _staff(client, db_session, Role.SCHOOL_ADMIN)
    alum = await _staff(client, db_session, Role.ALUMNI)

    ids = {
        p["user_id"] for p in (await client.get(f"{API}/team/people", headers=boss.headers)).json()
    }

    assert {str(admin.user_id), str(mod.user_id)} <= ids
    assert not ids & {str(school.user_id), str(alum.user_id), str(boss.user_id)}


async def test_deleting_removes_the_row(client: AsyncClient, db_session: AsyncSession) -> None:
    me = await _staff(client, db_session, Role.ADMIN)
    entry = await _add(client, me)

    gone = await client.delete(f"{API}/me/{entry['id']}", headers=me.headers)

    assert gone.status_code == 204
    left = await db_session.scalars(
        select(WorkLogEntry).where(WorkLogEntry.author_user_id == me.user_id)
    )
    assert left.all() == []


async def test_every_write_is_committed(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The test session wraps everything in one transaction, so a forgotten commit would pass every
    other test here and lose the data in the real app (found by hand in the browser). Count them."""
    me = await _staff(client, db_session, Role.ADMIN)
    commits: list[int] = []
    real_commit = AsyncSession.commit

    async def counting_commit(self: AsyncSession) -> None:
        commits.append(1)
        await real_commit(self)

    monkeypatch.setattr(AsyncSession, "commit", counting_commit)

    entry = await _add(client, me)
    after_add = len(commits)
    await client.patch(f"{API}/me/{entry['id']}", json={"text": "edited"}, headers=me.headers)
    after_edit = len(commits)
    await client.post(f"{API}/me/{entry['id']}/complete", headers=me.headers)
    after_complete = len(commits)
    await client.delete(f"{API}/me/{entry['id']}", headers=me.headers)

    assert after_add >= 1
    assert after_edit > after_add
    assert after_complete > after_edit
    assert len(commits) > after_complete
