import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.enum_column import str_enum
from app.infrastructure.database.mixins import UUIDPrimaryKeyMixin
from app.infrastructure.database.session import Base


class ReportTargetType(enum.StrEnum):
    PROFILE = "profile"
    MESSAGE = "message"
    CONTENT = "content"


class ReportStatus(enum.StrEnum):
    OPEN = "open"
    REVIEWING = "reviewing"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


# A report in one of these states is "live": it is waiting on a moderator, and while it
# is live the moderator may see the reported profile. Anything else is closed.
ACTIVE_REPORT_STATUSES = (ReportStatus.OPEN, ReportStatus.REVIEWING)


class Report(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "reports"

    reporter_user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    target_type: Mapped[ReportTargetType] = mapped_column(
        str_enum(ReportTargetType, name="report_target_type"), nullable=False, index=True
    )
    target_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False, index=True)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[ReportStatus] = mapped_column(
        str_enum(ReportStatus, name="report_status"),
        nullable=False,
        default=ReportStatus.OPEN,
        index=True,
    )
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
