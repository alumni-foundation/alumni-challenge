from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.enum_column import str_enum
from app.infrastructure.database.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.infrastructure.database.session import Base

DEFAULT_HOLD_MINUTES = 15
MIN_HOLD_MINUTES = 5
MAX_HOLD_MINUTES = 2880  # 48 hours, and only for manual-payment events
MAX_PARTY_SIZE = 4


class EventCategory(enum.StrEnum):
    HOMECOMING = "homecoming"
    GOLF_TOURNAMENT = "golf_tournament"
    SPORTS = "sports"
    NETWORKING = "networking"
    FORUM = "forum"
    MENTORSHIP = "mentorship"
    LEADERSHIP = "leadership"
    PHILANTHROPY = "philanthropy"
    OTHER = "other"


class EventStatus(enum.StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    CLOSED = "closed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class EventVisibility(enum.StrEnum):
    PUBLIC = "public"
    MEMBERS_ONLY = "members_only"


class QuestionKind(enum.StrEnum):
    TEXT = "text"
    LONG_TEXT = "long_text"
    NUMBER = "number"
    BOOLEAN = "boolean"
    CHOICE = "choice"
    MULTI_CHOICE = "multi_choice"
    SCHOOL = "school"  # the answer is the id of an active school organization


class QuestionAskedOf(enum.StrEnum):
    BOOKER = "booker"
    EACH_PARTICIPANT = "each_participant"


def _fk(target: str, name: str, *, ondelete: str | None = None) -> ForeignKey:
    return ForeignKey(target, name=name, ondelete=ondelete)


class EventSeries(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A named group of events that are rounds of one competition."""

    __tablename__ = "event_series"

    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        _fk("organizations.id", "fk_event_series_organization_id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        _fk("users.id", "fk_event_series_created_by", ondelete="SET NULL"),
        nullable=True,
    )


class Event(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "events"
    __table_args__ = (
        CheckConstraint("ends_at > starts_at", name="ck_events_ends_after_start"),
        CheckConstraint("price_minor >= 0", name="ck_events_price_not_negative"),
        CheckConstraint(
            f"max_party_size BETWEEN 1 AND {MAX_PARTY_SIZE}", name="ck_events_party_size_range"
        ),
        CheckConstraint(
            f"hold_minutes BETWEEN {MIN_HOLD_MINUTES} AND {MAX_HOLD_MINUTES}",
            name="ck_events_hold_minutes_range",
        ),
        CheckConstraint(
            "(series_id IS NULL) = (round_number IS NULL)", name="ck_events_series_and_round"
        ),
        CheckConstraint(
            "registration_closes_at IS NULL OR registration_opens_at IS NULL "
            "OR registration_closes_at > registration_opens_at",
            name="ck_events_registration_window",
        ),
        UniqueConstraint("series_id", "round_number", name="uq_events_series_round"),
    )

    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        _fk("organizations.id", "fk_events_organization_id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    series_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        _fk("event_series.id", "fk_events_series_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    round_number: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[EventCategory] = mapped_column(
        str_enum(EventCategory, name="event_category"), nullable=False
    )
    status: Mapped[EventStatus] = mapped_column(
        str_enum(EventStatus, name="event_status"),
        nullable=False,
        default=EventStatus.DRAFT,
        index=True,
    )
    visibility: Mapped[EventVisibility] = mapped_column(
        str_enum(EventVisibility, name="event_visibility"),
        nullable=False,
        default=EventVisibility.PUBLIC,
    )
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    venue_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    venue_address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    poster_file_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        _fk("files.id", "fk_events_poster_file_id", ondelete="SET NULL"),
        nullable=True,
    )
    registration_opens_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    registration_closes_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Money is whole minor units (1/100 of a shilling) with a currency, never a float.
    price_minor: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="KES")
    max_party_size: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)
    hold_minutes: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=DEFAULT_HOLD_MINUTES
    )
    waitlist_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # The organizer's switch: hide the "who's going" list from attendees.
    show_attendee_list: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    contact_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    refund_policy_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    reminder_hours_before: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=24)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        _fk("users.id", "fk_events_created_by", ondelete="SET NULL"),
        nullable=True,
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        _fk("users.id", "fk_events_updated_by", ondelete="SET NULL"),
        nullable=True,
    )


class EventSlot(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    A bookable window with its own capacity. Every event has at least one (a meetup has a single
    unlabelled slot). The two counters are the fast answer to "how many seats are left"; they are
    changed only while this row is locked (see bookings.seats) and the CHECK constraints below
    mean even a bug cannot make them oversell.
    """

    __tablename__ = "event_slots"
    __table_args__ = (
        CheckConstraint("ends_at > starts_at", name="ck_event_slots_ends_after_start"),
        CheckConstraint("capacity IS NULL OR capacity >= 0", name="ck_event_slots_capacity"),
        CheckConstraint(
            "seats_confirmed >= 0 AND seats_held >= 0", name="ck_event_slots_counters_not_negative"
        ),
        CheckConstraint(
            "capacity IS NULL OR seats_confirmed + seats_held <= capacity",
            name="ck_event_slots_not_oversold",
        ),
        UniqueConstraint("id", "event_id", name="uq_event_slots_id_event"),
    )

    event_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        _fk("events.id", "fk_event_slots_event_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    label: Mapped[str | None] = mapped_column(String(120), nullable=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    capacity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    seats_confirmed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    seats_held: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    position: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)


class EventQuestion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A registration question, configured per event (not hard-coded to golf)."""

    __tablename__ = "event_questions"
    __table_args__ = (UniqueConstraint("event_id", "key", name="uq_event_questions_event_key"),)

    event_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        _fk("events.id", "fk_event_questions_event_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    key: Mapped[str] = mapped_column(String(60), nullable=False)
    label: Mapped[str] = mapped_column(String(300), nullable=False)
    kind: Mapped[QuestionKind] = mapped_column(
        str_enum(QuestionKind, name="event_question_kind"), nullable=False
    )
    options: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True)
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    asked_of: Mapped[QuestionAskedOf] = mapped_column(
        str_enum(QuestionAskedOf, name="event_question_asked_of"),
        nullable=False,
        default=QuestionAskedOf.BOOKER,
    )
    position: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)


class EventConsent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Words an attendee must accept to book. A changed text is a new version."""

    __tablename__ = "event_consents"
    __table_args__ = (UniqueConstraint("event_id", "key", name="uq_event_consents_event_key"),)

    event_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        _fk("events.id", "fk_event_consents_event_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    key: Mapped[str] = mapped_column(String(60), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
