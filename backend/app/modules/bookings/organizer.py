"""
What the people running an event need on the day: the roster, a spreadsheet of it, the tee
sheet, and a way to write to everyone booked. Organizers see contact details here (they need
them to run the event, and the booking form says so); the CSV is audited and rate limited.
"""

import csv
import io
import uuid
from collections import defaultdict
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors.exceptions import ValidationError
from app.core.rate_limit.limiter import hit
from app.modules.audit.service import record as record_audit
from app.modules.bookings.models import (
    ACTIVE_STATUSES,
    Booking,
    BookingAnswer,
    BookingParticipant,
    BookingStatus,
    EventMessage,
    Ticket,
)
from app.modules.bookings.schemas import (
    AnswerOut,
    BookingSlotInfo,
    RegistrationRow,
    RosterParticipant,
    TeeSheetSlot,
)
from app.modules.bookings.tickets import effective_status
from app.modules.domain_events.service import publish as publish_event
from app.modules.events.models import Event, EventQuestion, EventSlot
from app.modules.identity.models import User

CSV_EXPORTS_PER_HOUR = 5
MESSAGES_PER_HOUR = 5
_FORMULA_STARTS = ("=", "+", "-", "@", "\t", "\r")


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def defuse(cell: Any) -> Any:
    """A spreadsheet runs text that starts with = + - @ as a formula. Prefix those with an
    apostrophe so they show as plain text. Numbers are left alone."""
    if isinstance(cell, str) and cell.startswith(_FORMULA_STARTS):
        return "'" + cell
    return cell


def _org_context(event: Event) -> dict[str, str]:
    return {"organization_id": str(event.organization_id)} if event.organization_id else {}


async def _rows(db: AsyncSession, bookings: list[Booking]) -> list[RegistrationRow]:
    if not bookings:
        return []
    ids = [b.id for b in bookings]
    people_by_booking: dict[uuid.UUID, list[BookingParticipant]] = defaultdict(list)
    for p in (
        await db.scalars(
            select(BookingParticipant)
            .where(BookingParticipant.booking_id.in_(ids))
            .order_by(BookingParticipant.booking_id, BookingParticipant.position)
        )
    ).all():
        people_by_booking[p.booking_id].append(p)
    tickets = {
        t.participant_id: t
        for t in (await db.scalars(select(Ticket).where(Ticket.booking_id.in_(ids)))).all()
    }
    position_of = {p.id: p.position for ps in people_by_booking.values() for p in ps}
    answers_by_booking: dict[uuid.UUID, list[AnswerOut]] = defaultdict(list)
    for answer, key in (
        await db.execute(
            select(BookingAnswer, EventQuestion.key)
            .join(EventQuestion, EventQuestion.id == BookingAnswer.question_id)
            .where(BookingAnswer.booking_id.in_(ids))
            .order_by(EventQuestion.position, EventQuestion.key)
        )
    ).all():
        answers_by_booking[answer.booking_id].append(
            AnswerOut(
                question_key=key, position=position_of[answer.participant_id], value=answer.value
            )
        )
    slot_ids = {b.slot_id for b in bookings}
    slots = {
        s.id: s
        for s in (await db.scalars(select(EventSlot).where(EventSlot.id.in_(slot_ids)))).all()
    }
    out: list[RegistrationRow] = []
    for b in bookings:
        slot = slots[b.slot_id]
        people = people_by_booking[b.id]
        out.append(
            RegistrationRow(
                booking_id=b.id,
                reference=b.reference,
                status=b.status,
                created_at=b.created_at,
                slot=BookingSlotInfo(
                    id=slot.id, label=slot.label, starts_at=slot.starts_at, ends_at=slot.ends_at
                ),
                party_size=b.party_size,
                amount_minor=b.amount_minor,
                currency=b.currency,
                booker_name=people[0].full_name if people else "",
                participants=[
                    RosterParticipant(
                        position=p.position,
                        full_name=p.full_name,
                        email=p.email,
                        phone=p.phone,
                        listed=p.listed,
                        claimed=p.position > 1 and p.user_id is not None,
                        ticket_status=(
                            effective_status(tickets[p.id], b) if p.id in tickets else None
                        ),
                        checked_in_at=tickets[p.id].checked_in_at if p.id in tickets else None,
                    )
                    for p in people
                ],
                answers=answers_by_booking[b.id],
            )
        )
    return out


async def registrations(
    db: AsyncSession,
    *,
    event: Event,
    status: BookingStatus | None,
    slot_id: uuid.UUID | None,
    q: str | None,
    limit: int,
    offset: int,
) -> tuple[list[RegistrationRow], int]:
    where: list[Any] = [Booking.event_id == event.id]
    if status is not None:
        where.append(Booking.status == status)
    if slot_id is not None:
        where.append(Booking.slot_id == slot_id)
    if q:
        like = f"%{_escape_like(q.strip())}%"
        named = select(BookingParticipant.booking_id).where(
            BookingParticipant.full_name.ilike(like, escape="\\")
        )
        where.append(or_(Booking.reference.ilike(like, escape="\\"), Booking.id.in_(named)))
    total = await db.scalar(select(func.count()).select_from(Booking).where(*where))
    bookings = list(
        (
            await db.scalars(
                select(Booking)
                .where(*where)
                .order_by(Booking.created_at, Booking.id)
                .limit(limit)
                .offset(offset)
            )
        ).all()
    )
    return await _rows(db, bookings), int(total or 0)


async def tee_sheet(db: AsyncSession, *, event: Event) -> list[TeeSheetSlot]:
    slots = (
        await db.scalars(
            select(EventSlot)
            .where(EventSlot.event_id == event.id)
            .order_by(EventSlot.starts_at, EventSlot.position, EventSlot.id)
        )
    ).all()
    bookings = list(
        (
            await db.scalars(
                select(Booking)
                .where(Booking.event_id == event.id, Booking.status.in_(ACTIVE_STATUSES))
                .order_by(Booking.created_at, Booking.id)
            )
        ).all()
    )
    by_slot: dict[uuid.UUID, list[RegistrationRow]] = defaultdict(list)
    for row in await _rows(db, bookings):
        by_slot[row.slot.id].append(row)
    return [
        TeeSheetSlot(
            slot=BookingSlotInfo(id=s.id, label=s.label, starts_at=s.starts_at, ends_at=s.ends_at),
            capacity=s.capacity,
            seats_confirmed=s.seats_confirmed,
            seats_held=s.seats_held,
            bookings=by_slot[s.id],
        )
        for s in slots
    ]


def _cell(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, list):
        return ", ".join(str(v) for v in value)
    if isinstance(value, bool):
        return "yes" if value else "no"
    return value


async def export_csv(db: AsyncSession, *, actor: User, event: Event) -> str:
    """One row per person. Audited and limited to a few an hour, because it is the whole guest
    list with phone numbers."""
    await hit(
        f"ratelimit:registrations_csv:{actor.id}",
        limit=CSV_EXPORTS_PER_HOUR,
        window_seconds=3600,
    )
    questions = list(
        (
            await db.scalars(
                select(EventQuestion)
                .where(EventQuestion.event_id == event.id)
                .order_by(EventQuestion.position, EventQuestion.key)
            )
        ).all()
    )
    bookings = list(
        (
            await db.scalars(
                select(Booking)
                .where(Booking.event_id == event.id)
                .order_by(Booking.created_at, Booking.id)
            )
        ).all()
    )
    rows = await _rows(db, bookings)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "reference",
            "booking_status",
            "slot",
            "slot_starts_at",
            "person",
            "name",
            "email",
            "phone",
            "ticket_status",
            "checked_in_at",
            "amount_minor",
            "currency",
            *[q.key for q in questions],
        ]
    )
    for r in rows:
        answers = {(a.question_key, a.position): a.value for a in r.answers}
        for p in r.participants:
            cells = [
                r.reference,
                r.status.value,
                r.slot.label or "",
                r.slot.starts_at.isoformat(),
                p.position,
                p.full_name,
                p.email or "",
                p.phone or "",
                p.ticket_status or "",
                p.checked_in_at.isoformat() if p.checked_in_at else "",
                r.amount_minor if p.position == 1 else "",
                r.currency if p.position == 1 else "",
                *[_cell(answers.get((q.key, p.position))) for q in questions],
            ]
            writer.writerow([defuse(c) for c in cells])
    await record_audit(
        db,
        actor_user_id=actor.id,
        action="event.export_registrations",
        target_type="event",
        target_id=event.id,
        context={
            **_org_context(event),
            "event_id": str(event.id),
            "rows": sum(len(r.participants) for r in rows),
        },
    )
    return buffer.getvalue()


async def send_message(
    db: AsyncSession,
    *,
    actor: User,
    event: Event,
    subject: str,
    body: str,
    slot_id: uuid.UUID | None,
) -> EventMessage:
    """
    Emails every confirmed booker of the event (or of one slot) through the queue, one queued
    email per booking so a failure retries that one person and nobody gets two. The organizer
    gets a count back, never the addresses.
    """
    await hit(f"ratelimit:event_message:{actor.id}", limit=MESSAGES_PER_HOUR, window_seconds=3600)
    if slot_id is not None:
        slot = await db.get(EventSlot, slot_id)
        if slot is None or slot.event_id != event.id:
            raise ValidationError(
                "That time slot does not belong to this event.", code="invalid_slot"
            )
    where: list[Any] = [Booking.event_id == event.id, Booking.status == BookingStatus.CONFIRMED]
    if slot_id is not None:
        where.append(Booking.slot_id == slot_id)
    booking_ids = list(
        (await db.scalars(select(Booking.id).where(*where).order_by(Booking.id))).all()
    )
    message = EventMessage(
        event_id=event.id,
        slot_id=slot_id,
        sent_by=actor.id,
        subject=subject,
        body=body,
        recipient_count=len(booking_ids),
    )
    db.add(message)
    await db.flush()
    for booking_id in booking_ids:
        await publish_event(
            db,
            event_type="event.message",
            payload={"message_id": str(message.id), "booking_id": str(booking_id)},
            dedupe_key=f"event.message:{message.id}:{booking_id}",
        )
    await record_audit(
        db,
        actor_user_id=actor.id,
        action="event.message",
        target_type="event",
        target_id=event.id,
        context={
            **_org_context(event),
            "event_id": str(event.id),
            "message_id": str(message.id),
            "recipients": len(booking_ids),
        },
    )
    return message
