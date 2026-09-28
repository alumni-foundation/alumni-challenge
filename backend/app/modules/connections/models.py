from __future__ import annotations

import enum
import uuid

from sqlalchemy import CheckConstraint, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.enum_column import str_enum
from app.infrastructure.database.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.infrastructure.database.session import Base


class ConnectionStatus(enum.StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    REMOVED = "removed"
    BLOCKED = "blocked"


class Connection(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "connections"
    __table_args__ = (
        UniqueConstraint("requester_id", "addressee_id", name="uq_connection_pair"),
        CheckConstraint("requester_id != addressee_id", name="ck_connection_not_self"),
    )

    requester_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    addressee_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[ConnectionStatus] = mapped_column(
        str_enum(ConnectionStatus, name="connection_status"),
        nullable=False,
        default=ConnectionStatus.PENDING,
    )
