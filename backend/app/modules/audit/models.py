import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.mixins import UUIDPrimaryKeyMixin
from app.infrastructure.database.session import Base


class AuditLogEntry(UUIDPrimaryKeyMixin, Base):
    """
    Append-only. Nothing ever updates or deletes a row here — there is
    deliberately no update/delete path in the service or router.

    The ERD calls the JSON field "metadata", but that name is reserved
    on every SQLAlchemy declarative model (Base.metadata) — it's mapped
    to a Python attribute named `context` instead, while the actual
    database column stays named `metadata` so the schema matches the ERD.
    """

    __tablename__ = "audit_log"

    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    target_type: Mapped[str] = mapped_column(String(50), nullable=False)
    target_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    context: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict, server_default="{}"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
