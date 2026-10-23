"""
Outbox writer + poller. See models.py for why this is an outbox rather
than "enqueue an ARQ job directly from the request handler" — the short
version is that a crash between committing the real change and
enqueueing the job would silently drop the event, and this design
can't have that failure mode.
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.domain_events.models import DomainEvent, DomainEventStatus
from app.modules.domain_events.registry import handlers_for

logger = logging.getLogger("domain_events")

MAX_ATTEMPTS = 5
DRAIN_BATCH_SIZE = 20

# Events that carry an email address because the person no longer exists to look up. Their
# payload is emptied the moment they have been handled, so the address is not kept.
SCRUB_AFTER_DISPATCH = frozenset({"email.account_deleted"})

# How long to wait before trying again, after the 1st, 2nd, 3rd and 4th failure. The fifth
# failure dead-letters the event. Spread out so an outage at an email provider (minutes to
# an hour) is ridden out instead of burning every attempt in the first half minute.
RETRY_DELAYS = (
    timedelta(seconds=30),
    timedelta(minutes=2),
    timedelta(minutes=10),
    timedelta(hours=1),
)


def retry_delay(attempts: int) -> timedelta:
    """`attempts` is the number of failures so far (1 or more)."""
    return RETRY_DELAYS[min(attempts, len(RETRY_DELAYS)) - 1]


async def publish(db: AsyncSession, *, event_type: str, payload: dict[str, Any]) -> DomainEvent:
    """
    Writes the row and flushes — does NOT commit. Callers publish inside
    the same request/transaction as the action the event describes, and
    the router's normal `db.commit()` covers both at once. A rolled-back
    action correctly takes its event with it.
    """
    event = DomainEvent(event_type=event_type, payload=payload)
    db.add(event)
    await db.flush()
    return event


async def drain_pending(db: AsyncSession, *, limit: int = DRAIN_BATCH_SIZE) -> int:
    """
    Runs every handler registered for each pending event's type. Returns
    the number of rows processed (dispatched or failed) in this call.

    Retry and dead-letter: a handler that raises leaves the row PENDING
    with `attempts` incremented, so the next poll retries it — up to
    MAX_ATTEMPTS, after which the row is marked FAILED and stops being
    retried automatically. That's the dead-letter: a FAILED row is never
    picked up again by this function, but it isn't deleted either, so
    `SELECT * FROM domain_events WHERE status = 'failed'` is always a
    real, inspectable list of what needs manual attention.
    """
    stmt = (
        select(DomainEvent)
        .where(DomainEvent.status == DomainEventStatus.PENDING)
        .where(
            or_(
                DomainEvent.next_attempt_at.is_(None),
                DomainEvent.next_attempt_at <= func.clock_timestamp(),
            )
        )
        .order_by(DomainEvent.created_at)
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    events = list((await db.scalars(stmt)).all())

    for event in events:
        try:
            for handler in handlers_for(event.event_type):
                await handler(db, event.payload)
        except Exception as exc:  # noqa: BLE001 — a handler's exact error is not our concern here
            event.attempts += 1
            event.last_error = str(exc)[:500]
            if event.attempts < MAX_ATTEMPTS:
                event.next_attempt_at = datetime.now(UTC) + retry_delay(event.attempts)
            else:
                event.status = DomainEventStatus.FAILED
                logger.error(
                    "domain_event_dead_lettered",
                    extra={
                        "event_id": str(event.id),
                        "event_type": event.event_type,
                        "error": event.last_error,
                    },
                )
        else:
            event.status = DomainEventStatus.DISPATCHED
            if event.event_type in SCRUB_AFTER_DISPATCH:
                event.payload = {}
            event.dispatched_at = datetime.now(UTC)

    await db.flush()
    return len(events)
