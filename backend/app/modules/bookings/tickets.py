"""
Tickets: one per person in a confirmed booking.

A ticket code is 64 hex characters = 32 bytes, in two halves:

* the first 32 hex characters (128 bits) are the ticket's id, a random UUID;
* the last 32 hex characters (128 bits) are a signature: HMAC-SHA256 of the ticket id and its
  `qr_version` under the TICKET_SIGNING_KEY secret, cut to its first 16 bytes.

So the signature is 128 bits, and the whole code is 256 bits long. Forging a code for a ticket
means guessing a 128-bit signature, and nothing secret is stored: a lost QR is simply drawn
again, and raising `qr_version` kills a leaked one. The code is also the only credential for the
ticket page, so a player with no account can open it from the emailed link. A ticket whose
booking is not `confirmed` is void whatever the ticket row says.
"""

import hashlib
import hmac
import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors.exceptions import ConflictError, NotFoundError
from app.modules.audit.service import record as record_audit
from app.modules.bookings.models import (
    Booking,
    BookingParticipant,
    BookingStatus,
    Ticket,
    TicketStatus,
)
from app.modules.bookings.schemas import BookingSlotInfo, TicketEventInfo, TicketOut
from app.modules.domain_events.service import publish as publish_event
from app.modules.events.models import Event, EventSlot
from app.modules.identity.models import User

_ID_HEX = 32  # the ticket id: 16 bytes
_SIG_BYTES = 16  # the signature: 128 bits
CODE_LENGTH = _ID_HEX + _SIG_BYTES * 2  # 64 hex characters in all

# Test-only seam: awaited after a scan has found its ticket valid and before it writes, so a
# test can hold two scans in exactly that gap. None in production.
check_in_hook: Callable[[], Awaitable[None]] | None = None


def _key() -> bytes:
    settings = get_settings()
    if settings.ticket_signing_key is not None:
        return settings.ticket_signing_key.get_secret_value().encode()
    # Development and tests only (production refuses to start without its own key): derived
    # from SECRET_KEY, so the two are never the same bytes.
    derived = hmac.new(
        settings.secret_key.get_secret_value().encode(), b"ticket-signing-key-v1", hashlib.sha256
    )
    return derived.digest()


def _sign(ticket_id: uuid.UUID, qr_version: int) -> str:
    message = f"ticket:{ticket_id}:{qr_version}".encode()
    return hmac.new(_key(), message, hashlib.sha256).digest()[:_SIG_BYTES].hex()


def make_code(ticket: Ticket) -> str:
    return ticket.id.hex + _sign(ticket.id, ticket.qr_version)


def parse_code(code: str) -> uuid.UUID | None:
    """The ticket id if the code is well formed. The signature is checked against the row's
    current `qr_version` by `find_by_code`."""
    code = code.strip().lower()
    if len(code) != CODE_LENGTH:
        return None
    try:
        int(code, 16)
        return uuid.UUID(code[:32])
    except ValueError:
        return None


async def find_by_code(db: AsyncSession, code: str, *, lock: bool = False) -> Ticket:
    """The ticket for a code, or 404. Wrong, forged and revoked codes are indistinguishable."""
    ticket_id = parse_code(code)
    if ticket_id is None:
        raise NotFoundError("Ticket not found.")
    stmt = select(Ticket).where(Ticket.id == ticket_id)
    if lock:
        stmt = stmt.with_for_update().execution_options(populate_existing=True)
    ticket = await db.scalar(stmt)
    if ticket is None:
        raise NotFoundError("Ticket not found.")
    expected = _sign(ticket.id, ticket.qr_version)
    if not hmac.compare_digest(expected, code.strip().lower()[32:]):
        raise NotFoundError("Ticket not found.")
    return ticket


async def issue_tickets(db: AsyncSession, booking: Booking) -> list[Ticket]:
    """Makes the missing tickets of a confirmed booking. Safe to call any number of times."""
    existing = {
        t.participant_id: t
        for t in (await db.scalars(select(Ticket).where(Ticket.booking_id == booking.id))).all()
    }
    people = (
        await db.scalars(
            select(BookingParticipant)
            .where(BookingParticipant.booking_id == booking.id)
            .order_by(BookingParticipant.position)
        )
    ).all()
    made: list[Ticket] = []
    for person in people:
        if person.id in existing:
            made.append(existing[person.id])
            continue
        ticket = Ticket(booking_id=booking.id, participant_id=person.id)
        db.add(ticket)
        made.append(ticket)
    await db.flush()
    return made


async def announce_confirmed(
    db: AsyncSession, booking: Booking, *, late_payment: bool = False
) -> None:
    """
    A booking became confirmed: make its tickets and queue the emails, one queued event per
    recipient, each with its own dedupe key. A repeat of this call (a retried request, a repeated
    payment callback) therefore queues nothing new, and a failed send retries only that one
    person's email, never anyone else's.
    """
    await issue_tickets(db, booking)
    await publish_event(
        db,
        event_type="booking.confirmed",
        payload={
            "booking_id": str(booking.id),
            **({"late_payment": True} if late_payment else {}),
        },
        dedupe_key=f"booking.confirmed:{booking.id}",
    )
    people = (
        await db.scalars(
            select(BookingParticipant)
            .where(BookingParticipant.booking_id == booking.id, BookingParticipant.position > 1)
            .order_by(BookingParticipant.position)
        )
    ).all()
    for person in people:
        if person.email:
            await publish_event(
                db,
                event_type="booking.ticket_issued",
                payload={"booking_id": str(booking.id), "participant_id": str(person.id)},
                dedupe_key=f"booking.ticket_issued:{person.id}",
            )


def effective_status(ticket: Ticket, booking: Booking) -> str:
    if booking.status != BookingStatus.CONFIRMED:
        return "void"
    return ticket.status.value


class TicketView:
    """Everything the ticket page needs, joined up."""

    def __init__(
        self,
        ticket: Ticket,
        booking: Booking,
        person: BookingParticipant,
        event: Event,
        slot: EventSlot,
    ) -> None:
        self.ticket = ticket
        self.booking = booking
        self.person = person
        self.event = event
        self.slot = slot


async def load_view(db: AsyncSession, ticket: Ticket) -> TicketView:
    booking = await db.get(Booking, ticket.booking_id)
    person = await db.get(BookingParticipant, ticket.participant_id)
    assert booking is not None and person is not None  # noqa: S101 - FKs guarantee both
    event = await db.get(Event, booking.event_id)
    slot = await db.get(EventSlot, booking.slot_id)
    assert event is not None and slot is not None  # noqa: S101
    return TicketView(ticket, booking, person, event, slot)


async def tickets_of_booking(db: AsyncSession, booking: Booking) -> list[TicketView]:
    tickets = (
        await db.scalars(
            select(Ticket)
            .join(BookingParticipant, BookingParticipant.id == Ticket.participant_id)
            .where(Ticket.booking_id == booking.id)
            .order_by(BookingParticipant.position)
        )
    ).all()
    return [await load_view(db, t) for t in tickets]


async def claim(db: AsyncSession, *, user: User, code: str) -> TicketView:
    """A signed-in player attaches the ticket from their emailed link to their own account."""
    ticket = await find_by_code(db, code, lock=True)
    view = await load_view(db, ticket)
    person = view.person
    if person.user_id is not None and person.user_id != user.id:
        raise ConflictError("This ticket has already been claimed.", code="already_claimed")
    if person.user_id is None:
        person.user_id = user.id
        await db.flush()
        await record_audit(
            db,
            actor_user_id=user.id,
            action="ticket.claim",
            target_type="ticket",
            target_id=ticket.id,
            context={"event_id": str(view.event.id)},
        )
    return view


async def reissue(db: AsyncSession, *, actor: User, booking: Booking, position: int) -> Ticket:
    """Invalidates the old QR of one person's ticket and gives a new one (for a leaked code)."""
    ticket = await db.scalar(
        select(Ticket)
        .join(BookingParticipant, BookingParticipant.id == Ticket.participant_id)
        .where(Ticket.booking_id == booking.id, BookingParticipant.position == position)
        .with_for_update()
    )
    if ticket is None:
        raise NotFoundError("Ticket not found.")
    if ticket.status == TicketStatus.CHECKED_IN:
        raise ConflictError("This ticket has already been used.", code="already_checked_in")
    ticket.qr_version += 1
    await db.flush()
    await record_audit(
        db,
        actor_user_id=actor.id,
        action="ticket.reissue",
        target_type="ticket",
        target_id=ticket.id,
        context={"event_id": str(booking.event_id)},
    )
    return ticket


async def check_in(
    db: AsyncSession, *, actor: User, event: Event, code: str, now: datetime
) -> tuple[str, TicketView]:
    """
    Scans a ticket at the door. Returns ("checked_in" | "already_checked_in", view).
    Scanning twice is not an error. The ticket row is locked first, so two phones scanning the
    same code at once agree on who was first. A cancelled booking, or a ticket for another
    event, is refused by name.
    """
    ticket = await find_by_code(db, code, lock=True)
    view = await load_view(db, ticket)
    if view.event.id != event.id:
        raise ConflictError("This ticket is for a different event.", code="wrong_event")
    booking = await db.scalar(
        select(Booking)
        .where(Booking.id == ticket.booking_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    assert booking is not None  # noqa: S101
    if booking.status != BookingStatus.CONFIRMED:
        raise ConflictError("This ticket is void: the booking is not confirmed.", code="void")
    if ticket.status == TicketStatus.CHECKED_IN:
        return "already_checked_in", view
    if ticket.status != TicketStatus.VALID:
        raise ConflictError("This ticket is void.", code="void")
    if check_in_hook is not None:
        await check_in_hook()
    await db.execute(
        update(Ticket)
        .where(Ticket.id == ticket.id)
        .values(status=TicketStatus.CHECKED_IN, checked_in_at=now, checked_in_by=actor.id)
        .execution_options(synchronize_session=False)
    )
    await db.refresh(ticket)
    await record_audit(
        db,
        actor_user_id=actor.id,
        action="ticket.check_in",
        target_type="ticket",
        target_id=ticket.id,
        context={
            **({"organization_id": str(event.organization_id)} if event.organization_id else {}),
            "event_id": str(event.id),
        },
    )
    return "checked_in", view


def ticket_out(view: TicketView) -> TicketOut:
    t, p, e, sl = view.ticket, view.person, view.event, view.slot
    return TicketOut(
        code=make_code(t),
        status=effective_status(t, view.booking),
        holder_name=p.full_name,
        position=p.position,
        booking_reference=view.booking.reference,
        event=TicketEventInfo(
            id=e.id,
            title=e.title,
            starts_at=e.starts_at,
            ends_at=e.ends_at,
            venue_name=e.venue_name,
            venue_address=e.venue_address,
        ),
        slot=BookingSlotInfo(id=sl.id, label=sl.label, starts_at=sl.starts_at, ends_at=sl.ends_at),
        checked_in_at=t.checked_in_at,
        claimed=p.position > 1 and p.user_id is not None,
    )


async def my_tickets(db: AsyncSession, *, user: User) -> list[TicketView]:
    """Tickets in bookings I made, and tickets I claimed, for events that have not ended."""
    rows = (
        await db.scalars(
            select(Ticket)
            .join(BookingParticipant, BookingParticipant.id == Ticket.participant_id)
            .join(Booking, Booking.id == Ticket.booking_id)
            .join(Event, Event.id == Booking.event_id)
            .where(
                or_(BookingParticipant.user_id == user.id, Booking.booker_user_id == user.id),
                Booking.status == BookingStatus.CONFIRMED,
                Event.ends_at > func.now(),
            )
            .order_by(Event.starts_at, Booking.id, BookingParticipant.position)
        )
    ).all()
    return [await load_view(db, t) for t in rows]
