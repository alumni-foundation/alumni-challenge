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
    ForeignKeyConstraint,
    Index,
    SmallInteger,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.enum_column import str_enum
from app.infrastructure.database.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.infrastructure.database.session import Base


class BookingStatus(enum.StrEnum):
    PENDING_PAYMENT = "pending_payment"
    CONFIRMED = "confirmed"
    WAITLISTED = "waitlisted"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


# A booking in one of these states counts towards "one active booking per person per event".
ACTIVE_STATUSES = (
    BookingStatus.PENDING_PAYMENT,
    BookingStatus.CONFIRMED,
    BookingStatus.WAITLISTED,
)


class Booking(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    One booker's claim on seats in one slot. The price is copied onto the booking when it is
    made (computed on the server, never sent by the client), so a later price change cannot
    change what someone owes.
    """

    __tablename__ = "bookings"
    __table_args__ = (
        ForeignKeyConstraint(
            ["slot_id", "event_id"],
            ["event_slots.id", "event_slots.event_id"],
            name="fk_bookings_slot_and_event",
            ondelete="RESTRICT",
        ),
        CheckConstraint("party_size BETWEEN 1 AND 4", name="ck_bookings_party_size"),
        CheckConstraint("unit_price_minor >= 0", name="ck_bookings_unit_price"),
        CheckConstraint(
            "amount_minor = unit_price_minor * party_size", name="ck_bookings_amount_matches"
        ),
        # A hold exists exactly while the booking waits for payment.
        CheckConstraint(
            "(status = 'pending_payment') = (hold_expires_at IS NOT NULL)",
            name="ck_bookings_hold_only_while_pending",
        ),
        UniqueConstraint(
            "booker_user_id", "idempotency_key", name="uq_bookings_booker_idempotency_key"
        ),
        UniqueConstraint("reference", name="uq_bookings_reference"),
        # Nobody holds two places on one event: stops hold hoarding.
        Index(
            "uq_bookings_one_active_per_person_per_event",
            "event_id",
            "booker_user_id",
            unique=True,
            postgresql_where=text("status IN ('pending_payment', 'confirmed', 'waitlisted')"),
        ),
        Index(
            "ix_bookings_holds_expiring",
            "hold_expires_at",
            postgresql_where=text("status = 'pending_payment'"),
        ),
        Index(
            "ix_bookings_waitlist_order",
            "slot_id",
            "waitlisted_at",
            postgresql_where=text("status = 'waitlisted'"),
        ),
        Index("ix_bookings_slot_status", "slot_id", "status"),
        Index("ix_bookings_event_status", "event_id", "status"),
        Index("ix_bookings_booker_created", "booker_user_id", "created_at"),
    )

    event_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    slot_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    # RESTRICT: accounts are anonymized on deletion, never removed, so history stays.
    booker_user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", name="fk_bookings_booker_user_id", ondelete="RESTRICT"),
        nullable=False,
    )
    party_size: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    status: Mapped[BookingStatus] = mapped_column(
        str_enum(BookingStatus, name="booking_status"), nullable=False
    )
    unit_price_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    hold_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    waitlisted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    offered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    from_waitlist: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    reference: Mapped[str] = mapped_column(String(16), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    request_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancel_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    cancelled_by: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", name="fk_bookings_cancelled_by", ondelete="SET NULL"),
        nullable=True,
    )
    reminder_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class BookingParticipant(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    A person in a booking. Position 1 is the booker. The others are named, and may have no
    account: `user_id` is set only when that person claims their ticket (slice 5.4). Nothing
    here ever looks a person up by the email or phone given for them.
    """

    __tablename__ = "booking_participants"
    __table_args__ = (
        UniqueConstraint("booking_id", "position", name="uq_booking_participants_position"),
        CheckConstraint("position BETWEEN 1 AND 4", name="ck_booking_participants_position"),
        Index("ix_booking_participants_user", "user_id"),
    )

    booking_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("bookings.id", name="fk_booking_participants_booking_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    position: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", name="fk_booking_participants_user_id", ondelete="SET NULL"),
        nullable=True,
    )
    # "Show me in who's going" (slice 5.3). The person's profile privacy still applies on top.
    listed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class BookingAnswer(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """An answer to one event question for one participant (booker-level questions are
    answered on participant 1)."""

    __tablename__ = "booking_answers"
    __table_args__ = (
        UniqueConstraint("participant_id", "question_id", name="uq_booking_answers_once"),
        Index("ix_booking_answers_question", "question_id"),
    )

    booking_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("bookings.id", name="fk_booking_answers_booking_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    participant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(
            "booking_participants.id", name="fk_booking_answers_participant_id", ondelete="CASCADE"
        ),
        nullable=False,
    )
    # RESTRICT: a question that has been answered cannot be deleted.
    question_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(
            "event_questions.id", name="fk_booking_answers_question_id", ondelete="RESTRICT"
        ),
        nullable=False,
    )
    value: Mapped[Any] = mapped_column(JSONB, nullable=False)


class BookingConsent(UUIDPrimaryKeyMixin, Base):
    """Proof of exactly which words were accepted, and when."""

    __tablename__ = "booking_consents"
    __table_args__ = (
        UniqueConstraint("booking_id", "consent_id", name="uq_booking_consents_once"),
        Index("ix_booking_consents_consent", "consent_id"),
    )

    booking_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("bookings.id", name="fk_booking_consents_booking_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    consent_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("event_consents.id", name="fk_booking_consents_consent_id", ondelete="RESTRICT"),
        nullable=False,
    )
    version: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    text_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    accepted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
