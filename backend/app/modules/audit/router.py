from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors.exceptions import ForbiddenError
from app.core.permissions.dependencies import get_user_roles
from app.core.permissions.roles import Role
from app.infrastructure.database.session import get_db_session
from app.modules.audit import schemas, service
from app.modules.audit.models import AuditLogEntry
from app.modules.identity.dependencies import get_current_user
from app.modules.identity.models import User
from app.modules.memberships.service import list_administered_organization_ids

router = APIRouter(prefix="/audit-log", tags=["audit"])

_PLATFORM_ADMINS = {Role.ADMIN, Role.SUPER_ADMIN}


@router.get("", response_model=list[schemas.AuditLogEntryResponse])
async def list_audit_log(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> list[AuditLogEntry]:
    """
    Platform admins see everything. A school_admin or partner_admin
    sees only entries tagged with an organization they administer —
    membership grants, email-domain changes, profile verifications for
    THEIR school, not anyone else's, and never platform-wide actions
    like a password reset. Anyone holding neither gets 403.
    """
    platform_roles = await get_user_roles(db, user_id=current_user.id)
    if platform_roles & _PLATFORM_ADMINS:
        return await service.list_entries(db, organization_ids=None, limit=limit, offset=offset)

    org_ids = await list_administered_organization_ids(db, user_id=current_user.id)
    if not org_ids:
        raise ForbiddenError("You do not have permission to view the audit log.")
    return await service.list_entries(db, organization_ids=org_ids, limit=limit, offset=offset)
