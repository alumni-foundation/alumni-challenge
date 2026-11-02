"""
The admin users list. Only what an admin needs to find an account and see where it stands:
id, email, name (from the alumni profile, null for staff without one), status, the roles it
holds and when it was created. Never a password hash, token, session or anything private.
Deleted accounts are anonymised and never listed.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions.roles import Role
from app.core.search import escape_like
from app.modules.alumni.models import AlumniProfile
from app.modules.identity.models import User, UserStatus
from app.modules.memberships.models import Membership, MembershipStatus


@dataclass(frozen=True)
class UserRow:
    id: uuid.UUID
    email: str
    full_name: str | None
    status: UserStatus
    roles: list[Role]
    created_at: datetime


async def list_users(
    db: AsyncSession,
    *,
    q: str | None,
    status: UserStatus | None,
    limit: int,
    offset: int,
) -> tuple[list[UserRow], int]:
    conditions = [User.status != UserStatus.DELETED]
    if status is not None:
        conditions.append(User.status == status)
    if q and q.strip():
        like = f"%{escape_like(q.strip())}%"
        conditions.append(
            or_(
                User.email.ilike(like, escape="\\"),
                AlumniProfile.full_name.ilike(like, escape="\\"),
            )
        )

    base = (
        select(User, AlumniProfile.full_name)
        .outerjoin(AlumniProfile, AlumniProfile.user_id == User.id)
        .where(*conditions)
    )
    total = await db.scalar(select(func.count()).select_from(base.subquery()))
    page = (
        await db.execute(base.order_by(User.created_at.desc(), User.id).limit(limit).offset(offset))
    ).all()

    # One query for the roles of everyone on this page, not one per user.
    ids = [user.id for user, _ in page]
    roles_by_user: dict[uuid.UUID, set[Role]] = {}
    if ids:
        role_rows = await db.execute(
            select(Membership.user_id, Membership.role).where(
                Membership.user_id.in_(ids), Membership.status == MembershipStatus.ACTIVE
            )
        )
        for user_id, role in role_rows.all():
            roles_by_user.setdefault(user_id, set()).add(role)

    rows = [
        UserRow(
            id=user.id,
            email=user.email,
            full_name=full_name,
            status=user.status,
            roles=sorted(roles_by_user.get(user.id, ()), key=lambda r: r.value),
            created_at=user.created_at,
        )
        for user, full_name in page
    ]
    return rows, int(total or 0)
