from __future__ import annotations

import enum
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.permissions.roles import Role
from app.infrastructure.database.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.infrastructure.database.session import Base

if TYPE_CHECKING:
    from app.modules.identity.models import User
    from app.modules.organizations.models import Organization


class MembershipStatus(enum.StrEnum):
    ACTIVE = "active"
    REVOKED = "revoked"


class Membership(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    The single source of truth for who can do what. organization_id is
    nullable — null means a platform-wide role (super_admin, admin,
    moderator). Every permission check in the app reads this table,
    never a role stored directly on User.
    """

    __tablename__ = "memberships"
    __table_args__ = (
        UniqueConstraint("user_id", "organization_id", "role", name="uq_membership_user_org_role"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    role: Mapped[Role] = mapped_column(Enum(Role, name="membership_role"), nullable=False)
    status: Mapped[MembershipStatus] = mapped_column(
        Enum(MembershipStatus, name="membership_status"),
        nullable=False,
        default=MembershipStatus.ACTIVE,
    )

    user: Mapped[User] = relationship(back_populates="memberships")
    organization: Mapped[Organization | None] = relationship(back_populates="memberships")

    @property
    def is_active(self) -> bool:
        return self.status == MembershipStatus.ACTIVE
