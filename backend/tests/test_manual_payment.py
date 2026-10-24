"""
Slice 5.5: paying by hand (manual M-Pesa). The payee, the code the booker pastes, the organizer's
confirm and reject, late payments, the refund queue, and who may see or do what.
"""

import uuid
from dataclasses import dataclass
from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions.roles import Role
from app.modules.audit.models import AuditLogEntry
from app.modules.bookings import seats
from app.modules.bookings import service as bookings_service
from app.modules.bookings.models import Booking, BookingStatus, Ticket
from app.modules.domain_events.models import DomainEvent
from app.modules.domain_events.service import drain_pending
from app.modules.events.models import EventSlot
from app.modules.identity.models import User
from tests.conftest import Mailbox
from tests.test_alumni_privacy import Actor, _grant, _make_actor, _make_school
from tests.test_bookings import _book
from tests.test_events_core import API, _create, _publish, _run_school

pytestmark = pytest.mark.asyncio

PRICE = 100_000


def _code() -> str:
    return uuid.uuid4().hex[:10].upper()


@dataclass
class Shop:
    """A school with an admin, an event manager, a payee and a published paid event."""

    school_id: uuid.UUID
    admin: Actor
    manager: Actor
    account: dict[str, Any]
    event: dict[str, Any]


async def _account(
    client: AsyncClient, admin: Actor, school_id: uuid.UUID | None, **over: Any
) -> dict[str, Any]:
    body = {
        "organization_id": str(school_id) if school_id else None,
        "label": "Yengolf Alumni",
        "mpesa_kind": "paybill",
        "shortcode_or_till": "123456",
        **over,
    }
    r = await client.post(f"{API}/payment-accounts", json=body, headers=admin.headers)
    assert r.status_code == 201, r.text
    data: dict[str, Any] = r.json()
    return data


async def _shop(
    client: AsyncClient,
    db: AsyncSession,
    *,
    kind: str = "paybill",
    capacity: int = 10,
    hold_minutes: int = 1440,
    price: int = PRICE,
) -> Shop:
    school, admin = await _run_school(client, db, Role.SCHOOL_ADMIN)
    manager = await _make_actor(client)
    await _grant(db, manager.user_id, Role.EVENT_MANAGER, school.id)
    account = await _account(client, admin, school.id, mpesa_kind=kind)
    ev = await _create(
        client,
        admin,
        school,
        price_minor=price,
        capacity=capacity,
        max_party_size=4,
        hold_minutes=hold_minutes,
        payment_account_id=account["id"],
    )
    published = await _publish(client, admin, ev["id"])
    assert published.status_code == 200, published.text
    return Shop(school.id, admin, manager, account, published.json())


async def _send(
    client: AsyncClient, actor: Actor, booking_id: str, code: str | None = None
) -> Response:
    return await client.post(
        f"{API}/bookings/{booking_id}/payment-reference",
        json={"code": _code() if code is None else code},
        headers=actor.headers,
    )


async def _act(
    client: AsyncClient, actor: Actor, booking_id: str, verb: str, **body: Any
) -> Response:
    return await client.post(
        f"{API}/bookings/{booking_id}/{verb}", json=body or None, headers=actor.headers
    )


async def _booked(
    client: AsyncClient, shop: Shop, who: Actor | None = None, **kw: Any
) -> tuple[Actor, dict[str, Any]]:
    who = who or await _make_actor(client)
    r = await _book(client, who, shop.event, **kw)
    assert r.status_code == 201, r.text
    data: dict[str, Any] = r.json()
    return who, data


async def _paid_and_sent(
    client: AsyncClient, shop: Shop, **kw: Any
) -> tuple[Actor, dict[str, Any], str]:
    who, b = await _booked(client, shop, **kw)
    code = _code()
    r = await _send(client, who, b["id"], code)
    assert r.status_code == 200, r.text
    return who, r.json(), code


async def _truth(db: AsyncSession, shop: Shop) -> tuple[int, int]:
    slot = await db.get(EventSlot, uuid.UUID(shop.event["slots"][0]["id"]), populate_existing=True)
    assert slot is not None
    assert (slot.seats_confirmed, slot.seats_held) == await seats.recount(db, slot.id)
    return slot.seats_confirmed, slot.seats_held


async def _expire(db: AsyncSession, booking_id: str, *, sweep: bool = True) -> None:
    await db.execute(
        text("UPDATE bookings SET hold_expires_at = now() - interval '1 minute' WHERE id = :i"),
        {"i": booking_id},
    )
    if sweep:
        await bookings_service.expire_due_holds(db)


async def _audit(db: AsyncSession, action: str, booking_id: str) -> int:
    return int(
        await db.scalar(
            select(func.count())
            .select_from(AuditLogEntry)
            .where(
                AuditLogEntry.action == action,
                AuditLogEntry.target_id == uuid.UUID(booking_id),
            )
        )
        or 0
    )


async def _outbox(db: AsyncSession, event_type: str) -> int:
    return int(
        await db.scalar(
            select(func.count())
            .select_from(DomainEvent)
            .where(DomainEvent.event_type == event_type)
        )
        or 0
    )


async def _email_of(db: AsyncSession, actor: Actor) -> str:
    user = await db.get(User, actor.user_id)
    assert user is not None
    return user.email


# =================================================================== payment accounts


async def test_an_organization_admin_creates_lists_and_switches_off_their_payee(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    school, admin = await _run_school(client, db_session, Role.SCHOOL_ADMIN)
    account = await _account(
        client, admin, school.id, mpesa_kind="till", shortcode_or_till="5551234"
    )

    assert account["provider"] == "manual_mpesa" and account["active"] is True
    mine = await client.get(f"{API}/payment-accounts", headers=admin.headers)
    assert [a["id"] for a in mine.json()] == [account["id"]]

    off = await client.patch(
        f"{API}/payment-accounts/{account['id']}", json={"active": False}, headers=admin.headers
    )
    assert off.status_code == 200 and off.json()["active"] is False


async def test_only_admins_of_that_organization_manage_its_payment_accounts(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    school, admin = await _run_school(client, db_session, Role.SCHOOL_ADMIN)
    other_school, other_admin = await _run_school(client, db_session, Role.SCHOOL_ADMIN)
    manager = await _make_actor(client)
    await _grant(db_session, manager.user_id, Role.EVENT_MANAGER, school.id)
    member = await _make_actor(client)
    body = {
        "organization_id": str(school.id),
        "label": "x",
        "mpesa_kind": "paybill",
        "shortcode_or_till": "123456",
    }

    for who in (manager, member, other_admin):
        r = await client.post(f"{API}/payment-accounts", json=body, headers=who.headers)
        assert r.status_code == 403, (who, r.text)
    platform = await client.post(
        f"{API}/payment-accounts", json={**body, "organization_id": None}, headers=admin.headers
    )
    assert platform.status_code == 403  # the platform's own account is for platform admins

    account = await _account(client, admin, school.id)
    for who in (manager, member, other_admin):
        r = await client.patch(
            f"{API}/payment-accounts/{account['id']}", json={"active": False}, headers=who.headers
        )
        assert r.status_code == 404
        listed = await client.get(f"{API}/payment-accounts", headers=who.headers)
        assert account["id"] not in [a["id"] for a in listed.json()]


async def test_a_platform_admin_makes_the_platforms_account(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    root = await _make_actor(client)
    await _grant(db_session, root.user_id, Role.ADMIN, None)

    account = await _account(client, root, None)

    assert account["organization_id"] is None


@pytest.mark.parametrize("number", ["12", "abcdef", "12 3456", "12345678901", ""])
async def test_a_paybill_or_till_number_is_digits_only(
    client: AsyncClient, db_session: AsyncSession, number: str
) -> None:
    school, admin = await _run_school(client, db_session, Role.SCHOOL_ADMIN)
    r = await client.post(
        f"{API}/payment-accounts",
        json={
            "organization_id": str(school.id),
            "label": "x",
            "mpesa_kind": "paybill",
            "shortcode_or_till": number,
        },
        headers=admin.headers,
    )
    assert r.status_code == 422


async def test_the_number_cannot_change_once_people_booked_events_paid_to_it(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    shop = await _shop(client, db_session)
    url = f"{API}/payment-accounts/{shop.account['id']}"
    await _booked(client, shop)

    moved = await client.patch(
        url, json={"shortcode_or_till": "999999"}, headers=shop.admin.headers
    )
    renamed = await client.patch(url, json={"label": "New name"}, headers=shop.admin.headers)

    assert moved.status_code == 409 and moved.json()["error"]["code"] == "payment_account_in_use"
    assert renamed.status_code == 200


# ============================================================== events and their payee


async def test_the_event_page_says_where_to_pay(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    shop = await _shop(client, db_session, kind="till")

    assert shop.event["payment"] == {
        "method": "manual_mpesa",
        "kind": "till",
        "number": "123456",
        "payee_name": "Yengolf Alumni",
        "currency": "KES",
    }


async def test_an_event_cannot_use_another_organizations_or_a_switched_off_account(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    school, admin = await _run_school(client, db_session, Role.SCHOOL_ADMIN)
    _, other_admin = await _run_school(client, db_session, Role.SCHOOL_ADMIN)
    other_school = await _make_school(db_session)
    await _grant(db_session, other_admin.user_id, Role.SCHOOL_ADMIN, other_school.id)
    theirs = await _account(client, other_admin, other_school.id)
    off = await _account(client, admin, school.id)
    await client.patch(
        f"{API}/payment-accounts/{off['id']}", json={"active": False}, headers=admin.headers
    )

    for account_id, code in ((theirs["id"], "invalid_payee"), (off["id"], "payee_inactive")):
        r = await client.post(
            f"{API}/events",
            json={
                "organization_id": str(school.id),
                "title": "Mixer",
                "category": "networking",
                "starts_at": "2099-01-01T10:00:00Z",
                "ends_at": "2099-01-01T12:00:00Z",
                "price_minor": PRICE,
                "capacity": 5,
                "payment_account_id": account_id,
            },
            headers=admin.headers,
        )
        assert r.status_code == 422 and r.json()["error"]["code"] == code, r.text


async def test_long_holds_need_a_manual_payee_and_stop_at_48_hours(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    school, admin = await _run_school(client, db_session, Role.SCHOOL_ADMIN)
    account = await _account(client, admin, school.id)
    base = {
        "organization_id": str(school.id),
        "title": "Mixer",
        "category": "networking",
        "starts_at": "2099-01-01T10:00:00Z",
        "ends_at": "2099-01-01T12:00:00Z",
        "price_minor": PRICE,
        "capacity": 5,
    }

    plain = await client.post(
        f"{API}/events", json={**base, "hold_minutes": 61}, headers=admin.headers
    )
    manual = await client.post(
        f"{API}/events",
        json={**base, "hold_minutes": 2880, "payment_account_id": account["id"]},
        headers=admin.headers,
    )
    too_long = await client.post(
        f"{API}/events",
        json={**base, "hold_minutes": 2881, "payment_account_id": account["id"]},
        headers=admin.headers,
    )

    assert plain.status_code == 422 and plain.json()["error"]["code"] == "hold_too_long"
    assert manual.status_code == 201 and manual.json()["hold_minutes"] == 2880
    assert too_long.status_code == 422


async def test_dropping_the_payee_from_an_event_with_a_long_hold_is_refused(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    school, admin = await _run_school(client, db_session, Role.SCHOOL_ADMIN)
    account = await _account(client, admin, school.id)
    ev = await _create(
        client,
        admin,
        school,
        price_minor=PRICE,
        capacity=5,
        hold_minutes=600,
        payment_account_id=account["id"],
    )

    r = await client.patch(
        f"{API}/events/{ev['id']}", json={"payment_account_id": None}, headers=admin.headers
    )

    assert r.status_code == 422 and r.json()["error"]["code"] == "hold_too_long"


async def test_the_payee_cannot_change_once_someone_has_booked(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    shop = await _shop(client, db_session)
    second = await _account(client, shop.admin, shop.school_id, shortcode_or_till="654321")
    await _booked(client, shop)

    r = await client.patch(
        f"{API}/events/{shop.event['id']}",
        json={"payment_account_id": second["id"]},
        headers=shop.admin.headers,
    )

    assert r.status_code == 409 and r.json()["error"]["code"] == "event_has_bookings"


# ===================================================================== how to pay


async def test_a_booking_says_how_to_pay_a_paybill_with_the_reference_as_account_number(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    shop = await _shop(client, db_session, kind="paybill")

    _, b = await _booked(client, shop)

    pay = b["payment"]
    assert pay["payee"]["kind"] == "paybill" and pay["payee"]["number"] == "123456"
    assert pay["account_reference"] == b["reference"]
    assert pay["state"] is None and pay["code"] is None and pay["can_submit_code"] is True
    assert b["amount_minor"] == PRICE


async def test_a_till_has_no_account_number_to_type(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    shop = await _shop(client, db_session, kind="till")

    _, b = await _booked(client, shop)

    assert b["payment"]["payee"]["kind"] == "till"
    assert b["payment"]["account_reference"] is None


async def test_a_free_event_has_nothing_to_pay(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    school, admin = await _run_school(client, db_session, Role.SCHOOL_ADMIN)
    ev = await _create(client, admin, school, capacity=5)
    published = (await _publish(client, admin, ev["id"])).json()
    who = await _make_actor(client)

    b = (await _book(client, who, published)).json()

    assert b["payment"] is None and b["status"] == "confirmed"
    refused = await _send(client, who, b["id"])
    assert refused.status_code == 409 and refused.json()["error"]["code"] == "not_manual_payment"


# ============================================================= the booker sends a code


async def test_the_code_is_trimmed_and_upper_cased(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    shop = await _shop(client, db_session)
    who, b = await _booked(client, shop)

    r = await _send(client, who, b["id"], "  sgk7f5x2qw \n")

    assert r.status_code == 200, r.text
    assert r.json()["payment"]["code"] == "SGK7F5X2QW"
    assert r.json()["payment"]["state"] == "awaiting_confirmation"
    assert r.json()["status"] == "pending_payment"  # still held; not confirmed by itself
    assert await _truth(db_session, shop) == (0, 1)


@pytest.mark.parametrize("bad", ["SHORT", "TOOLONGCODE123", "ABC DEF 1234", "ABCDEF12$%", ""])
async def test_a_code_that_cannot_be_an_mpesa_code_is_refused(
    client: AsyncClient, db_session: AsyncSession, bad: str
) -> None:
    shop = await _shop(client, db_session)
    who, b = await _booked(client, shop)

    r = await _send(client, who, b["id"], bad)

    assert r.status_code == 422


async def test_one_code_pays_for_one_booking_only_even_across_events(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    shop = await _shop(client, db_session)
    other_shop = await _shop(client, db_session)
    first, fb = await _booked(client, shop)
    second, sb = await _booked(client, shop)
    third, tb = await _booked(client, other_shop)
    code = _code()
    assert (await _send(client, first, fb["id"], code)).status_code == 200

    same_event = await _send(client, second, sb["id"], code.lower())
    other_event = await _send(client, third, tb["id"], code)

    for r in (same_event, other_event):
        assert r.status_code == 409 and r.json()["error"]["code"] == "payment_code_used"
        assert first.user_id.hex not in r.text  # nothing about whose it was
    clean = await client.get(f"{API}/bookings/{sb['id']}", headers=second.headers)
    assert clean.json()["payment"]["code"] is None and clean.json()["payment"]["state"] is None


async def test_the_database_itself_refuses_a_second_booking_with_the_same_code(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    shop = await _shop(client, db_session)
    _, a, code = await _paid_and_sent(client, shop)
    _, b = await _booked(client, shop)

    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            await db_session.execute(
                text("UPDATE bookings SET payment_reference_code = :c WHERE id = :i"),
                {"c": code, "i": b["id"]},
            )
    assert a["payment"]["code"] == code


async def test_sending_the_same_code_twice_is_harmless(
    client: AsyncClient, db_session: AsyncSession, mailbox: Mailbox
) -> None:
    shop = await _shop(client, db_session)
    who, b = await _booked(client, shop)
    code = _code()
    await drain_pending(db_session)
    mailbox.sent.clear()

    first = await _send(client, who, b["id"], code)
    again = await _send(client, who, b["id"], code)

    assert first.status_code == again.status_code == 200
    assert await _audit(db_session, "booking.payment_submitted", b["id"]) == 1
    assert await _outbox(db_session, "booking.payment_submitted") == 1
    await drain_pending(db_session)
    assert [m["to"] for m in mailbox.sent] == [await _email_of(db_session, who)]


async def test_a_different_code_while_one_is_waiting_is_refused(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    shop = await _shop(client, db_session)
    who, b, _ = await _paid_and_sent(client, shop)

    r = await _send(client, who, b["id"], _code())

    assert r.status_code == 409 and r.json()["error"]["code"] == "payment_already_submitted"


async def test_only_the_booker_sends_a_code(client: AsyncClient, db_session: AsyncSession) -> None:
    shop = await _shop(client, db_session)
    _, b = await _booked(client, shop)
    stranger = await _make_actor(client)

    for who in (stranger, shop.admin, shop.manager):
        r = await _send(client, who, b["id"])
        assert r.status_code == 404, (who, r.text)
    row = await db_session.get(Booking, uuid.UUID(b["id"]), populate_existing=True)
    assert row is not None and row.payment_state is None


async def test_a_confirmed_booking_cannot_take_another_code(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    shop = await _shop(client, db_session)
    who, b, _ = await _paid_and_sent(client, shop)
    assert (await _act(client, shop.admin, b["id"], "confirm-manual")).status_code == 200

    r = await _send(client, who, b["id"])

    assert r.status_code == 409


async def test_sending_codes_is_rate_limited_per_booking(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    shop = await _shop(client, db_session)
    who, b = await _booked(client, shop)

    for _ in range(5):
        assert (await _send(client, who, b["id"])).status_code == 200
        r = await _act(client, shop.admin, b["id"], "reject-manual", reason="not found")
        assert r.status_code == 200

    sixth = await _send(client, who, b["id"])

    assert sixth.status_code == 429


# ============================================================ the organizer confirms


async def test_confirming_turns_the_held_places_into_a_booking_with_tickets(
    client: AsyncClient, db_session: AsyncSession, mailbox: Mailbox
) -> None:
    shop = await _shop(client, db_session)
    who, b, code = await _paid_and_sent(client, shop, names=("Ann", "Ben"))
    assert await _truth(db_session, shop) == (0, 2)
    await drain_pending(db_session)
    mailbox.sent.clear()

    r = await _act(client, shop.admin, b["id"], "confirm-manual")

    assert r.status_code == 200, r.text
    out = r.json()
    assert out["status"] == "confirmed" and out["hold_expires_at"] is None
    assert out["payment"]["state"] == "confirmed" and out["payment"]["code"] == code
    assert await _truth(db_session, shop) == (2, 0)
    tickets = (
        await db_session.scalars(select(Ticket).where(Ticket.booking_id == uuid.UUID(b["id"])))
    ).all()
    assert len(tickets) == 2
    assert await _audit(db_session, "booking.payment_confirmed", b["id"]) == 1
    await drain_pending(db_session)
    assert [m["to"] for m in mailbox.sent] == [await _email_of(db_session, who)]
    assert "Booking confirmed" in (mailbox.sent[0]["subject"] or "")


async def test_confirming_twice_changes_and_sends_nothing_more(
    client: AsyncClient, db_session: AsyncSession, mailbox: Mailbox
) -> None:
    shop = await _shop(client, db_session)
    _, b, _ = await _paid_and_sent(client, shop)
    assert (await _act(client, shop.admin, b["id"], "confirm-manual")).status_code == 200
    await drain_pending(db_session)
    mailbox.sent.clear()

    again = await _act(client, shop.admin, b["id"], "confirm-manual")

    assert again.status_code == 200 and again.json()["status"] == "confirmed"
    assert await _truth(db_session, shop) == (1, 0)
    assert await _audit(db_session, "booking.payment_confirmed", b["id"]) == 1
    assert await _outbox(db_session, "booking.confirmed") == 1
    assert await _outbox(db_session, "booking.payment_confirmed") == 1
    await drain_pending(db_session)
    assert mailbox.sent == []
    count = await db_session.scalar(
        select(func.count()).select_from(Ticket).where(Ticket.booking_id == uuid.UUID(b["id"]))
    )
    assert count == 1


async def test_only_an_admin_of_the_organizing_school_confirms_money(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    shop = await _shop(client, db_session)
    who, b, _ = await _paid_and_sent(client, shop)
    _, other_admin = await _run_school(client, db_session, Role.SCHOOL_ADMIN)
    stranger = await _make_actor(client)

    assert (await _act(client, shop.manager, b["id"], "confirm-manual")).status_code == 403
    for actor in (who, other_admin, stranger):  # the booker cannot confirm their own payment
        assert (await _act(client, actor, b["id"], "confirm-manual")).status_code == 404
    row = await db_session.get(Booking, uuid.UUID(b["id"]), populate_existing=True)
    assert row is not None and row.status == BookingStatus.PENDING_PAYMENT


async def test_there_is_nothing_to_confirm_without_a_code(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    shop = await _shop(client, db_session)
    _, b = await _booked(client, shop)

    r = await _act(client, shop.admin, b["id"], "confirm-manual")

    assert r.status_code == 409 and r.json()["error"]["code"] == "no_payment_to_confirm"
    assert await _truth(db_session, shop) == (0, 1)


# ============================================================== the organizer rejects


async def test_rejecting_keeps_the_hold_tells_the_booker_and_frees_the_code(
    client: AsyncClient, db_session: AsyncSession, mailbox: Mailbox
) -> None:
    shop = await _shop(client, db_session)
    who, b, code = await _paid_and_sent(client, shop)
    await drain_pending(db_session)
    mailbox.sent.clear()

    r = await _act(client, shop.admin, b["id"], "reject-manual", reason="No payment of 1,000 found")

    assert r.status_code == 200, r.text
    out = r.json()
    assert out["status"] == "pending_payment" and out["hold_expires_at"] is not None
    assert out["payment"]["state"] == "rejected" and out["payment"]["code"] is None
    assert out["payment"]["rejection_reason"] == "No payment of 1,000 found"
    assert out["payment"]["can_submit_code"] is True
    assert await _truth(db_session, shop) == (0, 1)
    assert await _audit(db_session, "booking.payment_rejected", b["id"]) == 1
    await drain_pending(db_session)
    assert [m["to"] for m in mailbox.sent] == [await _email_of(db_session, who)]
    assert "No payment of 1,000 found" in (mailbox.sent[0]["body"] or "")

    # The code was wrong or someone else's: the real owner can use it on their own booking.
    other, ob = await _booked(client, shop)
    assert (await _send(client, other, ob["id"], code)).status_code == 200
    # And the booker can send a right code.
    again = await _send(client, who, b["id"])
    assert again.status_code == 200 and again.json()["payment"]["state"] == "awaiting_confirmation"


async def test_rejecting_twice_sends_one_email(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    shop = await _shop(client, db_session)
    _, b, _ = await _paid_and_sent(client, shop)
    for _ in range(2):
        r = await _act(client, shop.admin, b["id"], "reject-manual", reason="not found")
        assert r.status_code == 200

    assert await _outbox(db_session, "booking.payment_rejected") == 1
    assert await _audit(db_session, "booking.payment_rejected", b["id"]) == 1


async def test_a_second_rejection_after_a_new_code_is_a_new_email(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    shop = await _shop(client, db_session)
    who, b, _ = await _paid_and_sent(client, shop)
    await _act(client, shop.admin, b["id"], "reject-manual", reason="not found")
    await _send(client, who, b["id"])
    await _act(client, shop.admin, b["id"], "reject-manual", reason="still not found")

    assert await _outbox(db_session, "booking.payment_rejected") == 2


async def test_rejecting_needs_a_waiting_code_a_reason_and_an_admin(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    shop = await _shop(client, db_session)
    who, b = await _booked(client, shop)
    stranger = await _make_actor(client)

    none_waiting = await _act(client, shop.admin, b["id"], "reject-manual", reason="not found")
    assert none_waiting.status_code == 409
    await _send(client, who, b["id"])
    assert (await _act(client, shop.admin, b["id"], "reject-manual")).status_code == 422
    assert (
        await _act(client, shop.manager, b["id"], "reject-manual", reason="no")
    ).status_code in (403, 422)
    assert (
        await _act(client, shop.manager, b["id"], "reject-manual", reason="not found")
    ).status_code == 403
    for actor in (who, stranger):
        r = await _act(client, actor, b["id"], "reject-manual", reason="not found")
        assert r.status_code == 404


async def test_the_rejection_reason_is_the_bookers_to_read_and_nobody_elses(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    shop = await _shop(client, db_session)
    who, b, _ = await _paid_and_sent(client, shop)
    stranger = await _make_actor(client)
    await _act(client, shop.admin, b["id"], "reject-manual", reason="Looks like a typo")

    mine = await client.get(f"{API}/bookings/{b['id']}", headers=who.headers)
    theirs = await client.get(f"{API}/bookings/{b['id']}", headers=stranger.headers)

    assert mine.json()["payment"]["rejection_reason"] == "Looks like a typo"
    assert theirs.status_code == 404 and "typo" not in theirs.text


# ======================================================================= late payments


async def test_a_late_payment_is_accepted_when_the_places_are_still_free(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    shop = await _shop(client, db_session, capacity=4)
    who, b = await _booked(client, shop, names=("Ann", "Ben"))
    await _expire(db_session, b["id"])
    assert await _truth(db_session, shop) == (0, 0)
    sent = await _send(client, who, b["id"])  # paid in the last minutes, sent after the hold
    assert sent.status_code == 200, sent.text
    assert sent.json()["status"] == "expired"

    r = await _act(client, shop.admin, b["id"], "confirm-manual")

    assert r.status_code == 200, r.text
    assert r.json()["status"] == "confirmed" and r.json()["payment"]["state"] == "confirmed"
    assert await _truth(db_session, shop) == (2, 0)
    assert await _audit(db_session, "booking.late_payment_accepted", b["id"]) == 1
    assert await _audit(db_session, "booking.payment_confirmed", b["id"]) == 0


async def test_a_late_payment_with_the_places_gone_goes_to_the_refund_queue(
    client: AsyncClient, db_session: AsyncSession, mailbox: Mailbox
) -> None:
    shop = await _shop(client, db_session, capacity=2)
    late, b = await _booked(client, shop, names=("Ann", "Ben"))
    await _expire(db_session, b["id"])
    taker, _ = await _booked(client, shop, names=("Cy", "Di"))  # takes both places
    assert (await _send(client, late, b["id"])).status_code == 200
    await drain_pending(db_session)
    mailbox.sent.clear()

    r = await _act(client, shop.admin, b["id"], "confirm-manual")

    assert r.status_code == 200, r.text
    out = r.json()
    assert out["status"] == "expired" and out["payment"]["state"] == "needs_refund"
    assert await _truth(db_session, shop) == (0, 2)  # the new booker's places are untouched
    assert await _audit(db_session, "booking.payment_unallocated", b["id"]) == 1
    assert await _audit(db_session, "booking.payment_confirmed", b["id"]) == 0
    tickets = await db_session.scalar(
        select(func.count()).select_from(Ticket).where(Ticket.booking_id == uuid.UUID(b["id"]))
    )
    assert tickets == 0
    await drain_pending(db_session)
    assert [m["to"] for m in mailbox.sent] == [await _email_of(db_session, late)]
    assert "refund" in (mailbox.sent[0]["subject"] or "").lower()

    queue = await client.get(
        f"{API}/events/{shop.event['id']}/payments", headers=shop.admin.headers
    )
    assert [(row["booking_id"], row["payment"]["state"]) for row in queue.json()] == [
        (b["id"], "needs_refund")
    ]
    assert taker.user_id != late.user_id


async def test_confirm_sweeps_a_hold_that_ran_out_before_deciding(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    shop = await _shop(client, db_session, capacity=1)
    late, b, _ = await _paid_and_sent(client, shop)
    await _expire(db_session, b["id"], sweep=False)  # nobody has swept it yet
    other, _ = await _booked(client, shop)  # booking sweeps the slot and takes the place
    assert other.user_id != late.user_id

    r = await _act(client, shop.admin, b["id"], "confirm-manual")

    assert r.json()["status"] == "expired" and r.json()["payment"]["state"] == "needs_refund"
    assert await _truth(db_session, shop) == (0, 1)


async def test_a_hold_nobody_swept_yet_still_counts_as_ended_when_the_organizer_confirms(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    shop = await _shop(client, db_session, capacity=4)
    _, b, _ = await _paid_and_sent(client, shop)
    await _expire(db_session, b["id"], sweep=False)  # past its time, still marked pending

    r = await _act(client, shop.admin, b["id"], "confirm-manual")

    assert r.status_code == 200 and r.json()["status"] == "confirmed"
    assert await _audit(db_session, "booking.late_payment_accepted", b["id"]) == 1
    assert await _audit(db_session, "booking.payment_confirmed", b["id"]) == 0
    assert await _truth(db_session, shop) == (1, 0)


async def test_a_late_payment_from_someone_who_booked_again_is_owed_back(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    shop = await _shop(client, db_session, capacity=5)
    who, b = await _booked(client, shop)
    await _expire(db_session, b["id"])
    again = await _book(client, who, shop.event)  # they simply booked again
    assert again.status_code == 201
    assert (await _send(client, who, b["id"])).status_code == 200

    r = await _act(client, shop.admin, b["id"], "confirm-manual")

    assert r.status_code == 200 and r.json()["payment"]["state"] == "needs_refund"
    assert r.json()["status"] == "expired"
    assert await _truth(db_session, shop) == (0, 1)


async def test_a_payment_for_a_cancelled_booking_is_owed_back_not_confirmed(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    shop = await _shop(client, db_session)
    who, b = await _booked(client, shop)
    assert (await _act(client, who, b["id"], "cancel")).status_code == 200
    assert (await _send(client, who, b["id"])).status_code == 200

    r = await _act(client, shop.admin, b["id"], "confirm-manual")

    assert r.json()["status"] == "cancelled" and r.json()["payment"]["state"] == "needs_refund"
    assert await _truth(db_session, shop) == (0, 0)


async def test_no_code_is_taken_once_the_event_is_cancelled(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    shop = await _shop(client, db_session)
    who, b = await _booked(client, shop)
    cancelled = await client.post(
        f"{API}/events/{shop.event['id']}/cancel",
        json={"reason": "Rain stopped play"},
        headers=shop.admin.headers,
    )
    assert cancelled.status_code == 200, cancelled.text

    r = await _send(client, who, b["id"])

    assert r.status_code == 409 and r.json()["error"]["code"] == "payment_not_accepted"


# ========================================================================= refunds


async def test_marking_a_refund_closes_it_and_tells_the_booker(
    client: AsyncClient, db_session: AsyncSession, mailbox: Mailbox
) -> None:
    shop = await _shop(client, db_session, capacity=1)
    late, b = await _booked(client, shop)
    await _expire(db_session, b["id"])
    await _booked(client, shop)
    await _send(client, late, b["id"])
    await _act(client, shop.admin, b["id"], "confirm-manual")
    await drain_pending(db_session)
    mailbox.sent.clear()

    r = await _act(client, shop.admin, b["id"], "mark-refunded", note="Sent 12:40")

    assert r.status_code == 200, r.text
    assert r.json()["payment"]["state"] == "refunded" and r.json()["status"] == "expired"
    assert await _audit(db_session, "booking.refund_marked", b["id"]) == 1
    again = await _act(client, shop.admin, b["id"], "mark-refunded")
    assert again.status_code == 200
    assert await _audit(db_session, "booking.refund_marked", b["id"]) == 1
    await drain_pending(db_session)
    assert [m["to"] for m in mailbox.sent] == [await _email_of(db_session, late)]
    queue = await client.get(
        f"{API}/events/{shop.event['id']}/payments", headers=shop.admin.headers
    )
    assert queue.json() == []


async def test_only_money_that_is_owed_can_be_marked_refunded(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    shop = await _shop(client, db_session)
    who, b, _ = await _paid_and_sent(client, shop)

    waiting = await _act(client, shop.admin, b["id"], "mark-refunded")
    await _act(client, shop.admin, b["id"], "confirm-manual")
    paid = await _act(client, shop.admin, b["id"], "mark-refunded")

    assert waiting.status_code == paid.status_code == 409
    assert paid.json()["error"]["code"] == "nothing_to_refund"
    assert (await _act(client, shop.manager, b["id"], "mark-refunded")).status_code == 403
    assert (await _act(client, who, b["id"], "mark-refunded")).status_code == 404


async def test_cancelling_a_paid_booking_with_a_refund_queues_the_money_and_frees_the_places(
    client: AsyncClient, db_session: AsyncSession, mailbox: Mailbox
) -> None:
    shop = await _shop(client, db_session)
    who, b, _ = await _paid_and_sent(client, shop, names=("Ann", "Ben"))
    await _act(client, shop.admin, b["id"], "confirm-manual")
    await drain_pending(db_session)
    mailbox.sent.clear()

    r = await _act(
        client, shop.admin, b["id"], "organizer-cancel", reason="Double booked", refund=True
    )

    assert r.status_code == 200, r.text
    assert r.json()["status"] == "cancelled" and r.json()["payment"]["state"] == "needs_refund"
    assert await _truth(db_session, shop) == (0, 0)
    assert await _audit(db_session, "booking.refund_owed", b["id"]) == 1
    await drain_pending(db_session)
    assert {m["to"] for m in mailbox.sent} == {await _email_of(db_session, who)}

    done = await _act(client, shop.admin, b["id"], "mark-refunded")
    assert done.json()["status"] == "refunded" and done.json()["payment"]["state"] == "refunded"
    assert await _truth(db_session, shop) == (0, 0)


async def test_cancelling_without_a_refund_leaves_the_payment_as_paid(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    shop = await _shop(client, db_session)
    _, b, _ = await _paid_and_sent(client, shop)
    await _act(client, shop.admin, b["id"], "confirm-manual")

    r = await _act(client, shop.admin, b["id"], "organizer-cancel", reason="No show", refund=False)

    assert r.json()["status"] == "cancelled" and r.json()["payment"]["state"] == "confirmed"


async def test_only_an_admin_cancels_on_the_organizers_behalf(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    shop = await _shop(client, db_session)
    who, b = await _booked(client, shop)
    stranger = await _make_actor(client)

    assert (
        await _act(client, shop.manager, b["id"], "organizer-cancel", reason="no")
    ).status_code in (403, 422)
    for actor in (who, stranger):
        r = await _act(client, actor, b["id"], "organizer-cancel", reason="Not yours", refund=True)
        assert r.status_code == 404
    row = await db_session.get(Booking, uuid.UUID(b["id"]), populate_existing=True)
    assert row is not None and row.status == BookingStatus.PENDING_PAYMENT


async def test_cancelling_the_event_puts_every_confirmed_payment_in_the_refund_queue(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    shop = await _shop(client, db_session)
    _, paid, _ = await _paid_and_sent(client, shop)
    await _act(client, shop.admin, paid["id"], "confirm-manual")
    _, waiting, _ = await _paid_and_sent(client, shop)

    cancel = await client.post(
        f"{API}/events/{shop.event['id']}/cancel",
        json={"reason": "Rain stopped play"},
        headers=shop.admin.headers,
    )
    assert cancel.status_code == 200, cancel.text

    refunds = await client.get(
        f"{API}/events/{shop.event['id']}/payments",
        params={"state": "needs_refund"},
        headers=shop.admin.headers,
    )
    assert [r["booking_id"] for r in refunds.json()] == [paid["id"]]
    # A code nobody has checked yet stays in the queue to be decided (confirming it now would
    # send it straight to refunds, since the booking is cancelled).
    both = await client.get(f"{API}/events/{shop.event['id']}/payments", headers=shop.admin.headers)
    assert {r["booking_id"] for r in both.json()} == {paid["id"], waiting["id"]}


# ==================================================================== who sees what


async def test_the_organizers_list_shows_codes_to_the_people_who_run_the_event_only(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    shop = await _shop(client, db_session)
    who, b, code = await _paid_and_sent(client, shop)
    _, other_admin = await _run_school(client, db_session, Role.SCHOOL_ADMIN)
    url = f"{API}/events/{shop.event['id']}/registrations"

    for organizer in (shop.admin, shop.manager):
        rows = (await client.get(url, headers=organizer.headers)).json()
        assert rows[0]["payment"]["code"] == code
        assert rows[0]["payment"]["state"] == "awaiting_confirmation"
    for outsider in (who, other_admin):
        assert (await client.get(url, headers=outsider.headers)).status_code in (403, 404)
    by_code = await client.get(url, params={"q": code[2:7].lower()}, headers=shop.admin.headers)
    assert [r["booking_id"] for r in by_code.json()] == [b["id"]]
    by_state = await client.get(
        url, params={"payment_state": "rejected"}, headers=shop.admin.headers
    )
    assert by_state.json() == []


async def test_the_money_queue_is_for_admins_of_that_event_only(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    shop = await _shop(client, db_session)
    who, b, _ = await _paid_and_sent(client, shop)
    _, other_admin = await _run_school(client, db_session, Role.SCHOOL_ADMIN)
    url = f"{API}/events/{shop.event['id']}/payments"

    ok = await client.get(url, headers=shop.admin.headers)
    assert ok.status_code == 200 and ok.headers["X-Total-Count"] == "1"
    assert [r["booking_id"] for r in ok.json()] == [b["id"]]
    assert (await client.get(url, headers=shop.manager.headers)).status_code == 403
    for outsider in (who, other_admin):
        assert (await client.get(url, headers=outsider.headers)).status_code in (403, 404)


async def test_nobody_else_can_read_or_touch_a_booking_that_is_not_theirs(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    shop = await _shop(client, db_session)
    _, b, code = await _paid_and_sent(client, shop)
    stranger = await _make_actor(client)

    read = await client.get(f"{API}/bookings/{b['id']}", headers=stranger.headers)
    mine = await client.get(f"{API}/bookings", headers=stranger.headers)

    assert read.status_code == 404 and code not in read.text
    assert mine.json() == [] and code not in mine.text
    anon = await client.post(f"{API}/bookings/{b['id']}/payment-reference", json={"code": _code()})
    assert anon.status_code == 401


async def test_payment_emails_go_to_the_booker_only(
    client: AsyncClient, db_session: AsyncSession, mailbox: Mailbox
) -> None:
    shop = await _shop(client, db_session)
    who, b = await _booked(client, shop)
    friend = "friend@example.com"
    await db_session.execute(
        text("UPDATE booking_participants SET email = :e WHERE booking_id = :b AND position = 1"),
        {"e": friend, "b": b["id"]},
    )
    await drain_pending(db_session)
    mailbox.sent.clear()

    await _send(client, who, b["id"])
    await _act(client, shop.admin, b["id"], "reject-manual", reason="not found")
    await drain_pending(db_session)

    mine = await _email_of(db_session, who)
    assert len(mailbox.sent) == 2
    assert {m["to"] for m in mailbox.sent} == {mine}
    assert all(friend not in (m["body"] or "") for m in mailbox.sent)


async def test_the_counters_stay_true_through_a_mixed_run_of_payments(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    shop = await _shop(client, db_session, capacity=6)
    a, ab, _ = await _paid_and_sent(client, shop, names=("A1", "A2"))
    _, bb, _ = await _paid_and_sent(client, shop, names=("B1", "B2", "B3"))
    c, cb = await _booked(client, shop)
    await _act(client, shop.admin, ab["id"], "confirm-manual")
    await _act(client, shop.admin, ab["id"], "organizer-cancel", reason="Mistake", refund=True)
    await _act(client, shop.admin, bb["id"], "confirm-manual")
    await _act(client, c, cb["id"], "cancel")

    assert await _truth(db_session, shop) == (3, 0)
    assert a.user_id != c.user_id
