from __future__ import annotations

import enum
import uuid

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.enum_column import str_enum
from app.infrastructure.database.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.infrastructure.database.session import Base


class VerificationStatus(enum.StrEnum):
    UNVERIFIED = "unverified"
    VERIFIED = "verified"


class VerificationMethod(enum.StrEnum):
    ADMIN = "admin"
    PEER = "peer"
    EMAIL_DOMAIN = "email_domain"


class ProfileVisibility(enum.StrEnum):
    PUBLIC = "public"
    MEMBERS_ONLY = "members_only"
    CONNECTIONS_ONLY = "connections_only"
    PRIVATE = "private"


class AlumniProfile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "alumni_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    graduation_year: Mapped[int | None] = mapped_column(nullable=True)
    school_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True
    )
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    profession: Mapped[str | None] = mapped_column(String(255), nullable=True)
    company: Mapped[str | None] = mapped_column(String(255), nullable=True)

    verification_status: Mapped[VerificationStatus] = mapped_column(
        str_enum(VerificationStatus, name="verification_status"),
        nullable=False,
        default=VerificationStatus.UNVERIFIED,
    )
    verification_method: Mapped[VerificationMethod | None] = mapped_column(
        str_enum(VerificationMethod, name="verification_method"), nullable=True
    )

    profile_visibility: Mapped[ProfileVisibility] = mapped_column(
        str_enum(ProfileVisibility, name="profile_visibility"),
        nullable=False,
        default=ProfileVisibility.MEMBERS_ONLY,
    )
    avatar_file_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("files.id", ondelete="SET NULL"), nullable=True
    )


class PeerVouch(UUIDPrimaryKeyMixin, Base):
    """
    Threshold for auto-verification is 3 — enforced in the service
    layer, not here; this table just records who vouched for whom.
    """

    __tablename__ = "peer_vouches"
    __table_args__ = (
        UniqueConstraint("vouched_user_id", "voucher_user_id", name="uq_peer_vouch_pair"),
    )

    vouched_user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("alumni_profiles.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    voucher_user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("alumni_profiles.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )


class SchoolEmailDomain(UUIDPrimaryKeyMixin, Base):
    """For auto-verify by institutional email — Phase 8; table exists now for completeness."""

    __tablename__ = "school_email_domains"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    domain: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)


class Skill(UUIDPrimaryKeyMixin, Base):
    """Shared vocabulary. Names are stored trimmed and lowercased ('Python' == 'python')."""

    __tablename__ = "skills"

    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)


class AlumniSkill(Base):
    __tablename__ = "alumni_skills"

    alumni_profile_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("alumni_profiles.id", ondelete="CASCADE"),
        primary_key=True,
    )
    skill_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("skills.id", ondelete="CASCADE"), primary_key=True
    )


class Interest(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "interests"

    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)


class AlumniInterest(Base):
    __tablename__ = "alumni_interests"

    alumni_profile_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("alumni_profiles.id", ondelete="CASCADE"),
        primary_key=True,
    )
    interest_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("interests.id", ondelete="CASCADE"), primary_key=True
    )
