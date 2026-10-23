import uuid

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions.dependencies import require_roles
from app.core.permissions.roles import Role
from app.infrastructure.database.session import get_db_session
from app.modules.identity.models import User
from app.modules.memberships import role_changes
from app.modules.memberships.models import Membership
from app.modules.organizations.schemas import MembershipResponse

router = APIRouter(tags=["roles"])


class PlatformRoleRequest(BaseModel):
    role: Role


@router.post(
    "/users/{user_id}/platform-roles",
    response_model=MembershipResponse,
    status_code=status.HTTP_201_CREATED,
)
async def grant_platform_role(
    user_id: uuid.UUID,
    body: PlatformRoleRequest,
    db: AsyncSession = Depends(get_db_session),
    actor: User = Depends(require_roles(Role.ADMIN, Role.SUPER_ADMIN)),
) -> Membership:
    """
    Give someone a platform-wide role (super_admin, admin or moderator). A super admin can
    grant any of them; an admin can grant moderator only, and only to someone ranked below
    admin. Nobody can change their own roles.
    """
    membership = await role_changes.grant_platform_role(
        db, actor=actor, target_user_id=user_id, role=body.role
    )
    await db.commit()
    return membership


@router.delete("/users/{user_id}/platform-roles/{role}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_platform_role(
    user_id: uuid.UUID,
    role: Role,
    db: AsyncSession = Depends(get_db_session),
    actor: User = Depends(require_roles(Role.ADMIN, Role.SUPER_ADMIN)),
) -> Response:
    """Same rank rule as granting. The last super admin can never be revoked."""
    await role_changes.revoke_platform_role(db, actor=actor, target_user_id=user_id, role=role)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
