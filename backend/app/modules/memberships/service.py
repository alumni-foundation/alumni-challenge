import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.memberships.models import Membership, MembershipStatus


async def list_active_memberships(db: AsyncSession, *, user_id: uuid.UUID) -> list[Membership]:
    """
    Every active role row this user holds, platform-wide and org-scoped.

    For DISPLAY only (the web app uses it to decide which screens and buttons to show).
    Authorization decisions must still go through core.permissions.get_user_roles;
    the server re-checks every action regardless of what the client showed.
    """
    stmt = (
        select(Membership)
        .where(Membership.user_id == user_id, Membership.status == MembershipStatus.ACTIVE)
        .order_by(Membership.created_at, Membership.id)
    )
    return list((await db.scalars(stmt)).all())
