import enum
import uuid
from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.enum_column import str_enum
from app.infrastructure.database.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.infrastructure.database.session import Base

TEXT_MAX = 500


class WorkLogKind(enum.StrEnum):
    PLANNED = "planned"
    DONE = "done"


class WorkLogEntry(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    One line in a staff member's daily to-do and done list. `entry_date` is the calendar day in
    Nairobi when the line was added; the server sets it, the client never sends it. The composite
    index starts with the author, so it also serves "all of one person's entries".
    """

    __tablename__ = "work_log_entries"
    __table_args__ = (
        Index("ix_work_log_entries_author_user_id_entry_date", "author_user_id", "entry_date"),
        CheckConstraint(
            f"char_length(text) BETWEEN 1 AND {TEXT_MAX}", name="ck_work_log_entries_text_length"
        ),
        CheckConstraint(
            "(kind = 'done') = (completed_at IS NOT NULL)", name="ck_work_log_entries_done_has_time"
        ),
    )

    author_user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[WorkLogKind] = mapped_column(
        str_enum(WorkLogKind, name="work_log_kind"), nullable=False
    )
    text: Mapped[str] = mapped_column(String(TEXT_MAX), nullable=False)
    entry_date: Mapped[date] = mapped_column(Date, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
