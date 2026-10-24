"""
Paying by hand (manual M-Pesa): the booker pays the organizer's paybill or till, pastes the
M-Pesa code, and an organizer matches it to a payment and confirms it.

The rules that matter, in one place:

* A code belongs to one booking for ever (a database unique index; the message says only that it
  was used, never whose).
* Only the booker sends a code. Only an organization admin confirms, rejects or refunds. A
  stranger gets a 404 for any booking that is not theirs, so nothing about it leaks.
* Confirming is idempotent: a second click changes nothing and queues nothing.
* A payment that turns up after the hold ran out is never lost (design section 8): if the
  places are still free the booking is confirmed again ("late payment accepted"); if they are
  gone, or the booking was cancelled, the payment is flagged `needs_refund`, the booker is told
  at once, and it waits in the organizer's refund queue. Money is never silently kept and never
  silently returned.
* Every decision writes an audit row and queues an email through the outbox.
"""

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.core.rate_limit.limiter import hit
from app.modules.audit.service import record as record_audit
from app.modules.bookings import payment_view, seats
from app.modules.bookings.models import Booking, BookingStatus, ManualPaymentState
from app.modules.bookings.service import db_now, get_booking
from app.modules.bookings.tickets import announce_confirmed
from app.modules.domain_events.service import publish as publish_event
from app.modules.events import access
from app.modules.events.models import Event, EventSlot
from app.modules.identity.models import User

CODES_PER_USER_PER_HOUR = 10
CODES_PER_BOOKING_PER_HOUR = 5


def _audit_context(event: Event, **extra: Any) -> dict[str, Any]:
    return {
        **({"organization_id": str(event.organization_id)} if event.organization_id else {}),
        "event_id": str(event.id),
        **extra,
    }


async def _lock_booking(db: AsyncSession, booking_id: uuid.UUID) -> Booking:
    booking = await db.scalar(
        select(Booking)
        .where(Booking.id == booking_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    assert booking is not None  # noqa: S101 - the caller just loaded it
    return booking


async def _admin_booking(
    db: AsyncSession, *, actor: User, booking_id: uuid.UUID
) -> tuple[Booking, Event]:
    """The booking, for an organization admin of its event. Anyone who cannot even see it: 404.
    An event manager who is not an admin may look but not decide money: 403."""
    booking = await db.get(Booking, booking_id)
    if booking is None:
        raise NotFoundError("Booking not found.")
    event = await db.get(Event, booking.event_id)
    assert event is not None  # noqa: S101 - FK guarantees it
    roles = await access.event_roles(db, user=actor, organization_id=event.organization_id)
    if not roles & access.MANAGER_ROLES:
        raise NotFoundError("Booking not found.")
    if not roles & access.ADMIN_ROLES:
        raise ForbiddenError("Only an organization admin can confirm or refund payments.")
    return booking, event


# ------------------------------------------------------------------ the booker sends a code


async def submit_code(db: AsyncSession, *, user: User, booking_id: uuid.UUID, code: str) -> Booking:
    booking = await get_booking(db, booking_id=booking_id, viewer=user)
    if booking.booker_user_id != user.id:
        # Organizers can see the booking but only the person who paid sends their own code.
        raise NotFoundError("Booking not found.")
    event = await db.get(Event, booking.event_id)
    assert event is not None  # noqa: S101
    payee = await payment_view.manual_payee(db, event)
    if payee is None or booking.amount_minor == 0:
        raise ConflictError(
            "This booking is not paid for with an M-Pesa code.", code="not_manual_payment"
        )

    await hit(
        f"ratelimit:payment_code:{user.id}", limit=CODES_PER_USER_PER_HOUR, window_seconds=3600
    )
    await hit(
        f"ratelimit:payment_code_booking:{booking.id}",
        limit=CODES_PER_BOOKING_PER_HOUR,
        window_seconds=3600,
    )

    booking = await _lock_booking(db, booking.id)
    if booking.payment_reference_code == code and booking.payment_state in (
        ManualPaymentState.AWAITING_CONFIRMATION,
        ManualPaymentState.CONFIRMED,
    ):
        return booking  # sent twice: harmless
    if booking.payment_state not in (None, ManualPaymentState.REJECTED):
        raise ConflictError(
            "A payment code was already sent for this booking.", code="payment_already_submitted"
        )
    now = await db_now(db)
    if booking.status not in (
        BookingStatus.PENDING_PAYMENT,
        BookingStatus.EXPIRED,
        BookingStatus.CANCELLED,
    ) or not payment_view.event_still_on(event, now):
        raise ConflictError(
            "This booking can no longer take a payment code.", code="payment_not_accepted"
        )

    try:
        async with db.begin_nested():
            booking.payment_reference_code = code
            booking.payment_state = ManualPaymentState.AWAITING_CONFIRMATION
            booking.payment_submitted_at = now
            booking.payment_decided_at = None
            booking.payment_decided_by = None
            booking.payment_note = None
            await db.flush()
    except IntegrityError as exc:
        if "uq_bookings_payment_reference_code" in str(exc.orig):
            await db.refresh(booking)
            raise ConflictError(
                "That M-Pesa code has already been used for a booking.",
                code="payment_code_used",
            ) from exc
        raise

    await record_audit(
        db,
        actor_user_id=user.id,
        action="booking.payment_submitted",
        target_type="booking",
        target_id=booking.id,
        context=_audit_context(event, code=code),
    )
    await publish_event(
        db,
        event_type="booking.payment_submitted",
        payload={"booking_id": str(booking.id)},
        dedupe_key=f"booking.payment_submitted:{booking.id}:{code}",
    )
    return booking


# ----------------------------------------------------------------- the organizer decides


async def confirm(db: AsyncSession, *, actor: User, booking_id: uuid.UUID) -> Booking:
    """Marks the payment received. Idempotent."""
    booking, event = await _admin_booking(db, actor=actor, booking_id=booking_id)
    slot = await _lock_and_sweep(db, booking)
    booking = await _lock_booking(db, booking.id)

    if booking.payment_state == ManualPaymentState.CONFIRMED:
        return booking
    if booking.payment_state != ManualPaymentState.AWAITING_CONFIRMATION:
        raise ConflictError(
            "There is no payment code waiting to be confirmed on this booking.",
            code="no_payment_to_confirm",
        )
    await _settle(db, actor=actor, booking=booking, event=event, slot=slot, reason=None)
    return booking


async def mark_paid(
    db: AsyncSession, *, actor: User, booking_id: uuid.UUID, reason: str
) -> Booking:
    """An organization admin says the money arrived, with no M-Pesa code to show for it (cash,
    a bank transfer, a code that was never sent). The reason is written down and audited.
    Settles exactly like a confirmed code, late-payment rules included. Idempotent."""
    booking, event = await _admin_booking(db, actor=actor, booking_id=booking_id)
    if booking.amount_minor == 0:
        raise ConflictError("Nothing is owed on this booking.", code="not_a_paid_booking")
    slot = await _lock_and_sweep(db, booking)
    booking = await _lock_booking(db, booking.id)

    if booking.payment_state == ManualPaymentState.CONFIRMED:
        return booking
    if booking.payment_state in (ManualPaymentState.NEEDS_REFUND, ManualPaymentState.REFUNDED):
        raise ConflictError(
            "This payment has already been settled.", code="payment_already_settled"
        )
    await _settle(db, actor=actor, booking=booking, event=event, slot=slot, reason=reason)
    return booking


async def _lock_and_sweep(db: AsyncSession, booking: Booking) -> EventSlot:
    """Locks the slot and ends any hold that ran out, so the booking is judged as it really is."""
    from app.modules.bookings.service import _expire  # the same sweep booking itself uses

    slot = await seats.lock_slot(db, booking.slot_id)
    await _expire(db, slot)
    return slot


async def _settle(
    db: AsyncSession,
    *,
    actor: User,
    booking: Booking,
    event: Event,
    slot: EventSlot,
    reason: str | None,
) -> None:
    """The money is in. Confirm the booking if the places allow it, otherwise record that the
    payment must be returned. `reason` is set when the organizer marked it paid by hand."""
    by_hand = reason is not None
    now = await db_now(db)
    was = booking.status
    late = False
    owed = False
    if was == BookingStatus.PENDING_PAYMENT:
        await seats.confirm_held(db, slot, booking.party_size)
        booking.status = BookingStatus.CONFIRMED
        booking.hold_expires_at = None
        booking.confirmed_at = now
    elif was == BookingStatus.EXPIRED:
        free = seats.free_seats(slot)
        if payment_view.event_still_on(event, now) and (free is None or free >= booking.party_size):
            try:
                async with db.begin_nested():
                    booking.status = BookingStatus.CONFIRMED
                    booking.confirmed_at = now
                    await db.flush()  # may hit "one active booking per person per event"
                    await seats.take(db, slot, booking.party_size, hold=False)
                late = True
            except IntegrityError as exc:
                if "uq_bookings_one_active_per_person_per_event" not in str(exc.orig):
                    raise
                await db.refresh(booking)  # they booked again meanwhile: the money is owed back
                owed = True
        else:
            owed = True
    elif was == BookingStatus.CANCELLED:
        owed = True
    else:
        raise ConflictError(
            "This booking is not waiting for a payment.", code="payment_not_accepted"
        )

    booking.payment_state = (
        ManualPaymentState.NEEDS_REFUND if owed else ManualPaymentState.CONFIRMED
    )
    booking.paid_without_code = by_hand and booking.payment_reference_code is None
    booking.payment_decided_at = now
    booking.payment_decided_by = actor.id
    booking.payment_note = reason
    await db.flush()
    context = _audit_context(
        event,
        code=booking.payment_reference_code,
        was=was.value,
        **({"marked_paid_by_hand": True, "reason": reason} if by_hand else {}),
    )

    if owed:
        await record_audit(
            db,
            actor_user_id=actor.id,
            action="booking.payment_unallocated",
            target_type="booking",
            target_id=booking.id,
            context=context,
        )
        await publish_event(
            db,
            event_type="booking.payment_unallocated",
            payload={"booking_id": str(booking.id)},
            dedupe_key=f"booking.payment_unallocated:{booking.id}",
        )
        return

    await record_audit(
        db,
        actor_user_id=actor.id,
        action=(
            "booking.late_payment_accepted"
            if late
            else "booking.payment_marked_paid"
            if by_hand
            else "booking.payment_confirmed"
        ),
        target_type="booking",
        target_id=booking.id,
        context=context,
    )
    await publish_event(
        db,
        event_type="booking.payment_confirmed",
        payload={"booking_id": str(booking.id)},
        dedupe_key=f"booking.payment_confirmed:{booking.id}",
    )
    await announce_confirmed(db, booking, late_payment=late)


async def reject(db: AsyncSession, *, actor: User, booking_id: uuid.UUID, reason: str) -> Booking:
    """The code does not match a payment. The booking is left as it is, so the booker can
    check and send a right code while the hold lasts. Idempotent."""
    booking, event = await _admin_booking(db, actor=actor, booking_id=booking_id)
    booking = await _lock_booking(db, booking.id)
    if booking.payment_state == ManualPaymentState.REJECTED:
        return booking
    if booking.payment_state != ManualPaymentState.AWAITING_CONFIRMATION:
        raise ConflictError(
            "There is no payment code waiting to be decided on this booking.",
            code="no_payment_to_reject",
        )
    code = booking.payment_reference_code
    stamp = booking.payment_submitted_at.isoformat() if booking.payment_submitted_at else ""
    now = await db_now(db)
    booking.payment_reference_code = None  # a wrong code must not block the right owner's
    booking.payment_state = ManualPaymentState.REJECTED
    booking.payment_decided_at = now
    booking.payment_decided_by = actor.id
    booking.payment_note = reason
    await db.flush()
    await record_audit(
        db,
        actor_user_id=actor.id,
        action="booking.payment_rejected",
        target_type="booking",
        target_id=booking.id,
        context=_audit_context(event, code=code, reason=reason),
    )
    await publish_event(
        db,
        event_type="booking.payment_rejected",
        payload={"booking_id": str(booking.id)},
        dedupe_key=f"booking.payment_rejected:{booking.id}:{stamp}",
    )
    return booking


async def mark_refunded(
    db: AsyncSession, *, actor: User, booking_id: uuid.UUID, note: str | None
) -> Booking:
    """The organizer sent the money back by hand. Idempotent."""
    booking, event = await _admin_booking(db, actor=actor, booking_id=booking_id)
    booking = await _lock_booking(db, booking.id)
    if booking.payment_state == ManualPaymentState.REFUNDED:
        return booking
    if booking.payment_state != ManualPaymentState.NEEDS_REFUND:
        raise ConflictError("No refund is owed on this booking.", code="nothing_to_refund")
    booking.payment_state = ManualPaymentState.REFUNDED
    booking.payment_decided_at = await db_now(db)
    booking.payment_decided_by = actor.id
    booking.payment_note = note
    if booking.status == BookingStatus.CANCELLED and booking.confirmed_at is not None:
        booking.status = BookingStatus.REFUNDED  # was a confirmed, paid booking
    await db.flush()
    await record_audit(
        db,
        actor_user_id=actor.id,
        action="booking.refund_marked",
        target_type="booking",
        target_id=booking.id,
        context=_audit_context(
            event, code=booking.payment_reference_code, amount_minor=booking.amount_minor
        ),
    )
    await publish_event(
        db,
        event_type="booking.refunded",
        payload={"booking_id": str(booking.id)},
        dedupe_key=f"booking.refunded:{booking.id}",
    )
    return booking


async def organizer_cancel(
    db: AsyncSession, *, actor: User, booking_id: uuid.UUID, reason: str, refund: bool
) -> Booking:
    """An organization admin cancels a booking, with or without giving the money back. A
    payment that was confirmed and is to be returned goes into the refund queue."""
    from app.modules.bookings.service import cancel_booking

    _, event = await _admin_booking(db, actor=actor, booking_id=booking_id)
    booking = await cancel_booking(
        db, actor=actor, booking_id=booking_id, reason=reason, as_organizer=True
    )
    if refund and booking.payment_state == ManualPaymentState.CONFIRMED:
        booking.payment_state = ManualPaymentState.NEEDS_REFUND
        booking.payment_decided_at = await db_now(db)
        booking.payment_decided_by = actor.id
        await db.flush()
        await record_audit(
            db,
            actor_user_id=actor.id,
            action="booking.refund_owed",
            target_type="booking",
            target_id=booking.id,
            context=_audit_context(event, amount_minor=booking.amount_minor),
        )
        await publish_event(
            db,
            event_type="booking.refund_owed",
            payload={"booking_id": str(booking.id)},
            dedupe_key=f"booking.refund_owed:{booking.id}",
        )
    return booking


async def refund_queue(
    db: AsyncSession,
    *,
    event: Event,
    state: ManualPaymentState | None,
    limit: int,
    offset: int,
) -> tuple[list[Booking], int]:
    """Everything the organizer must act on for this event's money, oldest first: payments
    waiting for a decision and payments owed back."""
    where = (
        Booking.event_id == event.id,
        Booking.payment_state.in_(
            (state,)
            if state
            else (ManualPaymentState.AWAITING_CONFIRMATION, ManualPaymentState.NEEDS_REFUND)
        ),
    )
    total = await db.scalar(select(func.count()).select_from(Booking).where(*where))
    rows = (
        await db.scalars(
            select(Booking)
            .where(*where)
            .order_by(Booking.payment_submitted_at, Booking.id)
            .limit(limit)
            .offset(offset)
        )
    ).all()
    return list(rows), int(total or 0)
