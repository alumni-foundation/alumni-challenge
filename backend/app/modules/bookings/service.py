"""
Making, reading and cancelling bookings.

The order inside `create_booking` matters and is the heart of the "never oversell" promise:
cheap checks first (no locks held), then lock the slot, then re-check the things that can have
changed, then take the seats. Everything that decides who gets a seat uses the database clock.
"""

import hashlib
import json
import secrets
import uuid
from datetime import timedelta
from typing import Any

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors.exceptions import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ValidationError,
)
from app.core.rate_limit.limiter import hit
from app.modules.audit.service import record as record_audit
from app.modules.bookings import seats
from app.modules.bookings.answers import validate_answers
from app.modules.bookings.models import (
    ACTIVE_STATUSES,
    Booking,
    BookingAnswer,
    BookingConsent,
    BookingParticipant,
    BookingStatus,
)
from app.modules.bookings.schemas import (
    AnswerOut,
    BookingBrief,
    BookingConsentOut,
    BookingCreate,
    BookingEventInfo,
    BookingOut,
    BookingSlotInfo,
    ParticipantOut,
    ParticipantUpdate,
)
from app.modules.bookings.tickets import issue_tickets
from app.modules.domain_events.service import publish as publish_event
from app.modules.events import access
from app.modules.events.models import (
    Event,
    EventConsent,
    EventQuestion,
    EventSlot,
    EventStatus,
)
from app.modules.events.service import registration_state
from app.modules.files.urls import public_file_path
from app.modules.identity.models import User

MAX_PENDING_HOLDS = 3
BOOKINGS_PER_HOUR = 20
_REFERENCE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # no 0/O, 1/I/L

_REGISTRATION_MESSAGES = {
    "draft": "This event is not open for booking.",
    "cancelled": "This event has been cancelled.",
    "ended": "This event has already ended.",
    "closed": "Registration for this event is closed.",
    "not_open_yet": "Registration for this event has not opened yet.",
}


async def db_now(db: AsyncSession) -> Any:
    return await db.scalar(select(func.clock_timestamp()))


def request_hash(event_id: uuid.UUID, body: BookingCreate) -> str:
    canonical = json.dumps(
        {"event": str(event_id), "body": body.model_dump(mode="json")},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


async def _new_reference(db: AsyncSession) -> str:
    for _ in range(10):
        ref = "AC-" + "".join(secrets.choice(_REFERENCE_ALPHABET) for _ in range(8))
        if await db.scalar(select(Booking.id).where(Booking.reference == ref)) is None:
            return ref
    raise ConflictError("Could not make a booking reference. Try again.", code="busy")


async def _find_by_key(db: AsyncSession, user: User, key: str) -> Booking | None:
    return await db.scalar(
        select(Booking)
        .where(Booking.booker_user_id == user.id, Booking.idempotency_key == key)
        .execution_options(populate_existing=True)
    )


def _replay(existing: Booking, sha: str) -> Booking:
    if existing.request_sha256 != sha:
        raise ValidationError(
            "This Idempotency-Key was already used for a different booking.",
            code="idempotency_key_reused",
        )
    return existing


async def _expire(db: AsyncSession, slot: EventSlot) -> int:
    expired = await seats.release_expired_holds(db, slot)
    for booking in expired:
        await publish_event(
            db, event_type="booking.expired", payload={"booking_id": str(booking.id)}
        )
    return len(expired)


async def _check_consents(
    db: AsyncSession, event: Event, accepted: list[str]
) -> list[EventConsent]:
    consents = list(
        (await db.scalars(select(EventConsent).where(EventConsent.event_id == event.id))).all()
    )
    keys = {c.key for c in consents}
    unknown = set(accepted) - keys
    if unknown:
        raise ValidationError("Unknown consent.", code="unknown_consent")
    missing = [c for c in consents if c.required and c.key not in accepted]
    if missing:
        raise ValidationError(
            "You need to accept: " + "; ".join(c.key for c in missing) + ".",
            code="consent_required",
        )
    return [c for c in consents if c.key in accepted]


async def create_booking(
    db: AsyncSession,
    *,
    user: User,
    event_id: uuid.UUID,
    body: BookingCreate,
    idempotency_key: str,
) -> Booking:
    if not 1 <= len(idempotency_key) <= 255:
        raise ValidationError("The Idempotency-Key is missing or too long.", code="idempotency_key")
    sha = request_hash(event_id, body)

    existing = await _find_by_key(db, user, idempotency_key)
    if existing is not None:
        return _replay(existing, sha)

    event, _roles = await access.get_event_for_viewer(db, event_id=event_id, viewer=user)
    state = registration_state(event, await db_now(db))
    if state != "open":
        raise ConflictError(
            _REGISTRATION_MESSAGES.get(state, "Booking is not open."), code=f"registration_{state}"
        )

    slot_ids = {
        row
        for row in (
            await db.scalars(select(EventSlot.id).where(EventSlot.event_id == event.id))
        ).all()
    }
    if body.slot_id not in slot_ids:
        raise ValidationError("That time slot does not belong to this event.", code="invalid_slot")

    party = len(body.participants)
    if party > event.max_party_size:
        raise ValidationError(
            f"At most {event.max_party_size} people can be booked together.",
            code="party_too_large",
        )
    if party > 1 and not body.others_consent_confirmed:
        raise ValidationError(
            "Please confirm you may share the other people's details.",
            code="others_consent_required",
        )

    answers = await validate_answers(db, event_id=event.id, party_size=party, answers=body.answers)
    accepted = await _check_consents(db, event, body.accepted_consents)

    await hit(f"ratelimit:booking_create:{user.id}", limit=BOOKINGS_PER_HOUR, window_seconds=3600)

    pending = await db.scalar(
        select(func.count())
        .select_from(Booking)
        .where(
            Booking.booker_user_id == user.id,
            Booking.status == BookingStatus.PENDING_PAYMENT,
            Booking.hold_expires_at > func.clock_timestamp(),
        )
    )
    if (pending or 0) >= MAX_PENDING_HOLDS:
        raise ConflictError(
            "You already have several bookings waiting for payment. Finish or cancel one first.",
            code="too_many_holds",
        )

    slot = await seats.lock_slot(db, body.slot_id)
    await _expire(db, slot)

    # Things that can have changed while we waited for the lock.
    existing = await _find_by_key(db, user, idempotency_key)
    if existing is not None:
        return _replay(existing, sha)
    already = await db.scalar(
        select(Booking.id).where(
            Booking.event_id == event.id,
            Booking.booker_user_id == user.id,
            Booking.status.in_(ACTIVE_STATUSES),
        )
    )
    if already is not None:
        raise ConflictError("You already have a booking for this event.", code="already_booked")

    free = seats.free_seats(slot)
    if free is not None and free < party:
        raise ConflictError("There are not enough places left in that time slot.", code="sold_out")

    if seats.capacity_check_hook is not None:
        await seats.capacity_check_hook()

    paid = event.price_minor > 0
    now = await db_now(db)
    booking = Booking(
        event_id=event.id,
        slot_id=slot.id,
        booker_user_id=user.id,
        party_size=party,
        status=BookingStatus.PENDING_PAYMENT if paid else BookingStatus.CONFIRMED,
        unit_price_minor=event.price_minor,
        amount_minor=event.price_minor * party,
        currency=event.currency,
        hold_expires_at=now + timedelta(minutes=event.hold_minutes) if paid else None,
        confirmed_at=None if paid else now,
        reference=await _new_reference(db),
        idempotency_key=idempotency_key,
        request_sha256=sha,
    )
    try:
        async with db.begin_nested():
            db.add(booking)
            await db.flush()
            await seats.take(db, slot, party, hold=paid)
    except IntegrityError as exc:
        name = str(exc.orig)
        if "uq_bookings_one_active_per_person_per_event" in name:
            raise ConflictError(
                "You already have a booking for this event.", code="already_booked"
            ) from exc
        if "uq_bookings_booker_idempotency_key" in name:
            existing = await _find_by_key(db, user, idempotency_key)
            if existing is not None:
                return _replay(existing, sha)
        raise

    for position, person in enumerate(body.participants, start=1):
        db.add(
            BookingParticipant(
                booking_id=booking.id,
                position=position,
                full_name=person.full_name,
                email=user.email if position == 1 else person.email,
                phone=person.phone,
                user_id=user.id if position == 1 else None,
                listed=person.listed,
            )
        )
    await db.flush()
    by_position = {
        p.position: p
        for p in (
            await db.scalars(
                select(BookingParticipant).where(BookingParticipant.booking_id == booking.id)
            )
        ).all()
    }
    for a in answers:
        db.add(
            BookingAnswer(
                booking_id=booking.id,
                participant_id=by_position[a.position].id,
                question_id=a.question_id,
                value=a.value,
            )
        )
    for consent in accepted:
        db.add(
            BookingConsent(
                booking_id=booking.id,
                consent_id=consent.id,
                version=consent.version,
                text_sha256=hashlib.sha256(consent.text.encode()).hexdigest(),
                accepted_at=now,
            )
        )
    await db.flush()

    await record_audit(
        db,
        actor_user_id=user.id,
        action="booking.create",
        target_type="booking",
        target_id=booking.id,
        context={
            **({"organization_id": str(event.organization_id)} if event.organization_id else {}),
            "event_id": str(event.id),
            "party_size": party,
            "status": booking.status.value,
        },
    )
    if booking.status == BookingStatus.CONFIRMED:
        await issue_tickets(db, booking)
        await publish_event(
            db, event_type="booking.confirmed", payload={"booking_id": str(booking.id)}
        )
    return booking


# ----------------------------------------------------------------------------- reading


async def get_booking(db: AsyncSession, *, booking_id: uuid.UUID, viewer: User) -> Booking:
    """The booker, or someone who runs the event. Anyone else: 404."""
    booking = await db.get(Booking, booking_id)
    if booking is None:
        raise NotFoundError("Booking not found.")
    if booking.booker_user_id == viewer.id:
        return booking
    event = await db.get(Event, booking.event_id)
    if event is None:  # pragma: no cover - FK guarantees it
        raise NotFoundError("Booking not found.")
    roles = await access.event_roles(db, user=viewer, organization_id=event.organization_id)
    if not roles & access.MANAGER_ROLES:
        raise NotFoundError("Booking not found.")
    return booking


def _can_cancel(booking: Booking, event: Event, now: Any) -> bool:
    if now >= event.starts_at:
        return False
    if booking.status in (BookingStatus.PENDING_PAYMENT, BookingStatus.WAITLISTED):
        return True
    return booking.status == BookingStatus.CONFIRMED and booking.amount_minor == 0


async def build_out(db: AsyncSession, booking: Booking) -> BookingOut:
    event = await db.get(Event, booking.event_id)
    slot = await db.get(EventSlot, booking.slot_id)
    assert event is not None and slot is not None  # noqa: S101 - FKs guarantee both
    participants = (
        await db.scalars(
            select(BookingParticipant)
            .where(BookingParticipant.booking_id == booking.id)
            .order_by(BookingParticipant.position)
        )
    ).all()
    by_id = {p.id: p for p in participants}
    answers = (
        await db.execute(
            select(BookingAnswer, EventQuestion.key, EventQuestion.position)
            .join(EventQuestion, EventQuestion.id == BookingAnswer.question_id)
            .where(BookingAnswer.booking_id == booking.id)
            .order_by(EventQuestion.position, EventQuestion.key)
        )
    ).all()
    consents = (
        await db.execute(
            select(BookingConsent, EventConsent.key)
            .join(EventConsent, EventConsent.id == BookingConsent.consent_id)
            .where(BookingConsent.booking_id == booking.id)
            .order_by(EventConsent.key)
        )
    ).all()
    return BookingOut(
        id=booking.id,
        reference=booking.reference,
        status=booking.status,
        event=BookingEventInfo(
            id=event.id,
            title=event.title,
            category=event.category,
            starts_at=event.starts_at,
            ends_at=event.ends_at,
            venue_name=event.venue_name,
            poster_url=public_file_path(event.poster_file_id) if event.poster_file_id else None,
        ),
        slot=BookingSlotInfo(
            id=slot.id, label=slot.label, starts_at=slot.starts_at, ends_at=slot.ends_at
        ),
        party_size=booking.party_size,
        unit_price_minor=booking.unit_price_minor,
        amount_minor=booking.amount_minor,
        currency=booking.currency,
        hold_expires_at=booking.hold_expires_at,
        created_at=booking.created_at,
        confirmed_at=booking.confirmed_at,
        cancelled_at=booking.cancelled_at,
        cancel_reason=booking.cancel_reason,
        can_cancel=_can_cancel(booking, event, await db_now(db)),
        participants=[
            ParticipantOut(
                position=p.position,
                full_name=p.full_name,
                email=p.email,
                phone=p.phone,
                listed=p.listed,
                claimed=p.position > 1 and p.user_id is not None,
            )
            for p in participants
        ],
        answers=[
            AnswerOut(question_key=key, position=by_id[a.participant_id].position, value=a.value)
            for a, key, _pos in answers
        ],
        consents=[
            BookingConsentOut(key=key, version=c.version, accepted_at=c.accepted_at)
            for c, key in consents
        ],
    )


async def list_my_bookings(
    db: AsyncSession,
    *,
    user: User,
    status: BookingStatus | None,
    limit: int,
    offset: int,
) -> tuple[list[Booking], int]:
    where = [Booking.booker_user_id == user.id]
    if status is not None:
        where.append(Booking.status == status)
    total = await db.scalar(select(func.count()).select_from(Booking).where(*where))
    rows = (
        await db.scalars(
            select(Booking)
            .where(*where)
            .order_by(Booking.created_at.desc(), Booking.id)
            .limit(limit)
            .offset(offset)
        )
    ).all()
    return list(rows), int(total or 0)


async def my_booking_brief(
    db: AsyncSession, *, event_id: uuid.UUID, user: User | None
) -> BookingBrief | None:
    """The caller's current booking for an event, if any (shown on the event page)."""
    if user is None:
        return None
    booking = await db.scalar(
        select(Booking)
        .where(
            Booking.event_id == event_id,
            Booking.booker_user_id == user.id,
            Booking.status.in_(ACTIVE_STATUSES),
        )
        .order_by(Booking.created_at.desc())
        .limit(1)
    )
    if booking is None:
        return None
    return BookingBrief(
        id=booking.id,
        reference=booking.reference,
        status=booking.status,
        slot_id=booking.slot_id,
        party_size=booking.party_size,
        hold_expires_at=booking.hold_expires_at,
    )


# ----------------------------------------------------------------------------- changing


async def cancel_booking(
    db: AsyncSession,
    *,
    actor: User,
    booking_id: uuid.UUID,
    reason: str | None,
    as_organizer: bool = False,
) -> Booking:
    """
    Cancels a booking and gives its seats back. The booker may cancel until the event starts,
    except a paid, confirmed booking: those go through the organizer (design decision 6).
    Cancelling twice is harmless.
    """
    booking = await get_booking(db, booking_id=booking_id, viewer=actor)
    event = await db.get(Event, booking.event_id)
    assert event is not None  # noqa: S101 - FK guarantees it
    is_booker = booking.booker_user_id == actor.id
    if not is_booker or as_organizer:
        roles = await access.event_roles(db, user=actor, organization_id=event.organization_id)
        if not roles & access.MANAGER_ROLES:
            raise NotFoundError("Booking not found.")

    slot = await seats.lock_slot(db, booking.slot_id)
    booking = await db.scalar(
        select(Booking)
        .where(Booking.id == booking.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )  # type: ignore[assignment]
    assert booking is not None  # noqa: S101
    if booking.status == BookingStatus.CANCELLED:
        return booking
    if booking.status not in ACTIVE_STATUSES:
        raise ConflictError("This booking can no longer be cancelled.", code="not_cancellable")

    if not as_organizer:
        if await db_now(db) >= event.starts_at:
            raise ConflictError("The event has already started.", code="event_started")
        if booking.status == BookingStatus.CONFIRMED and booking.amount_minor > 0:
            raise ForbiddenError(
                "A paid booking is cancelled by the organizer. Contact them to ask for a refund.",
            )

    was = booking.status
    await seats.release(db, slot, booking.party_size, was=was)
    booking.status = BookingStatus.CANCELLED
    booking.hold_expires_at = None
    booking.cancelled_at = await db_now(db)
    booking.cancelled_by = actor.id
    booking.cancel_reason = reason
    await db.flush()
    await record_audit(
        db,
        actor_user_id=actor.id,
        action="booking.cancel",
        target_type="booking",
        target_id=booking.id,
        context={
            **({"organization_id": str(event.organization_id)} if event.organization_id else {}),
            "event_id": str(event.id),
            "was": was.value,
            "by_organizer": not is_booker,
        },
    )
    await publish_event(db, event_type="booking.cancelled", payload={"booking_id": str(booking.id)})
    return booking


async def update_participant(
    db: AsyncSession,
    *,
    actor: User,
    booking_id: uuid.UUID,
    position: int,
    body: ParticipantUpdate,
) -> Booking:
    booking = await db.get(Booking, booking_id)
    if booking is None or booking.booker_user_id != actor.id:
        raise NotFoundError("Booking not found.")
    if booking.status not in ACTIVE_STATUSES:
        raise ConflictError("This booking can no longer be changed.", code="not_changeable")
    event = await db.get(Event, booking.event_id)
    assert event is not None  # noqa: S101
    if event.status == EventStatus.CANCELLED or await db_now(db) >= event.starts_at:
        raise ConflictError("This booking can no longer be changed.", code="not_changeable")
    person = await db.scalar(
        select(BookingParticipant).where(
            BookingParticipant.booking_id == booking.id, BookingParticipant.position == position
        )
    )
    if person is None:
        raise NotFoundError("Participant not found.")
    changes = body.model_dump(exclude_unset=True)
    if position == 1 and "email" in changes:
        raise ValidationError(
            "Your email comes from your account and cannot be changed here.", code="invalid_email"
        )
    if "full_name" in changes and changes["full_name"] is None:
        raise ValidationError("A name is needed.", code="invalid_name")
    for field in ("full_name", "email", "phone"):
        if field in changes:
            setattr(person, field, changes[field])
    if changes.get("listed") is not None:
        person.listed = changes["listed"]
    await db.flush()
    return booking


async def cancel_all_for_event(db: AsyncSession, *, actor: User, event: Event, reason: str) -> int:
    """The organizer cancelled the event: every active booking ends and every seat is freed.
    Paid ones are left for the refund queue (slice 5.5) by their `cancelled` status and amount."""
    slot_ids = (
        await db.scalars(
            select(EventSlot.id).where(EventSlot.event_id == event.id).order_by(EventSlot.id)
        )
    ).all()
    count = 0
    for slot_id in slot_ids:
        slot = await seats.lock_slot(db, slot_id)
        active = (
            await db.scalars(
                select(Booking)
                .where(Booking.slot_id == slot.id, Booking.status.in_(ACTIVE_STATUSES))
                .order_by(Booking.id)
                .with_for_update()
            )
        ).all()
        now = await db_now(db)
        for booking in active:
            await seats.release(db, slot, booking.party_size, was=booking.status)
            booking.status = BookingStatus.CANCELLED
            booking.hold_expires_at = None
            booking.cancelled_at = now
            booking.cancelled_by = actor.id
            booking.cancel_reason = f"Event cancelled: {reason}"[:500]
            await publish_event(
                db,
                event_type="booking.event_cancelled",
                payload={"booking_id": str(booking.id)},
            )
            count += 1
    await db.flush()
    return count


async def expire_due_holds(db: AsyncSession) -> int:
    """
    Worker sweep: ends holds that ran out of time on slots nobody has touched since. Booking
    already does this for the slot it works on, so this only tidies up quiet slots.
    """
    slot_ids = (
        await db.scalars(
            select(Booking.slot_id)
            .where(
                Booking.status == BookingStatus.PENDING_PAYMENT,
                Booking.hold_expires_at < func.clock_timestamp(),
            )
            .distinct()
        )
    ).all()
    total = 0
    for slot_id in sorted(slot_ids):
        slot = await seats.lock_slot(db, slot_id)
        total += await _expire(db, slot)
    return total


# ----------------------------------------------------------------- account deletion & export


async def settle_bookings_for_deletion(db: AsyncSession, *, user: User) -> None:
    """
    Run before an account is anonymized (design decision 10). A paid, confirmed booking for an
    event that has not ended blocks deletion: it must pass or be refunded first. Everything
    else still open is cancelled so the seats are released, and the person's own details are
    wiped from every booking they made.
    """
    now = await db_now(db)
    open_rows = (
        await db.execute(
            select(Booking, Event)
            .join(Event, Event.id == Booking.event_id)
            .where(Booking.booker_user_id == user.id, Booking.status.in_(ACTIVE_STATUSES))
            .order_by(Booking.id)
        )
    ).all()
    for booking, event in open_rows:
        if (
            booking.status == BookingStatus.CONFIRMED
            and booking.amount_minor > 0
            and event.ends_at > now
        ):
            raise ConflictError(
                "You have a paid booking for an event that has not happened yet. Your account "
                "can be deleted once the event has passed or the booking has been refunded.",
                code="paid_booking_open",
            )
    for booking, event in open_rows:
        if event.starts_at > now:
            await cancel_booking(db, actor=user, booking_id=booking.id, reason="Account deleted")

    mine = select(Booking.id).where(Booking.booker_user_id == user.id)
    first_ids = select(BookingParticipant.id).where(
        BookingParticipant.booking_id.in_(mine), BookingParticipant.position == 1
    )
    await db.execute(delete(BookingAnswer).where(BookingAnswer.participant_id.in_(first_ids)))
    await db.execute(
        update(BookingParticipant)
        .where(BookingParticipant.booking_id.in_(mine), BookingParticipant.position == 1)
        .values(full_name="Deleted user", email=None, phone=None, user_id=None, listed=False)
    )
    await db.execute(
        update(BookingParticipant)
        .where(BookingParticipant.user_id == user.id, BookingParticipant.position > 1)
        .values(full_name="Deleted user", email=None, phone=None, user_id=None, listed=False)
    )


async def export_bookings(db: AsyncSession, *, user: User) -> list[dict[str, Any]]:
    rows = (
        await db.execute(
            select(Booking, Event.title)
            .join(Event, Event.id == Booking.event_id)
            .where(Booking.booker_user_id == user.id)
            .order_by(Booking.created_at, Booking.id)
        )
    ).all()
    out: list[dict[str, Any]] = []
    for booking, title in rows:
        people = (
            await db.scalars(
                select(BookingParticipant)
                .where(BookingParticipant.booking_id == booking.id)
                .order_by(BookingParticipant.position)
            )
        ).all()
        out.append(
            {
                "reference": booking.reference,
                "event": title,
                "status": booking.status.value,
                "party_size": booking.party_size,
                "amount_minor": booking.amount_minor,
                "currency": booking.currency,
                "booked_at": booking.created_at.isoformat(),
                # Other people's contact details stay out; only the names given for them.
                "people": [
                    {"full_name": p.full_name}
                    if p.position > 1
                    else {"full_name": p.full_name, "email": p.email, "phone": p.phone}
                    for p in people
                ],
            }
        )
    return out
