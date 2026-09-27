from __future__ import annotations

import enum
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.infrastructure.database.session import Base

if TYPE_CHECKING:
    from app.modules.memberships.models import Membership


class OrganizationType(enum.StrEnum):
    SCHOOL = "school"
    PARTNER = "partner"


class OrganizationStatus(enum.StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class Organization(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    Schools and partners share this table, distinguished by `type`.
    Per the Phase 0 ERD decision — lets a future org type slot in
    without a schema change, matches the doc's multi-organization model.
    """

    __tablename__ = "organizations"

    type: Mapped[OrganizationType] = mapped_column(
        Enum(OrganizationType, name="organization_type"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    logo_file_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("files.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[OrganizationStatus] = mapped_column(
        Enum(OrganizationStatus, name="organization_status"),
        nullable=False,
        default=OrganizationStatus.ACTIVE,
    )

    memberships: Mapped[list[Membership]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )
