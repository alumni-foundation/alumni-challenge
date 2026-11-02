"""GET /admin/overview: who may ask about what, and that the numbers are right and anonymous."""

import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions.roles import Role
from app.infrastructure.redis import get_redis_client
from app.modules.alumni.models import AlumniProfile, VerificationStatus
from app.modules.audit.models import AuditLogEntry
from app.modules.connections.models import Connection, ConnectionStatus
from app.modules.identity.models import User
from app.modules.moderation.models import Report, ReportStatus, ReportTargetType
from tests.test_alumni_privacy import Actor, _grant, _make_actor
from tests.test_events_core import API, _create, _platform_admin, _run_school
from tests.test_manual_payment import _act, _booked, _code, _paid_and_sent, _send, _shop

URL = f"{API}/admin/overview"
SECRET_NAME = "Zebediah Quillfeather"


async def _get(
    client: AsyncClient, who: Actor | None, org: uuid.UUID | str | None = None, **q: str
) -> Any:
    params = {k: v for k, v in q.items()}
    if org is not None:
        params["organization_id"] = str(org)
    return await client.get(URL, params=params, headers=who.headers if who else None)


async def _person(
    db: AsyncSession,
    school_id: uuid.UUID | None,
    *,
    complete: bool = True,
    verified: bool = False,
    days_ago: float = 1,
) -> uuid.UUID:
    """A member made straight in the database (the shortcut keeps the counts easy to follow)."""
    created = datetime.now(UTC) - timedelta(days=days_ago)
    user = User(
        email=f"p-{uuid.uuid4().hex[:10]}@example.com", password_hash="x", created_at=created
    )
    db.add(user)
    await db.flush()
    db.add(
        AlumniProfile(
            user_id=user.id,
            full_name=SECRET_NAME,
            school_id=school_id,
            graduation_year=2010 if complete else None,
            verification_status=(
                VerificationStatus.VERIFIED if verified else VerificationStatus.UNVERIFIED
            ),
            created_at=created,
            updated_at=created,
        )
    )
    await db.flush()
    return user.id


async def _flush_cache() -> None:
    redis = get_redis_client()
    for key in await redis.keys("admin_overview:*"):
        await redis.delete(key)


# ---------------------------------------------------------------------- who sees what


async def test_nobody_signed_out_and_nobody_without_a_role_gets_in(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    plain = await _make_actor(client)
    alum = await _make_actor(client)
    await _grant(db_session, alum.user_id, Role.ALUMNI, None)
    sports = await _make_actor(client)
    school, _ = await _run_school(client, db_session, Role.SCHOOL_ADMIN)
    await _grant(db_session, sports.user_id, Role.SPORTS_MANAGER, school.id)

    assert (await _get(client, None)).status_code == 401
    for who in (plain, alum, sports):
        assert (await _get(client, who)).status_code == 403
        assert (await _get(client, who, school.id)).status_code == 403


@pytest.mark.parametrize("role", [Role.SCHOOL_ADMIN, Role.PARTNER_ADMIN, Role.EVENT_MANAGER])
async def test_an_organization_role_sees_its_own_organization_and_nobody_elses(
    client: AsyncClient, db_session: AsyncSession, role: Role
) -> None:
    mine, me = await _run_school(client, db_session, role)
    other, _ = await _run_school(client, db_session, Role.SCHOOL_ADMIN)
    await _person(db_session, mine.id)
    await _person(db_session, other.id)

    plain = await _get(client, me)
    named = await _get(client, me, mine.id)
    stranger = await _get(client, me, other.id)
    missing = await _get(client, me, uuid.uuid4())

    assert plain.status_code == 200 and named.status_code == 200
    assert plain.json()["totals"]["members"]["value"] == 1
    assert named.json()["organization_id"] == str(mine.id)
    # Another organization and one that does not exist look exactly alike.
    assert stranger.status_code == 404 and missing.status_code == 404
    assert stranger.json()["error"]["code"] == missing.json()["error"]["code"]
    assert str(other.id) not in stranger.text


async def test_a_school_admin_asking_about_another_school_learns_nothing(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    a, admin_a = await _run_school(client, db_session, Role.SCHOOL_ADMIN)
    b, _ = await _run_school(client, db_session, Role.SCHOOL_ADMIN)
    for _ in range(3):
        await _person(db_session, b.id)

    for period in ("30d", "90d", "365d"):
        r = await _get(client, admin_a, b.id, period=period)
        assert r.status_code == 404
        assert "totals" not in r.text and "members" not in r.text


async def test_a_role_in_one_organization_gives_nothing_in_another(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    a, _ = await _run_school(client, db_session, Role.SCHOOL_ADMIN)
    b, _ = await _run_school(client, db_session, Role.SCHOOL_ADMIN)
    both = await _make_actor(client)
    await _grant(db_session, both.user_id, Role.EVENT_MANAGER, a.id)
    await _grant(db_session, both.user_id, Role.PARTNER_ADMIN, b.id)
    await _person(db_session, a.id)
    await _person(db_session, b.id)
    await _person(db_session, b.id)

    together = await _get(client, both)
    one = await _get(client, both, b.id)

    assert together.json()["totals"]["members"]["value"] == 3  # all of mine, no more
    assert one.json()["totals"]["members"]["value"] == 2


async def test_a_revoked_role_no_longer_opens_the_dashboard(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    school, admin = await _run_school(client, db_session, Role.SCHOOL_ADMIN)
    assert (await _get(client, admin, school.id)).status_code == 200
    await db_session.execute(
        text("UPDATE memberships SET status = 'revoked' WHERE user_id = :u"),
        {"u": str(admin.user_id)},
    )

    assert (await _get(client, admin, school.id)).status_code == 403


async def test_a_moderator_gets_the_report_counts_and_nothing_else(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    mod = await _make_actor(client)
    await _grant(db_session, mod.user_id, Role.MODERATOR, None)
    school, _ = await _run_school(client, db_session, Role.SCHOOL_ADMIN)
    await _person(db_session, school.id)
    reporter = await _person(db_session, None)
    for status in (ReportStatus.OPEN, ReportStatus.REVIEWING, ReportStatus.RESOLVED):
        db_session.add(
            Report(
                reporter_user_id=reporter,
                target_type=ReportTargetType.PROFILE,
                target_id=uuid.uuid4(),
                reason="x",
                status=status,
            )
        )
    await db_session.flush()
    before = await _get(client, await _platform_admin(client, db_session))
    await _flush_cache()

    r = await _get(client, mod)

    body = r.json()
    assert r.status_code == 200
    for section in ("totals", "funnel", "upcoming_events", "signups_per_day", "recent_audit"):
        assert body[section] is None
    assert body["attention"]["reports_open"] == before.json()["attention"]["reports_open"]
    assert body["attention"]["reports_open"] >= 1 and body["attention"]["reports_reviewing"] >= 1
    for field in (
        "verification_requests_waiting",
        "payments_waiting_confirmation",
        "refunds_due",
        "events_in_draft",
    ):
        assert body["attention"][field] is None
    # A moderator has no organization to ask about.
    assert (await _get(client, mod, school.id)).status_code == 404


async def test_a_moderator_who_also_manages_a_school_gets_both_parts(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    school, me = await _run_school(client, db_session, Role.EVENT_MANAGER)
    await _grant(db_session, me.user_id, Role.MODERATOR, None)
    await _person(db_session, school.id)

    body = (await _get(client, me)).json()

    assert body["totals"]["members"]["value"] == 1
    assert body["attention"]["reports_open"] is not None


async def test_a_platform_admin_sees_everything_or_one_organization(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    admin = await _platform_admin(client, db_session)
    school, _ = await _run_school(client, db_session, Role.SCHOOL_ADMIN)
    base = (await _get(client, admin)).json()
    await _flush_cache()
    for _ in range(2):
        await _person(db_session, school.id)
    await _person(db_session, None)

    everything = await _get(client, admin)
    one = await _get(client, admin, school.id)
    nowhere = await _get(client, admin, uuid.uuid4())

    assert everything.json()["totals"]["members"]["value"] == base["totals"]["members"]["value"] + 3
    assert one.json()["totals"]["members"]["value"] == 2
    assert one.json()["attention"]["reports_open"] is None  # reports belong to no school
    assert everything.json()["attention"]["reports_open"] is not None
    assert nowhere.status_code == 404


async def test_a_bad_period_is_refused(client: AsyncClient, db_session: AsyncSession) -> None:
    admin = await _platform_admin(client, db_session)

    for bad in ("7d", "30", "", "all"):
        assert (await _get(client, admin, period=bad)).status_code == 422
    assert (await _get(client, admin, "not-a-uuid")).status_code == 422
    for good in ("30d", "90d", "365d"):
        assert (await _get(client, admin, period=good)).json()["period"] == good


# ------------------------------------------------------------------------ the numbers


async def test_totals_compare_with_the_period_before(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    school, admin = await _run_school(client, db_session, Role.SCHOOL_ADMIN)
    for days in (100, 50):  # before the last 30 days, and in the 30 before those
        await _person(db_session, school.id, days_ago=days)
    await _person(db_session, school.id, days_ago=45, verified=True)
    for _ in range(3):  # this period
        await _person(db_session, school.id, days_ago=5)
    await _person(db_session, school.id, days_ago=2, verified=True)

    t = (await _get(client, admin, period="30d")).json()["totals"]

    assert t["members"] == {"value": 7, "previous": 3, "change_percent": 133.3}
    assert t["new_members"] == {"value": 4, "previous": 2, "change_percent": 100.0}
    assert t["verified_members"]["value"] == 2
    assert t["verified_members"]["previous"] == 1
    nobody = await _run_school(client, db_session, Role.SCHOOL_ADMIN)
    empty = (await _get(client, nobody[1])).json()["totals"]
    assert empty["members"] == {"value": 0, "previous": 0, "change_percent": None}


async def test_the_funnel_counts_each_step_among_those_who_passed_the_one_before(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    shop = await _shop(client, db_session)
    school = shop.school_id
    await _person(db_session, school, complete=False)  # signed up only
    await _person(db_session, school)  # profile complete
    v1 = await _person(db_session, school, verified=True)
    v2 = await _person(db_session, school, verified=True)
    await _person(db_session, school, verified=True)
    db_session.add(Connection(requester_id=v1, addressee_id=v2, status=ConnectionStatus.ACCEPTED))
    other = await _person(db_session, school)
    db_session.add(
        Connection(requester_id=other, addressee_id=v1, status=ConnectionStatus.PENDING)
    )  # pending does not count
    # v2 books and the organizer confirms the payment
    booker = await _login_as(client, db_session, v2)
    _, b = await _booked(client, shop, booker)
    assert (await _send(client, booker, b["id"], _code())).status_code == 200
    assert (await _act(client, shop.admin, b["id"], "confirm-manual")).status_code == 200

    funnel = (await _get(client, shop.admin, school)).json()["funnel"]

    assert [(s["step"], s["count"]) for s in funnel] == [
        ("signed_up", 6),
        ("profile_complete", 5),
        ("verified", 3),
        ("connected", 2),
        ("booked_an_event", 1),
    ]
    assert [s["percent_of_previous"] for s in funnel] == [100.0, 83.3, 60.0, 66.7, 50.0]


async def _login_as(client: AsyncClient, db: AsyncSession, user_id: uuid.UUID) -> Actor:
    """A signed-in actor for a user made in the database: a token for that account."""
    from app.modules.identity.security import create_access_token

    token = create_access_token(user_id)
    return Actor(user_id, {"Authorization": f"Bearer {token}"})


async def test_attention_counts_only_this_organizations_work(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    mine = await _shop(client, db_session)
    theirs = await _shop(client, db_session)
    await _person(db_session, mine.school_id)  # waiting for verification
    await _person(db_session, mine.school_id, complete=False)  # not yet: no year
    await _person(db_session, mine.school_id, verified=True)
    await _person(db_session, theirs.school_id)
    await _paid_and_sent(client, mine)
    await _paid_and_sent(client, mine)
    await _paid_and_sent(client, theirs)
    _, to_refund, _ = await _paid_and_sent(client, mine)
    assert (await _act(client, mine.admin, to_refund["id"], "confirm-manual")).status_code == 200
    assert (
        await _act(
            client,
            mine.admin,
            to_refund["id"],
            "organizer-cancel",
            reason="cannot attend",
            refund=True,
        )
    ).status_code == 200
    await _create(client, mine.admin, None, organization_id=str(mine.school_id))  # a draft
    await _create(client, theirs.admin, None, organization_id=str(theirs.school_id))

    a = (await _get(client, mine.admin)).json()["attention"]

    assert a["verification_requests_waiting"] == 1
    assert a["payments_waiting_confirmation"] == 2
    assert a["refunds_due"] == 1
    assert a["events_in_draft"] == 1
    assert a["reports_open"] is None


async def test_upcoming_events_are_the_next_five_published_with_their_seats(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    shop = await _shop(client, db_session, capacity=10)
    await _paid_and_sent(client, shop, names=("A", "B"))
    _, b, _ = await _paid_and_sent(client, shop)
    await _act(client, shop.admin, b["id"], "mark-paid", reason="cash")
    soon = datetime.now(UTC) + timedelta(days=2)
    for i in range(6):
        ev = await _create(
            client,
            shop.admin,
            None,
            organization_id=str(shop.school_id),
            title=f"Later {i}",
            capacity=5,
            starts_at=(soon + timedelta(days=i)).isoformat(),
            ends_at=(soon + timedelta(days=i, hours=2)).isoformat(),
        )
        assert (await _act_publish(client, shop.admin, ev["id"])).status_code == 200

    upcoming = (await _get(client, shop.admin)).json()["upcoming_events"]

    assert len(upcoming) == 5
    assert [e["title"] for e in upcoming] == [f"Later {i}" for i in range(5)]
    assert all(e["capacity"] == 5 and e["confirmed_seats"] == 0 for e in upcoming)
    assert set(upcoming[0]) == {"id", "title", "starts_at", "confirmed_seats", "capacity"}


async def _act_publish(client: AsyncClient, admin: Actor, event_id: str) -> Any:
    return await client.post(f"{API}/events/{event_id}/publish", headers=admin.headers)


async def test_seats_confirmed_and_capacity_are_reported(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    shop = await _shop(client, db_session, capacity=10)
    _, b, _ = await _paid_and_sent(client, shop, names=("A", "B"))
    await _act(client, shop.admin, b["id"], "mark-paid", reason="cash")
    await _paid_and_sent(client, shop)  # held, not confirmed

    only = (await _get(client, shop.admin)).json()["upcoming_events"]

    assert [(e["confirmed_seats"], e["capacity"]) for e in only] == [(2, 10)]


async def test_signups_per_day_has_one_entry_for_every_day_of_the_period(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    school, admin = await _run_school(client, db_session, Role.SCHOOL_ADMIN)
    await _person(db_session, school.id, days_ago=0.1)
    await _person(db_session, school.id, days_ago=0.1)
    await _person(db_session, school.id, days_ago=3.5)
    await _person(db_session, school.id, days_ago=40)  # outside 30 days, inside 90

    d30 = (await _get(client, admin, period="30d")).json()["signups_per_day"]
    d90 = (await _get(client, admin, period="90d")).json()["signups_per_day"]
    d365 = (await _get(client, admin, period="365d")).json()["signups_per_day"]

    assert (len(d30), len(d90), len(d365)) == (30, 90, 365)
    days = [x["day"] for x in d30]
    assert days == sorted(days) and len(set(days)) == 30
    assert days[-1] == datetime.now(UTC).date().isoformat()
    assert sum(x["count"] for x in d30) == 3
    assert sum(x["count"] for x in d90) == 4


async def test_the_last_eight_audit_entries_are_only_those_the_caller_may_see(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    mine, admin = await _run_school(client, db_session, Role.SCHOOL_ADMIN)
    other, other_admin = await _run_school(client, db_session, Role.SCHOOL_ADMIN)
    base = datetime.now(UTC) - timedelta(hours=1)
    for i in range(10):
        for school, tag in ((mine, "mine"), (other, "theirs")):
            db_session.add(
                AuditLogEntry(
                    actor_user_id=admin.user_id,
                    action=f"test.{tag}.{i}",
                    target_type="thing",
                    context={"organization_id": str(school.id), "reason": SECRET_NAME},
                    created_at=base + timedelta(minutes=i),
                )
            )
    db_session.add(  # a platform-wide action with no organization
        AuditLogEntry(actor_user_id=None, action="test.platform", target_type="user", context={})
    )
    await db_session.flush()
    platform = await _platform_admin(client, db_session)

    mine_rows = (await _get(client, admin)).json()["recent_audit"]
    their_rows = (await _get(client, other_admin)).json()["recent_audit"]
    all_rows = (await _get(client, platform)).json()["recent_audit"]

    assert [r["action"] for r in mine_rows] == [f"test.mine.{i}" for i in range(9, 1, -1)]
    assert all(r["organization_id"] == str(mine.id) for r in mine_rows)
    assert all(r["action"].startswith("test.theirs") for r in their_rows)
    assert len(all_rows) == 8
    assert all_rows[0]["action"] == "test.platform"  # the newest of everything
    assert SECRET_NAME not in json.dumps([mine_rows, their_rows, all_rows])
    assert set(mine_rows[0]) == {
        "id",
        "action",
        "target_type",
        "target_id",
        "actor_user_id",
        "organization_id",
        "created_at",
    }


async def test_the_answer_holds_no_names_or_emails(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    shop = await _shop(client, db_session)
    for _ in range(3):
        await _person(db_session, shop.school_id, verified=True)
    await _paid_and_sent(client, shop, names=("Zed Hiddenname",))
    platform = await _platform_admin(client, db_session)

    for who, org in ((shop.admin, None), (shop.manager, shop.school_id), (platform, None)):
        text_ = (await _get(client, who, org)).text
        assert SECRET_NAME not in text_ and "Hiddenname" not in text_
        assert "@" not in text_ and "example.com" not in text_
        assert "full_name" not in text_ and "email" not in text_


# ---------------------------------------------------------------------- cache and limit


async def test_the_answer_is_kept_for_a_minute_and_then_recounted(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    school, admin = await _run_school(client, db_session, Role.SCHOOL_ADMIN)
    await _person(db_session, school.id)
    first = (await _get(client, admin)).json()
    await _person(db_session, school.id)

    cached = (await _get(client, admin)).json()
    redis = get_redis_client()
    keys = await redis.keys("admin_overview:*")
    ttl = await redis.ttl(keys[0])
    await _flush_cache()
    fresh = (await _get(client, admin)).json()

    assert first["totals"]["members"]["value"] == 1
    assert cached == first
    assert len(keys) == 1 and 0 < ttl <= 60
    assert fresh["totals"]["members"]["value"] == 2


async def test_two_organizations_never_share_a_cached_answer(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    a, admin_a = await _run_school(client, db_session, Role.SCHOOL_ADMIN)
    b, admin_b = await _run_school(client, db_session, Role.SCHOOL_ADMIN)
    await _person(db_session, a.id)
    for _ in range(2):
        await _person(db_session, b.id)

    first_a = await _get(client, admin_a)
    first_b = await _get(client, admin_b)
    platform = await _platform_admin(client, db_session)
    for_b_by_platform = await _get(client, platform, b.id)
    mod = await _make_actor(client)
    await _grant(db_session, mod.user_id, Role.MODERATOR, None)
    moderator = await _get(client, mod)

    assert first_a.json()["totals"]["members"]["value"] == 1
    assert first_b.json()["totals"]["members"]["value"] == 2
    assert for_b_by_platform.json()["totals"]["members"]["value"] == 2
    assert moderator.json()["totals"] is None  # not served the platform's or a school's answer


async def test_the_dashboard_is_rate_limited_per_person(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    school, admin = await _run_school(client, db_session, Role.SCHOOL_ADMIN)
    other = await _make_actor(client)
    await _grant(db_session, other.user_id, Role.EVENT_MANAGER, school.id)

    codes = [(await _get(client, admin)).status_code for _ in range(31)]

    assert codes[:30] == [200] * 30 and codes[30] == 429
    assert (await _get(client, other)).status_code == 200  # someone else is not slowed down


async def test_it_only_reads(client: AsyncClient, db_session: AsyncSession) -> None:
    _, admin = await _run_school(client, db_session, Role.SCHOOL_ADMIN)

    assert (await client.post(URL, headers=admin.headers)).status_code == 405


# ------------------------------------------------- every role, every period, over HTTP

TOP_KEYS = {
    "period",
    "organization_id",
    "totals",
    "funnel",
    "attention",
    "upcoming_events",
    "signups_per_day",
    "recent_audit",
}
ATTENTION_KEYS = {
    "reports_open",
    "reports_reviewing",
    "verification_requests_waiting",
    "payments_waiting_confirmation",
    "refunds_due",
    "events_in_draft",
}
TOTAL_KEYS = {"value", "previous", "change_percent"}


def _check_shape(body: dict[str, Any], period: str, *, members: bool, reports: bool) -> None:
    days = {"30d": 30, "90d": 90, "365d": 365}[period]
    assert set(body) == TOP_KEYS and body["period"] == period
    assert set(body["attention"]) == ATTENTION_KEYS
    if not members:
        for section in ("totals", "funnel", "upcoming_events", "signups_per_day", "recent_audit"):
            assert body[section] is None
        assert all(
            body["attention"][k] is None
            for k in ATTENTION_KEYS - {"reports_open", "reports_reviewing"}
        )
    else:
        assert set(body["totals"]) == {"members", "new_members", "verified_members"}
        assert all(set(t) == TOTAL_KEYS for t in body["totals"].values())
        assert [s["step"] for s in body["funnel"]] == [
            "signed_up",
            "profile_complete",
            "verified",
            "connected",
            "booked_an_event",
        ]
        assert all(set(s) == {"step", "count", "percent_of_previous"} for s in body["funnel"])
        assert len(body["signups_per_day"]) == days
        assert all(set(d) == {"day", "count"} for d in body["signups_per_day"])
        assert all(
            set(e) == {"id", "title", "starts_at", "confirmed_seats", "capacity"}
            for e in body["upcoming_events"]
        )
        assert len(body["recent_audit"]) <= 8
        assert all(
            isinstance(body["attention"][k], int)
            for k in ATTENTION_KEYS - {"reports_open", "reports_reviewing"}
        )
    assert (body["attention"]["reports_open"] is not None) == reports


async def test_every_role_over_http_for_every_period_gets_the_right_status_and_shape(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    shop = await _shop(client, db_session)  # school with admin, manager, event, a payment
    school = shop.school_id
    for _ in range(3):
        await _person(db_session, school, verified=True)
    await _paid_and_sent(client, shop)
    db_session.add(
        AuditLogEntry(
            actor_user_id=None,
            action="t.a",
            target_type="x",
            context={"organization_id": str(school)},
        )
    )
    reporter = await _person(db_session, None)
    db_session.add(
        Report(
            reporter_user_id=reporter,
            target_type=ReportTargetType.PROFILE,
            target_id=uuid.uuid4(),
            reason="x",
        )
    )
    await db_session.flush()
    platform = await _platform_admin(client, db_session)
    moderator = await _make_actor(client)
    await _grant(db_session, moderator.user_id, Role.MODERATOR, None)
    partner = await _make_actor(client)
    await _grant(db_session, partner.user_id, Role.PARTNER_ADMIN, school)
    sports = await _make_actor(client)
    await _grant(db_session, sports.user_id, Role.SPORTS_MANAGER, school)
    plain = await _make_actor(client)

    #            who, status, sees the member sections, sees report counts
    cases: list[tuple[str, Actor | None, int, bool, bool]] = [
        ("platform admin", platform, 200, True, True),
        ("moderator", moderator, 200, False, True),
        ("school admin", shop.admin, 200, True, False),
        ("partner admin", partner, 200, True, False),
        ("event manager", shop.manager, 200, True, False),
        ("sports manager", sports, 403, False, False),
        ("plain member", plain, 403, False, False),
        ("anonymous", None, 401, False, False),
    ]
    for period in ("30d", "90d", "365d"):
        for name, who, status, members, reports in cases:
            await _flush_cache()
            r = await client.get(
                URL, params={"period": period}, headers=who.headers if who else None
            )
            assert r.status_code == status, (name, period, r.text)
            if status == 200:
                _check_shape(r.json(), period, members=members, reports=reports)
            else:
                assert "error" in r.json() or "detail" in r.json()
        # and with an organization named
        one = await client.get(
            URL,
            params={"period": period, "organization_id": str(school)},
            headers=platform.headers,
        )
        assert one.status_code == 200
        _check_shape(one.json(), period, members=True, reports=False)
        assert one.json()["organization_id"] == str(school)
