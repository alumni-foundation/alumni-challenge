"""Slice 5.2: booking places, free RSVPs, holds, cancelling, and keeping seat counts honest."""

import uuid
from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors.exceptions import ValidationError
from app.core.permissions.roles import Role
from app.modules.bookings import seats
from app.modules.bookings import service as bookings_service
from app.modules.bookings.models import Booking, BookingStatus
from app.modules.bookings.schemas import BookingCreate, ParticipantInput
from app.modules.domain_events.models import DomainEvent
from app.modules.events.models import EventSlot
from app.modules.identity.models import User
from tests.test_alumni_privacy import PASSWORD, Actor, _make_actor
from tests.test_events_core import API, _create, _publish, _run_school, iso

pytestmark = pytest.mark.asyncio


async def _event(
    client: AsyncClient, db: AsyncSession, **over: Any
) -> tuple[Actor, dict[str, Any]]:
    school, admin = await _run_school(client, db, Role.SCHOOL_ADMIN)
    over.setdefault("capacity", 10)
    over.setdefault("max_party_size", 4)
    ev = await _create(client, admin, school, **over)
    r = await _publish(client, admin, ev["id"])
    assert r.status_code == 200, r.text
    return admin, r.json()


def _body(slot_id: str, names: tuple[str, ...] = ("Ann Alum",), **over: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "slot_id": slot_id,
        "participants": [{"full_name": n} for n in names],
    }
    if len(names) > 1:
        body["others_consent_confirmed"] = True
    body.update(over)
    return body


async def _book(
    client: AsyncClient,
    actor: Actor,
    event: dict[str, Any],
    *,
    names: tuple[str, ...] = ("Ann Alum",),
    key: str | None = None,
    **over: Any,
) -> Response:
    return await client.post(
        f"{API}/events/{event['id']}/bookings",
        json=_body(event["slots"][0]["id"], names, **over),
        headers={**actor.headers, "Idempotency-Key": key or uuid.uuid4().hex},
    )


async def _slot(db: AsyncSession, event: dict[str, Any]) -> EventSlot:
    slot = await db.get(EventSlot, uuid.UUID(event["slots"][0]["id"]), populate_existing=True)
    assert slot is not None
    return slot


async def _counters(db: AsyncSession, event: dict[str, Any]) -> tuple[int, int]:
    slot = await _slot(db, event)
    return slot.seats_confirmed, slot.seats_held


async def _assert_counters_true(db: AsyncSession, event: dict[str, Any]) -> None:
    slot = await _slot(db, event)
    assert (slot.seats_confirmed, slot.seats_held) == await seats.recount(db, slot.id)


async def _pretend_paid(db: AsyncSession, event: dict[str, Any], booking_id: str) -> None:
    """Moves a held booking to confirmed, as a payment would (payments arrive in a later slice)."""
    await db.execute(
        text("UPDATE event_slots SET seats_held = 0, seats_confirmed = 1 WHERE id = :s"),
        {"s": event["slots"][0]["id"]},
    )
    await db.execute(
        text("UPDATE bookings SET status = 'confirmed', hold_expires_at = NULL WHERE id = :b"),
        {"b": booking_id},
    )


# ----------------------------------------------------------------------- free RSVP


async def test_a_free_booking_is_confirmed_straight_away(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _, event = await _event(client, db_session)
    member = await _make_actor(client)
    r = await _book(client, member, event, names=("Ann Alum", "Ben Friend"))
    assert r.status_code == 201, r.text
    b = r.json()
    assert b["status"] == "confirmed"
    assert b["party_size"] == 2
    assert b["amount_minor"] == 0
    assert b["hold_expires_at"] is None
    assert b["reference"].startswith("AC-") and len(b["reference"]) == 11
    assert [p["position"] for p in b["participants"]] == [1, 2]
    assert await _counters(db_session, event) == (2, 0)
    queued = (
        await db_session.scalars(
            select(DomainEvent).where(DomainEvent.event_type == "booking.confirmed")
        )
    ).all()
    assert [e.payload["booking_id"] for e in queued] == [b["id"]]


async def test_the_booker_is_participant_one_and_their_email_comes_from_the_account(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _, event = await _event(client, db_session)
    member = await _make_actor(client)
    r = await _book(
        client,
        member,
        event,
        participants=[{"full_name": "Ann Alum", "email": "someone-else@example.com"}],
    )
    assert r.status_code == 201, r.text
    first = r.json()["participants"][0]
    user = await db_session.get(User, member.user_id)
    assert user is not None
    assert first["email"] == user.email
    assert first["claimed"] is False


async def test_booking_needs_sign_in_and_an_idempotency_key(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _, event = await _event(client, db_session)
    member = await _make_actor(client)
    url = f"{API}/events/{event['id']}/bookings"
    body = _body(event["slots"][0]["id"])
    anon = await client.post(url, json=body, headers={"Idempotency-Key": "k1"})
    assert anon.status_code == 401
    no_key = await client.post(url, json=body, headers=member.headers)
    assert no_key.status_code == 422


async def test_the_price_cannot_be_chosen_by_the_booker(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _, event = await _event(client, db_session, price_minor=150_000)
    member = await _make_actor(client)
    r = await _book(client, member, event, names=("Ann", "Ben"), amount_minor=1, price_minor=1)
    assert r.status_code == 201, r.text
    b = r.json()
    assert b["unit_price_minor"] == 150_000
    assert b["amount_minor"] == 300_000


# ------------------------------------------------------------------ who can book what


async def test_a_draft_or_members_only_event_is_invisible_to_those_who_cannot_see_it(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    school, admin = await _run_school(client, db_session, Role.SCHOOL_ADMIN)
    draft = await _create(client, admin, school, capacity=5)
    member = await _make_actor(client)
    r = await client.post(
        f"{API}/events/{draft['id']}/bookings",
        json=_body(draft["slots"][0]["id"]),
        headers={**member.headers, "Idempotency-Key": "k"},
    )
    assert r.status_code == 404


async def test_registration_windows_are_enforced(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    member = await _make_actor(client)
    _, not_yet = await _event(client, db_session, registration_opens_at=iso(2))
    r = await _book(client, member, not_yet)
    assert r.status_code == 409 and r.json()["error"]["code"] == "registration_not_open_yet"

    _, event = await _event(client, db_session)
    await db_session.execute(
        text("UPDATE events SET status = 'closed' WHERE id = :i"), {"i": event["id"]}
    )
    r = await _book(client, member, event)
    assert r.status_code == 409 and r.json()["error"]["code"] == "registration_closed"

    _, ended = await _event(client, db_session)
    await db_session.execute(
        text(
            "UPDATE events SET starts_at = now() - interval '3 hours', "
            "ends_at = now() - interval '1 hour' WHERE id = :i"
        ),
        {"i": ended["id"]},
    )
    r = await _book(client, member, ended)
    assert r.status_code == 409 and r.json()["error"]["code"] == "registration_ended"


async def test_group_rules(client: AsyncClient, db_session: AsyncSession) -> None:
    member = await _make_actor(client)
    _, solo = await _event(client, db_session, max_party_size=1)
    r = await _book(client, member, solo, names=("Ann", "Ben"))
    assert r.status_code == 422 and r.json()["error"]["code"] == "party_too_large"

    _, event = await _event(client, db_session)
    r = await _book(client, member, event, names=("Ann", "Ben"), others_consent_confirmed=False)
    assert r.status_code == 422 and r.json()["error"]["code"] == "others_consent_required"

    five = await client.post(
        f"{API}/events/{event['id']}/bookings",
        json=_body(event["slots"][0]["id"], tuple("ABCDE")),
        headers={**member.headers, "Idempotency-Key": "five"},
    )
    assert five.status_code == 422

    other_event_slot = await client.post(
        f"{API}/events/{event['id']}/bookings",
        json=_body(str(uuid.uuid4())),
        headers={**member.headers, "Idempotency-Key": "wrong-slot"},
    )
    assert other_event_slot.status_code == 422
    assert other_event_slot.json()["error"]["code"] == "invalid_slot"


# --------------------------------------------------------------------- capacity


async def test_a_group_never_gets_a_partial_place(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _, event = await _event(client, db_session, capacity=3)
    a, b = await _make_actor(client), await _make_actor(client)
    assert (await _book(client, a, event, names=("A1", "A2"))).status_code == 201
    r = await _book(client, b, event, names=("B1", "B2"))
    assert r.status_code == 409 and r.json()["error"]["code"] == "sold_out"
    assert await _counters(db_session, event) == (2, 0)
    assert (await _book(client, b, event)).status_code == 201
    assert await _counters(db_session, event) == (3, 0)
    again = await _book(client, await _make_actor(client), event)
    assert again.status_code == 409 and again.json()["error"]["code"] == "sold_out"
    await _assert_counters_true(db_session, event)


async def test_one_active_booking_per_person_per_event(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _, event = await _event(client, db_session)
    member = await _make_actor(client)
    first = await _book(client, member, event)
    assert first.status_code == 201
    second = await _book(client, member, event)
    assert second.status_code == 409 and second.json()["error"]["code"] == "already_booked"
    cancel = await client.post(
        f"{API}/bookings/{first.json()['id']}/cancel", headers=member.headers
    )
    assert cancel.status_code == 200
    third = await _book(client, member, event)
    assert third.status_code == 201


async def test_the_database_itself_refuses_a_second_active_booking(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _, event = await _event(client, db_session)
    member = await _make_actor(client)
    assert (await _book(client, member, event)).status_code == 201
    with pytest.raises(IntegrityError, match="uq_bookings_one_active_per_person_per_event"):
        await db_session.execute(
            text(
                "INSERT INTO bookings (id, event_id, slot_id, booker_user_id, party_size, status,"
                " unit_price_minor, amount_minor, currency, reference, idempotency_key,"
                " request_sha256, from_waitlist) SELECT gen_random_uuid(), event_id, slot_id,"
                " booker_user_id, 1, 'confirmed', 0, 0, 'KES', 'AC-DUPLICAT', 'dup', 'x', false"
                " FROM bookings LIMIT 1"
            )
        )


async def test_the_database_itself_refuses_a_reused_idempotency_key(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _, event = await _event(client, db_session)
    member = await _make_actor(client)
    assert (await _book(client, member, event, key="once")).status_code == 201
    with pytest.raises(IntegrityError, match="uq_bookings_booker_idempotency_key"):
        await db_session.execute(
            text(
                "INSERT INTO bookings (id, event_id, slot_id, booker_user_id, party_size, status,"
                " unit_price_minor, amount_minor, currency, reference, idempotency_key,"
                " request_sha256, from_waitlist) SELECT gen_random_uuid(), event_id, slot_id,"
                " booker_user_id, 1, 'cancelled', 0, 0, 'KES', 'AC-SECOND22', idempotency_key,"
                " 'x', false FROM bookings LIMIT 1"
            )
        )


async def test_the_database_refuses_to_oversell_even_when_told_to(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _, event = await _event(client, db_session, capacity=2)
    with pytest.raises(IntegrityError, match="ck_event_slots_not_oversold"):
        await db_session.execute(
            text("UPDATE event_slots SET seats_confirmed = 3 WHERE id = :i"),
            {"i": event["slots"][0]["id"]},
        )


# ------------------------------------------------------------------ paid and holds


async def test_a_paid_booking_holds_the_places_for_the_hold_time(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _, event = await _event(client, db_session, price_minor=350_000, hold_minutes=20)
    member = await _make_actor(client)
    r = await _book(client, member, event, names=("Ann", "Ben"))
    assert r.status_code == 201, r.text
    b = r.json()
    assert b["status"] == "pending_payment"
    assert b["hold_expires_at"] is not None
    assert b["can_cancel"] is True
    assert await _counters(db_session, event) == (0, 2)
    minutes = await db_session.scalar(
        text(
            "SELECT extract(epoch FROM (hold_expires_at - created_at)) / 60 FROM bookings"
            " WHERE id = :i"
        ),
        {"i": b["id"]},
    )
    assert 19 < float(minutes) < 21


async def test_an_expired_hold_frees_its_places_for_the_next_person(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _, event = await _event(client, db_session, price_minor=100_000, capacity=2)
    a, b = await _make_actor(client), await _make_actor(client)
    first = await _book(client, a, event, names=("A1", "A2"))
    assert first.status_code == 201
    blocked = await _book(client, b, event)
    assert blocked.status_code == 409
    await db_session.execute(
        text("UPDATE bookings SET hold_expires_at = now() - interval '1 minute' WHERE id = :i"),
        {"i": first.json()["id"]},
    )
    ok = await _book(client, b, event)
    assert ok.status_code == 201, ok.text
    old = await db_session.get(Booking, uuid.UUID(first.json()["id"]), populate_existing=True)
    assert old is not None and old.status == BookingStatus.EXPIRED
    assert old.hold_expires_at is None
    assert await _counters(db_session, event) == (0, 1)
    await _assert_counters_true(db_session, event)
    expired_mail = (
        await db_session.scalars(
            select(DomainEvent).where(DomainEvent.event_type == "booking.expired")
        )
    ).all()
    assert len(expired_mail) == 1


async def test_the_sweep_releases_holds_on_quiet_slots(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _, event = await _event(client, db_session, price_minor=100_000, capacity=5)
    a = await _make_actor(client)
    first = await _book(client, a, event, names=("A1", "A2"))
    await db_session.execute(
        text("UPDATE bookings SET hold_expires_at = now() - interval '1 minute' WHERE id = :i"),
        {"i": first.json()["id"]},
    )
    assert await bookings_service.expire_due_holds(db_session) == 1
    assert await _counters(db_session, event) == (0, 0)
    assert await bookings_service.expire_due_holds(db_session) == 0


async def test_at_most_three_unpaid_holds_per_person(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    member = await _make_actor(client)
    for _ in range(3):
        _, event = await _event(client, db_session, price_minor=100_000)
        assert (await _book(client, member, event)).status_code == 201
    _, fourth = await _event(client, db_session, price_minor=100_000)
    r = await _book(client, member, fourth)
    assert r.status_code == 409 and r.json()["error"]["code"] == "too_many_holds"


async def test_booking_attempts_are_rate_limited(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _, event = await _event(client, db_session, capacity=1)
    assert (await _book(client, await _make_actor(client), event)).status_code == 201
    member = await _make_actor(client)
    codes = [(await _book(client, member, event)).status_code for _ in range(21)]
    assert codes[:20] == [409] * 20
    assert codes[20] == 429


# -------------------------------------------------------------------- idempotency


async def test_retrying_with_the_same_key_gives_the_same_booking_and_one_seat(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _, event = await _event(client, db_session)
    member = await _make_actor(client)
    first = await _book(client, member, event, key="same-key")
    second = await _book(client, member, event, key="same-key")
    assert first.status_code == second.status_code == 201
    assert first.json()["id"] == second.json()["id"]
    assert await _counters(db_session, event) == (1, 0)


async def test_the_same_key_for_a_different_booking_is_refused(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _, event = await _event(client, db_session)
    member = await _make_actor(client)
    assert (await _book(client, member, event, key="k")).status_code == 201
    r = await _book(client, member, event, names=("Someone", "Else"), key="k")
    assert r.status_code == 422


async def test_the_service_replays_by_key_even_without_the_web_layer(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _, event = await _event(client, db_session)
    member = await _make_actor(client)
    user = await db_session.get(User, member.user_id)
    assert user is not None
    body = BookingCreate(
        slot_id=uuid.UUID(event["slots"][0]["id"]),
        participants=[ParticipantInput(full_name="Ann Alum")],
    )
    eid = uuid.UUID(event["id"])
    one = await bookings_service.create_booking(
        db_session, user=user, event_id=eid, body=body, idempotency_key="svc"
    )
    two = await bookings_service.create_booking(
        db_session, user=user, event_id=eid, body=body, idempotency_key="svc"
    )
    assert one.id == two.id
    other = body.model_copy(update={"participants": [ParticipantInput(full_name="Zed")]})
    with pytest.raises(ValidationError) as exc:
        await bookings_service.create_booking(
            db_session, user=user, event_id=eid, body=other, idempotency_key="svc"
        )
    assert exc.value.code == "idempotency_key_reused"
    assert await _counters(db_session, event) == (1, 0)


# ----------------------------------------------------------- questions and consents


async def _add_question(
    client: AsyncClient, admin: Actor, event: dict[str, Any], **body: Any
) -> dict[str, Any]:
    r = await client.post(f"{API}/events/{event['id']}/questions", json=body, headers=admin.headers)
    assert r.status_code == 201, r.text
    data: dict[str, Any] = r.json()
    return data


async def test_required_answers_are_enforced_and_checked_by_kind(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    school, admin = await _run_school(client, db_session, Role.SCHOOL_ADMIN)
    event = await _create(client, admin, school, capacity=10, max_party_size=2)
    await _add_question(
        client,
        admin,
        event,
        key="handicap",
        label="Handicap",
        kind="number",
        required=True,
        asked_of="each_participant",
    )
    await _add_question(
        client,
        admin,
        event,
        key="meal",
        label="Meal",
        kind="choice",
        required=True,
        options=[{"value": "beef", "label": "Beef"}, {"value": "veg", "label": "Veg"}],
    )
    await _add_question(client, admin, event, key="note", label="Note", kind="text")
    published = (await _publish(client, admin, event["id"])).json()
    member = await _make_actor(client)

    def answers(*extra: dict[str, Any]) -> list[dict[str, Any]]:
        return [
            {"question_key": "handicap", "position": 1, "value": 12.5},
            {"question_key": "meal", "value": "beef"},
            *extra,
        ]

    r = await _book(client, member, published, answers=[{"question_key": "meal", "value": "beef"}])
    assert r.status_code == 422 and r.json()["error"]["code"] == "answer_required"
    r = await _book(
        client, member, published, answers=answers({"question_key": "meal", "value": "fish"})
    )
    assert r.status_code == 422  # answered twice
    bad_choice = [
        {"question_key": "handicap", "value": 5},
        {"question_key": "meal", "value": "fish"},
    ]
    r = await _book(client, member, published, answers=bad_choice)
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_answer"
    r = await _book(
        client, member, published, answers=answers({"question_key": "nope", "value": 1})
    )
    assert r.status_code == 422 and r.json()["error"]["code"] == "unknown_question"
    r = await _book(
        client, member, published, answers=[{"question_key": "handicap", "value": "high"}]
    )
    assert r.status_code == 422
    # Two players: the per-person question must be answered for both.
    r = await _book(client, member, published, names=("Ann", "Ben"), answers=answers())
    assert r.status_code == 422 and r.json()["error"]["code"] == "answer_required"
    both = answers({"question_key": "handicap", "position": 2, "value": 20})
    r = await _book(client, member, published, names=("Ann", "Ben"), answers=both)
    assert r.status_code == 201, r.text
    got = {(a["question_key"], a["position"]): a["value"] for a in r.json()["answers"]}
    assert got == {("handicap", 1): 12.5, ("handicap", 2): 20, ("meal", 1): "beef"}


async def test_required_consents_must_be_accepted_and_are_recorded_with_their_words(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    school, admin = await _run_school(client, db_session, Role.SCHOOL_ADMIN)
    event = await _create(client, admin, school, capacity=10)
    c = await client.post(
        f"{API}/events/{event['id']}/consents",
        json={"key": "photos", "text": "Photos may be taken.", "required": True},
        headers=admin.headers,
    )
    assert c.status_code == 201
    published = (await _publish(client, admin, event["id"])).json()
    member = await _make_actor(client)
    r = await _book(client, member, published)
    assert r.status_code == 422 and r.json()["error"]["code"] == "consent_required"
    r = await _book(client, member, published, accepted_consents=["nope"])
    assert r.status_code == 422 and r.json()["error"]["code"] == "unknown_consent"
    r = await _book(client, member, published, accepted_consents=["photos"])
    assert r.status_code == 201, r.text
    assert [(x["key"], x["version"]) for x in r.json()["consents"]] == [("photos", 1)]
    row: str = (
        await db_session.execute(text("SELECT text_sha256 FROM booking_consents"))
    ).scalar_one()
    assert len(row) == 64

    blocked = await client.delete(
        f"{API}/events/{published['id']}/consents/{c.json()['id']}", headers=admin.headers
    )
    assert blocked.status_code == 409 and blocked.json()["error"]["code"] == "consent_accepted"


async def test_an_answered_question_cannot_be_deleted(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    school, admin = await _run_school(client, db_session, Role.SCHOOL_ADMIN)
    event = await _create(client, admin, school, capacity=10)
    q = await _add_question(client, admin, event, key="note", label="Note", kind="text")
    published = (await _publish(client, admin, event["id"])).json()
    member = await _make_actor(client)
    ok = await _book(client, member, published, answers=[{"question_key": "note", "value": "hi"}])
    assert ok.status_code == 201
    r = await client.delete(
        f"{API}/events/{published['id']}/questions/{q['id']}", headers=admin.headers
    )
    assert r.status_code == 409 and r.json()["error"]["code"] == "question_answered"


# ------------------------------------------------------------------ cancelling


async def test_cancelling_frees_the_places_and_is_harmless_to_repeat(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _, event = await _event(client, db_session)
    member = await _make_actor(client)
    b = (await _book(client, member, event, names=("A", "B"))).json()
    assert await _counters(db_session, event) == (2, 0)
    r = await client.post(
        f"{API}/bookings/{b['id']}/cancel", json={"reason": "Clash"}, headers=member.headers
    )
    assert r.status_code == 200 and r.json()["status"] == "cancelled"
    assert r.json()["cancel_reason"] == "Clash"
    assert await _counters(db_session, event) == (0, 0)
    again = await client.post(f"{API}/bookings/{b['id']}/cancel", headers=member.headers)
    assert again.status_code == 200
    assert await _counters(db_session, event) == (0, 0)


async def test_cancelling_an_unpaid_hold_releases_the_held_places(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _, event = await _event(client, db_session, price_minor=100_000)
    member = await _make_actor(client)
    b = (await _book(client, member, event)).json()
    assert await _counters(db_session, event) == (0, 1)
    r = await client.post(f"{API}/bookings/{b['id']}/cancel", headers=member.headers)
    assert r.status_code == 200
    assert await _counters(db_session, event) == (0, 0)
    row = await db_session.get(Booking, uuid.UUID(b["id"]), populate_existing=True)
    assert row is not None and row.hold_expires_at is None


async def test_a_paid_confirmed_booking_is_cancelled_by_the_organizer_not_the_booker(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _, event = await _event(client, db_session, price_minor=100_000)
    member = await _make_actor(client)
    b = (await _book(client, member, event)).json()
    await _pretend_paid(db_session, event, b["id"])
    r = await client.post(f"{API}/bookings/{b['id']}/cancel", headers=member.headers)
    assert r.status_code == 403


async def test_no_cancelling_once_the_event_has_started(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _, event = await _event(client, db_session)
    member = await _make_actor(client)
    b = (await _book(client, member, event)).json()
    await db_session.execute(
        text(
            "UPDATE events SET starts_at = now() - interval '1 hour',"
            " ends_at = now() + interval '1 hour' WHERE id = :i"
        ),
        {"i": event["id"]},
    )
    r = await client.post(f"{API}/bookings/{b['id']}/cancel", headers=member.headers)
    assert r.status_code == 409 and r.json()["error"]["code"] == "event_started"


async def test_other_people_cannot_see_or_cancel_a_booking(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    admin, event = await _event(client, db_session)
    member, stranger = await _make_actor(client), await _make_actor(client)
    b = (await _book(client, member, event)).json()
    for headers in (stranger.headers, None):
        got = await client.get(f"{API}/bookings/{b['id']}", headers=headers or {})
        assert got.status_code == (404 if headers else 401)
    assert (
        await client.post(f"{API}/bookings/{b['id']}/cancel", headers=stranger.headers)
    ).status_code == 404
    seen = await client.get(f"{API}/bookings/{b['id']}", headers=admin.headers)
    assert seen.status_code == 200 and seen.json()["reference"] == b["reference"]


async def test_my_bookings_and_my_booking_on_the_event_page(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _, event = await _event(client, db_session)
    member = await _make_actor(client)
    before = await client.get(f"{API}/events/{event['id']}", headers=member.headers)
    assert before.json()["my_booking"] is None
    b = (await _book(client, member, event)).json()
    page = await client.get(f"{API}/events/{event['id']}", headers=member.headers)
    assert page.json()["my_booking"]["id"] == b["id"]
    anon = await client.get(f"{API}/events/{event['id']}")
    assert anon.json()["my_booking"] is None
    mine = await client.get(f"{API}/bookings", headers=member.headers)
    assert [x["id"] for x in mine.json()] == [b["id"]]
    assert mine.headers["X-Total-Count"] == "1"
    none = await client.get(f"{API}/bookings?status=cancelled", headers=member.headers)
    assert none.json() == []


async def test_a_booker_can_fix_names_and_hide_themselves_but_not_change_their_email(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _, event = await _event(client, db_session)
    member, stranger = await _make_actor(client), await _make_actor(client)
    b = (await _book(client, member, event, names=("Ann", "Ben"))).json()
    url = f"{API}/bookings/{b['id']}/participants"
    r = await client.patch(
        f"{url}/2",
        json={"full_name": "Benjamin Friend", "phone": "+254 700 000 111"},
        headers=member.headers,
    )
    assert r.status_code == 200
    two = r.json()["participants"][1]
    assert two["full_name"] == "Benjamin Friend" and two["phone"] == "+254700000111"
    hide = await client.patch(f"{url}/1", json={"listed": False}, headers=member.headers)
    assert hide.json()["participants"][0]["listed"] is False
    mail = await client.patch(f"{url}/1", json={"email": "new@example.com"}, headers=member.headers)
    assert mail.status_code == 422
    nope = await client.patch(f"{url}/2", json={"full_name": "X"}, headers=stranger.headers)
    assert nope.status_code == 404
    missing = await client.patch(f"{url}/4", json={"full_name": "X"}, headers=member.headers)
    assert missing.status_code == 404


# ---------------------------------------------------------- events with bookings


async def test_price_currency_and_group_size_freeze_once_someone_has_booked(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    admin, event = await _event(client, db_session, price_minor=100_000)
    member = await _make_actor(client)
    assert (await _book(client, member, event)).status_code == 201
    url = f"{API}/events/{event['id']}"
    for change in ({"price_minor": 5}, {"max_party_size": 2}):
        r = await client.patch(url, json=change, headers=admin.headers)
        assert r.status_code == 409 and r.json()["error"]["code"] == "event_has_bookings"
    same = await client.patch(url, json={"price_minor": 100_000}, headers=admin.headers)
    assert same.status_code == 200
    title = await client.patch(url, json={"title": "Renamed"}, headers=admin.headers)
    assert title.status_code == 200
    slot = await client.delete(f"{url}/slots/{event['slots'][0]['id']}", headers=admin.headers)
    assert slot.status_code == 409


async def test_cancelling_an_event_cancels_every_booking_and_frees_the_seats(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    admin, event = await _event(client, db_session)
    a, b = await _make_actor(client), await _make_actor(client)
    assert (await _book(client, a, event, names=("A1", "A2"))).status_code == 201
    assert (await _book(client, b, event)).status_code == 201
    r = await client.post(
        f"{API}/events/{event['id']}/cancel",
        json={"reason": "Venue flooded"},
        headers=admin.headers,
    )
    assert r.status_code == 200, r.text
    rows = (
        await db_session.scalars(select(Booking).where(Booking.event_id == uuid.UUID(event["id"])))
    ).all()
    assert {x.status for x in rows} == {BookingStatus.CANCELLED}
    assert all("Venue flooded" in (x.cancel_reason or "") for x in rows)
    assert await _counters(db_session, event) == (0, 0)
    mail = (
        await db_session.scalars(
            select(DomainEvent).where(DomainEvent.event_type == "booking.event_cancelled")
        )
    ).all()
    assert len(mail) == 2
    after = await _book(client, await _make_actor(client), event)
    assert after.status_code == 409 and after.json()["error"]["code"] == "registration_cancelled"


# ------------------------------------------------------------- account deletion


async def _delete_account(client: AsyncClient, actor: Actor) -> Response:
    return await client.post(
        f"{API}/auth/me/delete", json={"password": PASSWORD}, headers=actor.headers
    )


async def test_account_deletion_is_refused_while_a_paid_booking_is_open(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _, event = await _event(client, db_session, price_minor=100_000)
    member = await _make_actor(client)
    b = (await _book(client, member, event)).json()
    await _pretend_paid(db_session, event, b["id"])
    r = await _delete_account(client, member)
    assert r.status_code == 409 and r.json()["error"]["code"] == "paid_booking_open"
    user = await db_session.get(User, member.user_id, populate_existing=True)
    assert user is not None and user.status.value == "active"


async def test_account_deletion_cancels_open_bookings_and_wipes_the_persons_details(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _, free = await _event(client, db_session)
    _, paid = await _event(client, db_session, price_minor=100_000)
    member = await _make_actor(client)
    assert (await _book(client, member, free, names=("Ann", "Ben"))).status_code == 201
    assert (await _book(client, member, paid)).status_code == 201
    r = await _delete_account(client, member)
    assert r.status_code in (200, 204), r.text
    assert await _counters(db_session, free) == (0, 0)
    assert await _counters(db_session, paid) == (0, 0)
    rows = (
        await db_session.execute(
            text(
                "SELECT p.position, p.full_name, p.email, p.phone FROM booking_participants p"
                " JOIN bookings b ON b.id = p.booking_id WHERE b.booker_user_id = :u"
                " ORDER BY p.position"
            ),
            {"u": member.user_id},
        )
    ).all()
    firsts = [r_ for r_ in rows if r_.position == 1]
    assert firsts and all(f.full_name == "Deleted user" and f.email is None for f in firsts)


async def test_the_data_export_lists_my_bookings_without_other_peoples_contact_details(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _, event = await _event(client, db_session)
    member = await _make_actor(client)
    r = await _book(
        client,
        member,
        event,
        participants=[
            {"full_name": "Ann"},
            {"full_name": "Ben", "email": "ben@example.com", "phone": "+254700000222"},
        ],
        others_consent_confirmed=True,
    )
    assert r.status_code == 201, r.text
    export = await client.get(f"{API}/auth/me/export", headers=member.headers)
    assert export.status_code == 200, export.text
    bookings = export.json()["event_bookings"]
    assert len(bookings) == 1
    assert bookings[0]["people"][1] == {"full_name": "Ben"}
    assert "ben@example.com" not in export.text
