"""Outbox publish/drain: dispatch, retry, dead-letter, and the wired welcome email."""

import uuid
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.mail.base import Mailer
from app.modules.events.models import DomainEvent, DomainEventStatus
from app.modules.events.registry import on
from app.modules.events.service import MAX_ATTEMPTS, drain_pending, publish

API = "/api/v1"


class _CapturingMailer(Mailer):
    def __init__(self) -> None:
        self.sent: list[dict[str, str]] = []

    async def send(self, *, to: str, subject: str, body: str) -> None:
        self.sent.append({"to": to, "subject": subject, "body": body})


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


async def test_a_failing_handler_retries_then_dead_letters(db_session: AsyncSession) -> None:
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


async def test_registration_publishes_user_registered_and_drain_sends_the_welcome_email(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The handler runs from drain_pending (the worker's job), never from
    # inside a FastAPI request — it calls get_mailer() directly rather
    # than through Depends(), so app.dependency_overrides can't reach it.
    # Patching the name where events/handlers.py imported it is the
    # correct way to fake it out here.
    import app.modules.events.handlers as handlers_module

    mailer = _CapturingMailer()
    monkeypatch.setattr(handlers_module, "get_mailer", lambda: mailer)

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
    assert row.payload["email"] == email
    assert row.status == DomainEventStatus.PENDING  # registering doesn't send it synchronously

    await drain_pending(db_session)
    assert len(mailer.sent) == 1
    assert mailer.sent[0]["to"] == email


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
