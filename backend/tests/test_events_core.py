"""Slice 5.1: events, slots, questions, consents, series, publishing, who can see and run what."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions.roles import Role
from app.modules.audit.models import AuditLogEntry
from app.modules.events import service as events_service
from app.modules.events.models import Event, EventSlot, EventStatus
from app.modules.organizations.models import Organization, OrganizationType
from tests.test_alumni_privacy import Actor, _grant, _make_actor, _make_school
from tests.test_file_upload import _encode, _photo, _upload

API = "/api/v1"


def iso(days: float = 10, hours: float = 0) -> str:
    return (datetime.now(UTC) + timedelta(days=days, hours=hours)).isoformat()


def event_body(**over: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "title": "Alumni Mixer",
        "category": "networking",
        "starts_at": iso(10),
        "ends_at": iso(10, 3),
    }
    body.update(over)
    return body


async def _run_school(
    client: AsyncClient, db: AsyncSession, role: Role
) -> tuple[Organization, Actor]:
    school = await _make_school(db)
    actor = await _make_actor(client)
    await _grant(db, actor.user_id, role, school.id)
    return school, actor


async def _platform_admin(client: AsyncClient, db: AsyncSession) -> Actor:
    actor = await _make_actor(client)
    await _grant(db, actor.user_id, Role.ADMIN, None)
    return actor


async def _create(
    client: AsyncClient, actor: Actor, school: Organization | None, **over: Any
) -> dict[str, Any]:
    body = event_body(**over)
    if school is not None:
        body.setdefault("organization_id", str(school.id))
    r = await client.post(f"{API}/events", json=body, headers=actor.headers)
    assert r.status_code == 201, r.text
    data: dict[str, Any] = r.json()
    return data


async def _publish(client: AsyncClient, admin: Actor, event_id: str) -> Response:
    return await client.post(f"{API}/events/{event_id}/publish", headers=admin.headers)


async def _published(
    client: AsyncClient, db: AsyncSession, **over: Any
) -> tuple[Organization, Actor, dict[str, Any]]:
    school, admin = await _run_school(client, db, Role.SCHOOL_ADMIN)
    ev = await _create(client, admin, school, **over)
    r = await _publish(client, admin, ev["id"])
    assert r.status_code == 200, r.text
    return school, admin, r.json()


# ------------------------------------------------------------------------- creating


async def test_an_event_manager_creates_a_draft_with_one_slot_for_the_whole_event(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    school, manager = await _run_school(client, db_session, Role.EVENT_MANAGER)
    ev = await _create(client, manager, school, capacity=40)
    assert ev["status"] == "draft"
    assert ev["can_manage"] is True
    assert len(ev["slots"]) == 1
    assert ev["slots"][0]["label"] is None
    assert ev["slots"][0]["capacity"] == 40
    assert ev["spots_left"] == 40
    assert ev["organizer"]["id"] == str(school.id)
    assert ev["visibility"] == "public"
    assert ev["hold_minutes"] == 15


async def test_nobody_else_can_create_an_event_for_an_organization(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    school = await _make_school(db_session)
    other_school, other_admin = await _run_school(client, db_session, Role.SCHOOL_ADMIN)
    member = await _make_actor(client)
    for actor in (member, other_admin):
        r = await client.post(
            f"{API}/events", json=event_body(organization_id=str(school.id)), headers=actor.headers
        )
        assert r.status_code == 403, r.text
    anon = await client.post(f"{API}/events", json=event_body(organization_id=str(school.id)))
    assert anon.status_code == 401


async def test_an_alumni_role_or_moderator_cannot_run_events(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    school = await _make_school(db_session)
    moderator = await _make_actor(client)
    await _grant(db_session, moderator.user_id, Role.MODERATOR, None)
    r = await client.post(
        f"{API}/events", json=event_body(organization_id=str(school.id)), headers=moderator.headers
    )
    assert r.status_code == 403


async def test_only_a_platform_admin_creates_an_event_run_by_the_platform(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    school, school_admin = await _run_school(client, db_session, Role.SCHOOL_ADMIN)
    r = await client.post(f"{API}/events", json=event_body(), headers=school_admin.headers)
    assert r.status_code == 403
    admin = await _platform_admin(client, db_session)
    r = await client.post(f"{API}/events", json=event_body(), headers=admin.headers)
    assert r.status_code == 201
    assert r.json()["organizer"] is None


async def test_an_event_for_a_missing_organization_is_not_found(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    admin = await _platform_admin(client, db_session)
    r = await client.post(
        f"{API}/events", json=event_body(organization_id=str(uuid.uuid4())), headers=admin.headers
    )
    assert r.status_code == 404


@pytest.mark.parametrize(
    "over",
    [
        {"ends_at": iso(9)},  # ends before it starts
        {"starts_at": "2026-12-01T10:00:00"},  # no time zone
        {"price_minor": -1},
        {"price_minor": 5000},  # paid, but the single slot has no capacity
        {"hold_minutes": 120},  # long holds are for manual-payment events only
        {"max_party_size": 5},
        {"currency": "USD"},
        {"title": "x"},
        {"registration_closes_at": iso(11)},  # after the event ends
        {"registration_opens_at": iso(5), "registration_closes_at": iso(4)},
        {"round_number": 3},  # a round without a series
    ],
)
async def test_bad_event_details_are_refused(
    client: AsyncClient, db_session: AsyncSession, over: dict[str, Any]
) -> None:
    school, manager = await _run_school(client, db_session, Role.EVENT_MANAGER)
    r = await client.post(
        f"{API}/events",
        json=event_body(organization_id=str(school.id), **over),
        headers=manager.headers,
    )
    assert r.status_code == 422, (over, r.text)


async def test_the_client_cannot_set_status_or_other_server_owned_fields(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    school, manager = await _run_school(client, db_session, Role.EVENT_MANAGER)
    ev = await _create(
        client, manager, school, status="published", created_by=str(uuid.uuid4()), seats_confirmed=9
    )
    assert ev["status"] == "draft"
    assert ev["slots"][0]["seats_confirmed"] == 0
    row = await db_session.get(Event, uuid.UUID(ev["id"]))
    assert row is not None and row.created_by == manager.user_id


# --------------------------------------------------------------------- who can see it


async def test_a_draft_is_invisible_to_everyone_except_the_people_who_run_it(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    school, manager = await _run_school(client, db_session, Role.EVENT_MANAGER)
    _, other_admin = await _run_school(client, db_session, Role.SCHOOL_ADMIN)
    member = await _make_actor(client)
    ev = await _create(client, manager, school)
    url = f"{API}/events/{ev['id']}"

    assert (await client.get(url)).status_code == 404
    assert (await client.get(url, headers=member.headers)).status_code == 404
    assert (await client.get(url, headers=other_admin.headers)).status_code == 404
    assert (await client.get(url, headers=manager.headers)).status_code == 200
    platform = await _platform_admin(client, db_session)
    assert (await client.get(url, headers=platform.headers)).status_code == 200

    listed = (await client.get(f"{API}/events", headers=member.headers)).json()
    assert ev["id"] not in [e["id"] for e in listed]


async def test_a_members_only_event_is_invisible_when_signed_out(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    school, admin = await _run_school(client, db_session, Role.SCHOOL_ADMIN)
    ev = await _create(client, admin, school, visibility="members_only")
    await _publish(client, admin, ev["id"])
    member = await _make_actor(client)
    url = f"{API}/events/{ev['id']}"

    assert (await client.get(url)).status_code == 404
    assert (await client.get(url, headers=member.headers)).status_code == 200
    assert ev["id"] not in [e["id"] for e in (await client.get(f"{API}/events")).json()]
    assert ev["id"] in [
        e["id"] for e in (await client.get(f"{API}/events", headers=member.headers)).json()
    ]


async def test_a_published_public_event_is_open_to_anyone_with_the_whole_picture(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    school, admin, ev = await _published(client, db_session, capacity=10, venue_name="Mt Kipipiri")
    r = await client.get(f"{API}/events/{ev['id']}")
    assert r.status_code == 200
    body = r.json()
    assert body["can_manage"] is False
    assert body["venue_name"] == "Mt Kipipiri"
    assert body["registration"]["state"] == "open"
    assert body["going_count"] == 0
    assert body["availability"] == "open"


# --------------------------------------------------------------- who can run it


async def test_a_manager_edits_but_only_an_admin_publishes_cancels_or_deletes(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    school, admin = await _run_school(client, db_session, Role.SCHOOL_ADMIN)
    manager = await _make_actor(client)
    await _grant(db_session, manager.user_id, Role.EVENT_MANAGER, school.id)
    ev = await _create(client, manager, school)
    url = f"{API}/events/{ev['id']}"

    r = await client.patch(url, json={"title": "Renamed"}, headers=manager.headers)
    assert r.status_code == 200 and r.json()["title"] == "Renamed"
    assert (await _publish(client, manager, ev["id"])).status_code == 403
    assert (await client.delete(url, headers=manager.headers)).status_code == 403
    assert (await _publish(client, admin, ev["id"])).status_code == 200
    r = await client.post(
        f"{url}/cancel", json={"reason": "Venue flooded"}, headers=manager.headers
    )
    assert r.status_code == 403
    r = await client.post(f"{url}/cancel", json={"reason": "Venue flooded"}, headers=admin.headers)
    assert r.status_code == 200 and r.json()["status"] == "cancelled"


async def test_another_schools_admin_cannot_touch_this_schools_published_event(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _, _, ev = await _published(client, db_session)
    _, rival = await _run_school(client, db_session, Role.SCHOOL_ADMIN)
    url = f"{API}/events/{ev['id']}"
    assert (
        await client.patch(url, json={"title": "Mine now"}, headers=rival.headers)
    ).status_code == 403
    assert (await client.post(f"{url}/close", headers=rival.headers)).status_code == 403
    assert (
        await client.post(
            f"{url}/slots",
            json={"starts_at": iso(10), "ends_at": iso(10, 1), "capacity": 5},
            headers=rival.headers,
        )
    ).status_code == 403
    assert (
        await client.post(
            f"{url}/questions",
            json={"key": "diet", "label": "Diet", "kind": "text"},
            headers=rival.headers,
        )
    ).status_code == 403


async def test_a_member_cannot_run_a_public_event(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _, _, ev = await _published(client, db_session)
    member = await _make_actor(client)
    r = await client.patch(
        f"{API}/events/{ev['id']}", json={"title": "Hijack"}, headers=member.headers
    )
    assert r.status_code == 403


async def test_a_platform_event_is_run_by_platform_admins_only(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    admin = await _platform_admin(client, db_session)
    ev = await _create(client, admin, None)
    _, school_admin = await _run_school(client, db_session, Role.SCHOOL_ADMIN)
    r = await client.patch(
        f"{API}/events/{ev['id']}", json={"title": "x" * 5}, headers=school_admin.headers
    )
    assert r.status_code == 404  # a draft they cannot even see
    assert (await _publish(client, admin, ev["id"])).status_code == 200
    r = await client.patch(
        f"{API}/events/{ev['id']}", json={"title": "x" * 5}, headers=school_admin.headers
    )
    assert r.status_code == 403


# -------------------------------------------------------------------------- lifecycle


async def test_publishing_needs_slots_a_future_end_and_capacity_for_paid_events(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    school, admin = await _run_school(client, db_session, Role.SCHOOL_ADMIN)
    ev = await _create(client, admin, school)
    slot_id = ev["slots"][0]["id"]
    url = f"{API}/events/{ev['id']}"

    assert (await client.delete(f"{url}/slots/{slot_id}", headers=admin.headers)).status_code == 204
    r = await _publish(client, admin, ev["id"])
    assert r.status_code == 422 and r.json()["error"]["code"] == "no_slots"

    # a paid event with an unlimited slot cannot be published
    paid = await _create(client, admin, school, capacity=5)
    await client.patch(
        f"{API}/events/{paid['id']}/slots/{paid['slots'][0]['id']}",
        json={"capacity": None},
        headers=admin.headers,
    )
    r = await client.patch(
        f"{API}/events/{paid['id']}", json={"price_minor": 350000}, headers=admin.headers
    )
    assert r.status_code == 422 and r.json()["error"]["code"] == "capacity_required"

    row = await db_session.get(Event, uuid.UUID(paid["id"]))
    assert row is not None
    row.ends_at = datetime.now(UTC) - timedelta(days=1)
    row.starts_at = datetime.now(UTC) - timedelta(days=2)
    await db_session.flush()
    r = await _publish(client, admin, paid["id"])
    assert r.status_code == 422 and r.json()["error"]["code"] == "event_in_past"


async def test_the_lifecycle_close_reopen_complete_and_the_dead_ends(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    school, admin, ev = await _published(client, db_session, capacity=10)
    url = f"{API}/events/{ev['id']}"

    r = await client.post(f"{url}/close", headers=admin.headers)
    assert r.json()["registration"]["state"] == "closed"
    assert (await client.post(f"{url}/close", headers=admin.headers)).status_code == 409
    r = await client.post(f"{url}/reopen", headers=admin.headers)
    assert r.json()["registration"]["state"] == "open"

    assert (
        await client.post(f"{url}/complete", headers=admin.headers)
    ).status_code == 409  # not started

    row = await db_session.get(Event, uuid.UUID(ev["id"]))
    assert row is not None
    row.starts_at = datetime.now(UTC) - timedelta(hours=1)
    await db_session.flush()
    r = await client.post(f"{url}/complete", headers=admin.headers)
    assert r.status_code == 200 and r.json()["status"] == "completed"
    assert (
        await client.patch(url, json={"title": "Late edit"}, headers=admin.headers)
    ).status_code == 409
    assert (
        await client.post(f"{url}/cancel", json={"reason": "too late"}, headers=admin.headers)
    ).status_code == 409


async def test_only_a_draft_can_be_deleted(client: AsyncClient, db_session: AsyncSession) -> None:
    school, admin, ev = await _published(client, db_session)
    assert (
        await client.delete(f"{API}/events/{ev['id']}", headers=admin.headers)
    ).status_code == 409
    draft = await _create(client, admin, school)
    assert (
        await client.delete(f"{API}/events/{draft['id']}", headers=admin.headers)
    ).status_code == 204
    assert (
        await client.get(f"{API}/events/{draft['id']}", headers=admin.headers)
    ).status_code == 404


def test_registration_state_follows_status_and_the_registration_window() -> None:
    now = datetime(2026, 11, 1, 12, tzinfo=UTC)

    def ev(**kw: Any) -> Event:
        base: dict[str, Any] = {
            "status": EventStatus.PUBLISHED,
            "starts_at": now + timedelta(days=5),
            "ends_at": now + timedelta(days=5, hours=3),
            "registration_opens_at": None,
            "registration_closes_at": None,
        }
        base.update(kw)
        return Event(**base)

    assert events_service.registration_state(ev(), now) == "open"
    assert events_service.registration_state(ev(status=EventStatus.DRAFT), now) == "draft"
    assert events_service.registration_state(ev(status=EventStatus.CANCELLED), now) == "cancelled"
    assert events_service.registration_state(ev(status=EventStatus.CLOSED), now) == "closed"
    assert events_service.registration_state(ev(status=EventStatus.COMPLETED), now) == "ended"
    assert events_service.registration_state(ev(ends_at=now - timedelta(minutes=1)), now) == "ended"
    assert (
        events_service.registration_state(ev(registration_opens_at=now + timedelta(hours=1)), now)
        == "not_open_yet"
    )
    assert (
        events_service.registration_state(ev(registration_closes_at=now), now) == "closed"
    )  # closing instant is already closed


def test_availability_words() -> None:
    assert events_service.availability_of(None, None) == "open"
    assert events_service.availability_of(40, 0) == "full"
    assert events_service.availability_of(40, 3) == "few_left"
    assert events_service.availability_of(40, 4) == "few_left"  # 10% of 40
    assert events_service.availability_of(40, 5) == "open"
    assert events_service.availability_of(10, 3) == "few_left"
    assert events_service.seats_left(10, 6, 3) == 1
    assert events_service.seats_left(10, 9, 5) == 0  # never negative


# --------------------------------------------------------------------------- listing


async def test_listing_filters_orders_paginates_and_counts(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    school, admin = await _run_school(client, db_session, Role.SCHOOL_ADMIN)
    ids = {}
    for name, days, cat in (
        ("Late", 30, "forum"),
        ("Soon", 5, "networking"),
        ("Middle", 12, "networking"),
    ):
        ev = await _create(
            client,
            admin,
            school,
            title=name,
            starts_at=iso(days),
            ends_at=iso(days, 2),
            category=cat,
        )
        await _publish(client, admin, ev["id"])
        ids[name] = ev["id"]

    r = await client.get(f"{API}/events", params={"organization_id": str(school.id)})
    assert [e["title"] for e in r.json()] == ["Soon", "Middle", "Late"]
    assert r.headers["X-Total-Count"] == "3"

    r = await client.get(
        f"{API}/events", params={"organization_id": str(school.id), "category": "networking"}
    )
    assert [e["title"] for e in r.json()] == ["Soon", "Middle"]
    r = await client.get(
        f"{API}/events", params={"organization_id": str(school.id), "limit": 1, "offset": 1}
    )
    assert [e["title"] for e in r.json()] == ["Middle"]
    assert r.headers["X-Total-Count"] == "3"
    r = await client.get(f"{API}/events", params={"organization_id": str(school.id), "q": "mid"})
    assert [e["title"] for e in r.json()] == ["Middle"]
    # a wildcard is just a character
    r = await client.get(f"{API}/events", params={"organization_id": str(school.id), "q": "%"})
    assert r.json() == []

    # past events are separate
    row = await db_session.get(Event, uuid.UUID(ids["Soon"]))
    assert row is not None
    row.starts_at = datetime.now(UTC) - timedelta(days=3)
    row.ends_at = datetime.now(UTC) - timedelta(days=2)
    await db_session.flush()
    upcoming = await client.get(f"{API}/events", params={"organization_id": str(school.id)})
    assert "Soon" not in [e["title"] for e in upcoming.json()]
    past = await client.get(
        f"{API}/events", params={"organization_id": str(school.id), "past": "true"}
    )
    assert [e["title"] for e in past.json()] == ["Soon"]


async def test_the_manage_list_shows_only_your_organizations_drafts(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    school, manager = await _run_school(client, db_session, Role.EVENT_MANAGER)
    other, other_admin = await _run_school(client, db_session, Role.SCHOOL_ADMIN)
    mine = await _create(client, manager, school, title="My draft")
    theirs = await _create(client, other_admin, other, title="Their draft")

    r = await client.get(f"{API}/events", params={"manage": "true"}, headers=manager.headers)
    titles = [e["title"] for e in r.json()]
    assert "My draft" in titles and "Their draft" not in titles

    platform = await _platform_admin(client, db_session)
    r = await client.get(
        f"{API}/events", params={"manage": "true", "limit": 100}, headers=platform.headers
    )
    assert {mine["id"], theirs["id"]} <= {e["id"] for e in r.json()}

    nobody = await _make_actor(client)
    r = await client.get(f"{API}/events", params={"manage": "true"}, headers=nobody.headers)
    assert r.json() == []
    assert (await client.get(f"{API}/events", params={"manage": "true"})).status_code == 403


# ---------------------------------------------------------------------------- slots


async def test_a_golf_style_event_has_four_slots_with_their_own_capacity(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    school, admin = await _run_school(client, db_session, Role.SCHOOL_ADMIN)
    day = [(6, 30, 7, 30), (7, 40, 8, 40), (11, 20, 12, 20), (12, 30, 13, 30)]
    base = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=14)
    slots = [
        {
            "label": f"{a:02d}:{b:02d} to {c:02d}:{d:02d}",
            "starts_at": (base + timedelta(hours=a, minutes=b)).isoformat(),
            "ends_at": (base + timedelta(hours=c, minutes=d)).isoformat(),
            "capacity": 40,
            "position": i,
        }
        for i, (a, b, c, d) in enumerate(day)
    ]
    ev = await _create(
        client,
        admin,
        school,
        title="Golf Day",
        category="golf_tournament",
        starts_at=slots[0]["starts_at"],
        ends_at=slots[-1]["ends_at"],
        price_minor=350000,
        max_party_size=4,
        slots=slots,
    )
    assert [s["capacity"] for s in ev["slots"]] == [40, 40, 40, 40]
    assert ev["spots_left"] == 160
    assert (await _publish(client, admin, ev["id"])).status_code == 200


async def test_slot_capacity_cannot_drop_below_what_is_taken_or_held(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    school, admin = await _run_school(client, db_session, Role.SCHOOL_ADMIN)
    ev = await _create(client, admin, school, capacity=10)
    slot_id = uuid.UUID(ev["slots"][0]["id"])
    slot = await db_session.get(EventSlot, slot_id)
    assert slot is not None
    slot.seats_confirmed, slot.seats_held = 4, 2
    await db_session.flush()
    url = f"{API}/events/{ev['id']}/slots/{slot_id}"

    r = await client.patch(url, json={"capacity": 5}, headers=admin.headers)
    assert r.status_code == 409 and r.json()["error"]["code"] == "capacity_below_taken"
    assert (await client.patch(url, json={"capacity": 6}, headers=admin.headers)).status_code == 200
    assert (await client.delete(url, headers=admin.headers)).status_code == 409


async def test_a_published_event_keeps_its_last_slot_and_slots_belong_to_their_event(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    school, admin, ev = await _published(client, db_session, capacity=10)
    other = await _create(client, admin, school, capacity=10)
    only = ev["slots"][0]["id"]
    r = await client.delete(f"{API}/events/{ev['id']}/slots/{only}", headers=admin.headers)
    assert r.status_code == 409 and r.json()["error"]["code"] == "last_slot"
    # a slot id from another event is simply not found
    r = await client.patch(
        f"{API}/events/{ev['id']}/slots/{other['slots'][0]['id']}",
        json={"capacity": 3},
        headers=admin.headers,
    )
    assert r.status_code == 404


async def test_the_database_refuses_to_oversell_a_slot_on_its_own(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    school, admin = await _run_school(client, db_session, Role.SCHOOL_ADMIN)
    ev = await _create(client, admin, school, capacity=3)
    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            await db_session.execute(
                text("UPDATE event_slots SET seats_confirmed = 2, seats_held = 2 WHERE id = :i"),
                {"i": ev["slots"][0]["id"]},
            )


# ------------------------------------------------------------- questions and consents


async def test_questions_are_validated_and_keys_are_unique(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    school, admin = await _run_school(client, db_session, Role.SCHOOL_ADMIN)
    ev = await _create(client, admin, school)
    url = f"{API}/events/{ev['id']}/questions"

    bad_cases = [
        {"key": "team", "label": "Team", "kind": "choice"},  # choice without options
        {
            "key": "team",
            "label": "Team",
            "kind": "choice",
            "options": [{"value": "a", "label": "A"}, {"value": "a", "label": "B"}],
        },
        {"key": "name", "label": "Name", "kind": "text", "options": [{"value": "a", "label": "A"}]},
        {"key": "Bad Key", "label": "x", "kind": "text"},
    ]
    for body in bad_cases:
        assert (await client.post(url, json=body, headers=admin.headers)).status_code == 422, body

    ok = {
        "key": "golf_team",
        "label": "Team",
        "kind": "choice",
        "required": True,
        "asked_of": "each_participant",
        "options": [
            {"value": "yengolf_alumni", "label": "YENGOLF Alumni"},
            {"value": "alumni_challenge", "label": "Alumni Challenge"},
        ],
    }
    r = await client.post(url, json=ok, headers=admin.headers)
    assert r.status_code == 201
    qid = r.json()["id"]
    assert (await client.post(url, json=ok, headers=admin.headers)).status_code == 409

    r = await client.patch(
        f"{url}/{qid}", json={"label": "Which team?", "required": False}, headers=admin.headers
    )
    assert r.json()["label"] == "Which team?" and r.json()["required"] is False
    assert r.json()["key"] == "golf_team"
    detail = (await client.get(f"{API}/events/{ev['id']}", headers=admin.headers)).json()
    assert [q["key"] for q in detail["questions"]] == ["golf_team"]
    assert (await client.delete(f"{url}/{qid}", headers=admin.headers)).status_code == 204


async def test_changing_a_consents_words_makes_a_new_version(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    school, admin = await _run_school(client, db_session, Role.SCHOOL_ADMIN)
    ev = await _create(client, admin, school)
    url = f"{API}/events/{ev['id']}/consents"
    r = await client.post(url, json={"key": "filming", "text": "We film."}, headers=admin.headers)
    assert r.status_code == 201 and r.json()["version"] == 1 and r.json()["required"] is True
    cid = r.json()["id"]
    same = await client.patch(f"{url}/{cid}", json={"text": "We film."}, headers=admin.headers)
    assert same.json()["version"] == 1
    changed = await client.patch(
        f"{url}/{cid}", json={"text": "We film and post."}, headers=admin.headers
    )
    assert changed.json()["version"] == 2
    assert (
        await client.post(url, json={"key": "filming", "text": "dup"}, headers=admin.headers)
    ).status_code == 409


# --------------------------------------------------------------------------- series


async def test_a_series_groups_rounds_and_each_round_number_is_used_once(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    school, admin = await _run_school(client, db_session, Role.SCHOOL_ADMIN)
    r = await client.post(
        f"{API}/event-series",
        json={"organization_id": str(school.id), "title": "Masters 2026"},
        headers=admin.headers,
    )
    assert r.status_code == 201
    sid = r.json()["id"]
    one = await _create(client, admin, school, title="Round 1", series_id=sid, round_number=1)
    await _publish(client, admin, one["id"])
    two = await _create(
        client, admin, school, title="Round 2 (hidden)", series_id=sid, round_number=2
    )

    dup = await client.post(
        f"{API}/events",
        json=event_body(organization_id=str(school.id), series_id=sid, round_number=1),
        headers=admin.headers,
    )
    assert dup.status_code == 409
    assert one["series"] == {"id": sid, "title": "Masters 2026", "round_number": 1}

    public = await client.get(f"{API}/event-series/{sid}")
    assert [x["title"] for x in public.json()["rounds"]] == ["Round 1"]  # the draft stays hidden
    mine = await client.get(f"{API}/event-series/{sid}", headers=admin.headers)
    assert [x["round_number"] for x in mine.json()["rounds"]] == [1, 2]
    assert two["series"]["round_number"] == 2
    assert sid in [
        s["id"] for s in (await client.get(f"{API}/event-series", headers=admin.headers)).json()
    ]


async def test_a_series_belongs_to_one_organization(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    school, admin = await _run_school(client, db_session, Role.SCHOOL_ADMIN)
    other, other_admin = await _run_school(client, db_session, Role.SCHOOL_ADMIN)
    sid = (
        await client.post(
            f"{API}/event-series",
            json={"organization_id": str(school.id), "title": "Ours"},
            headers=admin.headers,
        )
    ).json()["id"]
    r = await client.post(
        f"{API}/events",
        json=event_body(organization_id=str(other.id), series_id=sid, round_number=1),
        headers=other_admin.headers,
    )
    assert r.status_code == 404
    r = await client.post(
        f"{API}/event-series",
        json={"organization_id": str(school.id), "title": "Steal"},
        headers=other_admin.headers,
    )
    assert r.status_code == 403
    assert (await client.get(f"{API}/event-series/{sid}")).status_code == 404  # no visible rounds


# --------------------------------------------------------------------------- posters


async def test_a_poster_must_be_uploaded_for_the_same_organizer(
    client: AsyncClient, db_session: AsyncSession, storage: Any
) -> None:
    school, manager = await _run_school(client, db_session, Role.EVENT_MANAGER)
    other, other_manager = await _run_school(client, db_session, Role.EVENT_MANAGER)
    ev = await _create(client, manager, school)
    png = _encode(_photo(), "PNG")

    mine = await _upload(client, manager, png, purpose="event_poster", organization_id=school.id)
    theirs = await _upload(
        client, other_manager, png, purpose="event_poster", organization_id=other.id
    )
    assert mine.status_code == 201 and theirs.status_code == 201

    url = f"{API}/events/{ev['id']}/poster"
    assert (
        await client.put(url, json={"file_id": theirs.json()["id"]}, headers=manager.headers)
    ).status_code == 404
    r = await client.put(url, json={"file_id": mine.json()["id"]}, headers=manager.headers)
    assert r.status_code == 200 and r.json()["poster_url"].endswith(f"{mine.json()['id']}/content")

    # a poster made for a school cannot be put on a platform event
    admin = await _platform_admin(client, db_session)
    platform_ev = await _create(client, admin, None)
    r = await client.put(
        f"{API}/events/{platform_ev['id']}/poster",
        json={"file_id": mine.json()["id"]},
        headers=admin.headers,
    )
    assert r.status_code == 404

    cleared = await client.delete(url, headers=manager.headers)
    assert cleared.json()["poster_url"] is None


# ----------------------------------------------------------------------------- audit


async def test_organizer_actions_are_audited_under_the_organization(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    school, admin = await _run_school(client, db_session, Role.SCHOOL_ADMIN)
    ev = await _create(client, admin, school)
    await _publish(client, admin, ev["id"])
    await client.post(
        f"{API}/events/{ev['id']}/cancel", json={"reason": "Rain"}, headers=admin.headers
    )

    actions = [
        e.action
        for e in await db_session.scalars(
            select(AuditLogEntry).where(AuditLogEntry.context["event_id"].astext == ev["id"])
        )
    ]
    assert {"event.create", "event.publish", "event.cancel"} <= set(actions)

    # visible to this school's admin, invisible to another school's admin
    _, rival = await _run_school(client, db_session, Role.SCHOOL_ADMIN)
    mine = await client.get(f"{API}/audit-log?limit=200", headers=admin.headers)
    assert "event.publish" in [e["action"] for e in mine.json()]
    theirs = await client.get(f"{API}/audit-log?limit=200", headers=rival.headers)
    assert "event.publish" not in [e["action"] for e in theirs.json()]


async def test_a_partner_can_run_events_too(client: AsyncClient, db_session: AsyncSession) -> None:
    partner = Organization(
        type=OrganizationType.PARTNER, name="p", slug=f"p-{uuid.uuid4().hex[:8]}"
    )
    db_session.add(partner)
    await db_session.flush()
    admin = await _make_actor(client)
    await _grant(db_session, admin.user_id, Role.PARTNER_ADMIN, partner.id)
    ev = await _create(client, admin, partner, title="Partner night")
    assert (await _publish(client, admin, ev["id"])).status_code == 200
