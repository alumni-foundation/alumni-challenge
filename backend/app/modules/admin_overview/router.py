import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors.exceptions import ForbiddenError, NotFoundError
from app.core.permissions.dependencies import get_user_roles
from app.core.permissions.roles import Role
from app.core.rate_limit.limiter import hit
from app.infrastructure.database.session import get_db_session
from app.infrastructure.redis import get_redis_client
from app.modules.admin_overview import schemas, service
from app.modules.identity.dependencies import get_current_user
from app.modules.identity.models import User
from app.modules.memberships.models import Membership, MembershipStatus
from app.modules.organizations.models import Organization

router = APIRouter(prefix="/admin", tags=["admin"])

CACHE_SECONDS = 60
REQUESTS_PER_MINUTE = 30
_PLATFORM_ADMINS = {Role.ADMIN, Role.SUPER_ADMIN}
_ORG_ROLES = (Role.SCHOOL_ADMIN, Role.PARTNER_ADMIN, Role.EVENT_MANAGER)


async def _own_organizations(db: AsyncSession, user_id: uuid.UUID) -> set[uuid.UUID]:
    stmt = select(Membership.organization_id).where(
        Membership.user_id == user_id,
        Membership.status == MembershipStatus.ACTIVE,
        Membership.role.in_(_ORG_ROLES),
        Membership.organization_id.is_not(None),
    )
    return {org for org in (await db.scalars(stmt)).all() if org is not None}


@router.get("/overview", response_model=schemas.Overview)
async def overview(
    organization_id: uuid.UUID | None = None,
    period: Literal["30d", "90d", "365d"] = Query(default="30d"),
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> schemas.Overview:
    """
    Platform admins: everything, or one organization with `organization_id`. School admins,
    partner admins and event managers: their own organizations only (any other id is 404, whether
    or not it exists). Moderators: the report counts only. Anyone else: 403.
    """
    await hit(
        f"ratelimit:admin_overview:{current_user.id}",
        limit=REQUESTS_PER_MINUTE,
        window_seconds=60,
    )
    roles = await get_user_roles(db, user_id=current_user.id)
    platform = bool(roles & _PLATFORM_ADMINS)
    moderator = Role.MODERATOR in roles
    own = await _own_organizations(db, current_user.id)
    if not (platform or moderator or own):
        raise ForbiddenError("You do not have permission to view the dashboard.")

    scope: set[uuid.UUID] | None
    if organization_id is not None:
        if platform:
            if await db.get(Organization, organization_id) is None:
                raise NotFoundError("Organization not found.")
        elif organization_id not in own:
            raise NotFoundError("Organization not found.")
        scope = {organization_id}
    elif platform:
        scope = None
    else:
        scope = own  # empty for a moderator with no organization: no member sections

    see_members = platform or bool(own)
    see_reports = moderator or (platform and organization_id is None)
    see_audit = see_members

    scope_key = "all" if scope is None else ",".join(sorted(str(o) for o in scope)) or "none"
    key = f"admin_overview:{scope_key}:{period}:{int(see_members)}{int(see_reports)}"
    redis = get_redis_client()
    cached = await redis.get(key)
    if cached:
        # The answer depends on the scope, which is in the key; asking for your only
        # organization by id or without it is the same answer.
        return schemas.Overview.model_validate_json(cached).model_copy(
            update={"organization_id": organization_id}
        )

    result = await service.build(
        db,
        period=period,
        organization_id=organization_id,
        scope=scope,
        see_members=see_members,
        see_reports=see_reports,
        see_audit=see_audit,
    )
    await redis.set(key, result.model_dump_json(), ex=CACHE_SECONDS)
    return result
