import enum
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.mixins import UUIDPrimaryKeyMixin
from app.infrastructure.database.session import Base


class DomainEventStatus(enum.StrEnum):
    PENDING = "pending"
    DISPATCHED = "dispatched"
    FAILED = "failed"


class DomainEvent(Base, UUIDPrimaryKeyMixin):
    """
    The outbox: publishing an event means writing a row here in the SAME
    transaction as whatever triggered it (see events/service.py). That's
    what makes delivery reliable — the event can never be "lost" between
    committing the real change and telling the queue about it, because
    there is no separate step; a background poller (the ARQ cron job in
    worker.py) finds pending rows and dispatches them.
    """

    __tablename__ = "domain_events"

    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[DomainEventStatus] = mapped_column(
        String(20), nullable=False, default=DomainEventStatus.PENDING, index=True
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __mapper_args__ = {"eager_defaults": True}
