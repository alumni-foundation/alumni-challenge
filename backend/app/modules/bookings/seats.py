"""
The ONLY place seat counters change.

Every booking, cancellation, expiry and (later) waitlist promotion goes through here, and every
one of them starts by locking the slot row (`lock_slot`). The second person who wants the last
seat therefore waits for the first to finish and then sees the truth. Two rules keep it honest:

* Counters are changed with `SET seats_held = seats_held + n` (the database does the
  arithmetic), never "read, add in Python, write back".
* The CHECK constraints on event_slots refuse an impossible count, so even a mistake here
  cannot oversell: it fails loudly instead.

Lock order everywhere is: the slot, then bookings in id order, so two operations cannot
deadlock. Waiting for a lock is capped (LOCK_TIMEOUT); a timeout becomes a retryable 503.
"""

import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from sqlalchemy import func, select, text, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors.exceptions import NotFoundError, ServiceBusyError
from app.modules.bookings.models import Booking, BookingStatus
from app.modules.events.models import EventSlot

LOCK_TIMEOUT = "3s"
_LOCK_NOT_AVAILABLE = "55P03"

# Test-only seam: called after the capacity check and before the seats are taken, so a test can
# hold two bookings in exactly that gap and prove the lock keeps them apart. None in production.
capacity_check_hook: Callable[[], Awaitable[None]] | None = None


async def lock_slot(db: AsyncSession, slot_id: uuid.UUID) -> EventSlot:
    """Locks the slot row until the transaction ends and returns it, freshly read."""
    await db.execute(text(f"SET LOCAL lock_timeout = '{LOCK_TIMEOUT}'"))
    try:
        slot = await db.scalar(
            select(EventSlot)
            .where(EventSlot.id == slot_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    except DBAPIError as exc:
        if getattr(exc.orig, "sqlstate", None) == _LOCK_NOT_AVAILABLE:
            raise ServiceBusyError("Busy right now. Please try again in a moment.") from exc
        raise
    if slot is None:
        raise NotFoundError("Slot not found.")
    return slot


def free_seats(slot: EventSlot) -> int | None:
    """Seats left, or None if the slot has no limit."""
    if slot.capacity is None:
        return None
    return max(slot.capacity - slot.seats_confirmed - slot.seats_held, 0)


async def _add(db: AsyncSession, slot: EventSlot, *, confirmed: int = 0, held: int = 0) -> None:
    await db.execute(
        update(EventSlot)
        .where(EventSlot.id == slot.id)
        .values(
            seats_confirmed=EventSlot.seats_confirmed + confirmed,
            seats_held=EventSlot.seats_held + held,
        )
        .execution_options(synchronize_session=False)
    )
    await db.refresh(slot)


async def take(db: AsyncSession, slot: EventSlot, n: int, *, hold: bool) -> None:
    """Takes `n` seats as a hold (waiting for payment) or straight as confirmed."""
    await _add(db, slot, held=n if hold else 0, confirmed=0 if hold else n)


async def confirm_held(db: AsyncSession, slot: EventSlot, n: int) -> None:
    """A held booking was paid for: its seats move from held to confirmed."""
    await _add(db, slot, held=-n, confirmed=n)


async def release(db: AsyncSession, slot: EventSlot, n: int, *, was: BookingStatus) -> None:
    """Gives back the seats of a booking that was `was` (pending_payment or confirmed)."""
    if was == BookingStatus.PENDING_PAYMENT:
        await _add(db, slot, held=-n)
    elif was == BookingStatus.CONFIRMED:
        await _add(db, slot, confirmed=-n)


async def release_expired_holds(db: AsyncSession, slot: EventSlot) -> list[Booking]:
    """
    Ends every hold on this slot whose time has run out. The caller holds the slot lock.
    Called at the start of every seat change, so capacity is right even if the worker is late.
    Uses the database clock, like everything that decides who has a seat.
    """
    expired = list(
        (
            await db.scalars(
                select(Booking)
                .where(
                    Booking.slot_id == slot.id,
                    Booking.status == BookingStatus.PENDING_PAYMENT,
                    Booking.hold_expires_at < func.clock_timestamp(),
                )
                .order_by(Booking.id)
                .with_for_update()
            )
        ).all()
    )
    for booking in expired:
        await release(db, slot, booking.party_size, was=BookingStatus.PENDING_PAYMENT)
        booking.status = BookingStatus.EXPIRED
        booking.hold_expires_at = None
    if expired:
        await db.flush()
    return expired


async def recount(db: AsyncSession, slot_id: uuid.UUID) -> tuple[int, int]:
    """(confirmed, held) worked out from the bookings themselves, for checking the counters."""
    rows = (
        await db.execute(
            select(Booking.status, func.coalesce(func.sum(Booking.party_size), 0))
            .where(
                Booking.slot_id == slot_id,
                Booking.status.in_((BookingStatus.CONFIRMED, BookingStatus.PENDING_PAYMENT)),
            )
            .group_by(Booking.status)
        )
    ).all()
    by_status = {status: int(total) for status, total in rows}
    return by_status.get(BookingStatus.CONFIRMED, 0), by_status.get(
        BookingStatus.PENDING_PAYMENT, 0
    )


async def counters_that_disagree(db: AsyncSession) -> list[uuid.UUID]:
    """Slots whose counters differ from the truth. Should always be empty."""
    confirmed = (
        select(Booking.slot_id, func.sum(Booking.party_size).label("n"))
        .where(Booking.status == BookingStatus.CONFIRMED)
        .group_by(Booking.slot_id)
        .subquery()
    )
    held = (
        select(Booking.slot_id, func.sum(Booking.party_size).label("n"))
        .where(Booking.status == BookingStatus.PENDING_PAYMENT)
        .group_by(Booking.slot_id)
        .subquery()
    )
    rows = await db.execute(
        select(EventSlot.id)
        .outerjoin(confirmed, confirmed.c.slot_id == EventSlot.id)
        .outerjoin(held, held.c.slot_id == EventSlot.id)
        .where(
            (EventSlot.seats_confirmed != func.coalesce(confirmed.c.n, 0))
            | (EventSlot.seats_held != func.coalesce(held.c.n, 0))
        )
    )
    return [r[0] for r in rows.all()]


def now_utc() -> datetime:
    return datetime.now(UTC)
