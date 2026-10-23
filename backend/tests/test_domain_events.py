"""Outbox publish/drain: dispatch, retry, dead-letter, and the wired welcome email."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.domain_events import service as events_service
from app.modules.domain_events.models import DomainEvent, DomainEventStatus
from app.modules.domain_events.registry import on
from app.modules.domain_events.service import MAX_ATTEMPTS, drain_pending, publish
from tests.conftest import Mailbox

API = "/api/v1"


async def test_publish_writes_a_pending_row_and_drain_dispatches_it(
    db_session: AsyncSession,
) -> None:
    event_type = f"test.event.{uuid.uuid4().hex[:8]}"
    calls: list[dict[str, Any]] = []

    @on(event_type)
    async def _handler(db: AsyncSession, payload: dict[str, Any]) -> None:
        calls.append(payload)

    event = await publish(db_session, event_type=event_type, payload={"x": 1})
    assert event.status == DomainEventStatus.PENDING

    processed = await drain_pending(db_session)
    assert processed >= 1
    assert calls == [{"x": 1}]

    refreshed = await db_session.get(DomainEvent, event.id)
    assert refreshed is not None
    assert refreshed.status == DomainEventStatus.DISPATCHED
    assert refreshed.dispatched_at is not None


async def test_a_failing_handler_retries_then_dead_letters(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    # No waiting between attempts here; the waiting itself is tested separately below.
    monkeypatch.setattr(events_service, "retry_delay", lambda attempts: timedelta(0))
    event_type = f"test.always_fails.{uuid.uuid4().hex[:8]}"
    attempts = 0

    @on(event_type)
    async def _flaky(db: AsyncSession, payload: dict[str, Any]) -> None:
        nonlocal attempts
        attempts += 1
        raise RuntimeError("simulated handler failure")

    event = await publish(db_session, event_type=event_type, payload={})
    await db_session.flush()

    for _ in range(MAX_ATTEMPTS - 1):
        await drain_pending(db_session)
        refreshed = await db_session.get(DomainEvent, event.id)
        assert refreshed is not None
        assert refreshed.status == DomainEventStatus.PENDING  # still retryable

    # One more failure crosses the threshold.
    await drain_pending(db_session)
    refreshed = await db_session.get(DomainEvent, event.id)
    assert refreshed is not None
    assert refreshed.status == DomainEventStatus.FAILED
    assert refreshed.attempts == MAX_ATTEMPTS
    assert "simulated handler failure" in (refreshed.last_error or "")
    assert attempts == MAX_ATTEMPTS

    # A dead-lettered event is never retried again, even after more drains.
    before = attempts
    await drain_pending(db_session)
    assert attempts == before


async def test_drain_only_touches_pending_rows_of_its_own_batch(db_session: AsyncSession) -> None:
    # A dispatched event from a previous drain is not reprocessed.
    event_type = f"test.once.{uuid.uuid4().hex[:8]}"
    calls = 0

    @on(event_type)
    async def _once(db: AsyncSession, payload: dict[str, Any]) -> None:
        nonlocal calls
        calls += 1

    await publish(db_session, event_type=event_type, payload={})
    await drain_pending(db_session)
    await drain_pending(db_session)
    assert calls == 1


async def test_registration_queues_one_email_and_the_worker_sends_the_verification_link(
    client: AsyncClient, db_session: AsyncSession, mailbox: Mailbox
) -> None:
    email = f"welcome-{uuid.uuid4().hex[:10]}@example.com"
    r = await client.post(
        f"{API}/auth/register",
        json={"email": email, "password": "correct-horse-battery", "confirm_18_or_older": True},
    )
    assert r.status_code == 201

    row = await db_session.scalar(
        select(DomainEvent).where(DomainEvent.event_type == "user.registered")
    )
    assert row is not None
    assert row.payload == {"user_id": r.json()["id"]}  # an id, never the address or a token
    assert row.status == DomainEventStatus.PENDING
    assert mailbox.sent == []  # registering does not send inside the request

    await drain_pending(db_session)
    assert len(mailbox.sent) == 1
    assert mailbox.sent[0]["to"] == email
    assert mailbox.links("/verify-email")  # the one email carries the verification link


async def test_a_failed_attempt_waits_before_the_next_one(db_session: AsyncSession) -> None:
    event_type = f"test.backoff.{uuid.uuid4().hex[:8]}"
    calls = 0

    @on(event_type)
    async def _fails(db: AsyncSession, payload: dict[str, Any]) -> None:
        nonlocal calls
        calls += 1
        raise RuntimeError("provider down")

    event = await publish(db_session, event_type=event_type, payload={})

    await drain_pending(db_session)
    await drain_pending(db_session)  # straight away: it must not be tried again yet

    assert calls == 1
    refreshed = await db_session.get(DomainEvent, event.id)
    assert refreshed is not None
    assert refreshed.status == DomainEventStatus.PENDING
    assert refreshed.next_attempt_at is not None
    assert refreshed.next_attempt_at > datetime.now(UTC)

    refreshed.next_attempt_at = datetime.now(UTC) - timedelta(seconds=1)  # time passes
    await db_session.flush()
    await drain_pending(db_session)
    assert calls == 2


def test_the_delays_grow_and_the_last_is_an_hour() -> None:
    delays = [events_service.retry_delay(n) for n in range(1, MAX_ATTEMPTS)]

    assert delays == sorted(delays)
    assert delays[0] == timedelta(seconds=30)
    assert delays[-1] == timedelta(hours=1)


async def test_an_address_held_for_a_deleted_account_notice_is_cleared_once_sent(
    db_session: AsyncSession, mailbox: Mailbox
) -> None:
    event = await publish(
        db_session, event_type="email.account_deleted", payload={"email": "gone@example.com"}
    )

    await drain_pending(db_session)

    assert [m["to"] for m in mailbox.sent] == ["gone@example.com"]
    refreshed = await db_session.get(DomainEvent, event.id)
    assert refreshed is not None
    assert refreshed.status == DomainEventStatus.DISPATCHED
    assert refreshed.payload == {}


async def test_a_rolled_back_action_never_leaves_a_dangling_pending_event(
    db_session: AsyncSession,
) -> None:
    event_type = f"test.rollback.{uuid.uuid4().hex[:8]}"
    event = await publish(db_session, event_type=event_type, payload={})
    event_id = event.id
    await db_session.rollback()

    # The row from the rolled-back transaction was never committed —
    # a fresh query sees nothing, exactly like the action it described.
    refreshed = await db_session.get(DomainEvent, event_id)
    assert refreshed is None
