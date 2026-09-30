"""
Outbox writer + poller. See models.py for why this is an outbox rather
than "enqueue an ARQ job directly from the request handler" — the short
version is that a crash between committing the real change and
enqueueing the job would silently drop the event, and this design
can't have that failure mode.
"""

import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.events.models import DomainEvent, DomainEventStatus
from app.modules.events.registry import handlers_for

logger = logging.getLogger("domain_events")

MAX_ATTEMPTS = 5
DRAIN_BATCH_SIZE = 20


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
            if event.attempts >= MAX_ATTEMPTS:
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
            event.dispatched_at = datetime.now(UTC)

    await db.flush()
    return len(events)
