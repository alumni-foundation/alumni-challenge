from __future__ import annotations

import enum
import uuid

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.enum_column import str_enum
from app.infrastructure.database.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.infrastructure.database.session import Base


class PaymentProvider(enum.StrEnum):
    """How money reaches the organizer. Only the manual one exists so far (slice 5.5)."""

    MANUAL_MPESA = "manual_mpesa"


class MpesaKind(enum.StrEnum):
    PAYBILL = "paybill"
    TILL = "till"


class PaymentAccount(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    Who an event's money is paid to. For manual M-Pesa this is just the public paybill or till
    number people already pay to, so nothing here is secret. `organization_id` null means the
    platform's own account.
    """

    __tablename__ = "payment_accounts"
    __table_args__ = (
        CheckConstraint(
            "shortcode_or_till ~ '^[0-9]{4,10}$'", name="ck_payment_accounts_number_digits"
        ),
    )

    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(
            "organizations.id", name="fk_payment_accounts_organization_id", ondelete="RESTRICT"
        ),
        nullable=True,
        index=True,
    )
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    provider: Mapped[PaymentProvider] = mapped_column(
        str_enum(PaymentProvider, name="payment_provider"), nullable=False
    )
    mpesa_kind: Mapped[MpesaKind] = mapped_column(
        str_enum(MpesaKind, name="mpesa_kind"), nullable=False
    )
    shortcode_or_till: Mapped[str] = mapped_column(String(10), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="KES")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", name="fk_payment_accounts_created_by", ondelete="SET NULL"),
        nullable=True,
    )
