import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions.dependencies import require_roles, require_roles_for_org
from app.core.permissions.roles import Role
from app.infrastructure.database.session import get_db_session
from app.modules.alumni.models import SchoolEmailDomain
from app.modules.identity.dependencies import get_current_user
from app.modules.identity.models import User
from app.modules.memberships.models import Membership
from app.modules.organizations import schemas, service
from app.modules.organizations.models import Organization, OrganizationType

router = APIRouter(prefix="/organizations", tags=["organizations"])

_ORG_ADMINS = (Role.SCHOOL_ADMIN, Role.PARTNER_ADMIN, Role.ADMIN, Role.SUPER_ADMIN)


@router.post("", response_model=schemas.OrganizationResponse, status_code=status.HTTP_201_CREATED)
async def create_organization(
    body: schemas.OrganizationCreate,
    db: AsyncSession = Depends(get_db_session),
    _admin: User = Depends(require_roles(Role.ADMIN, Role.SUPER_ADMIN)),
) -> Organization:
    org = await service.create_organization(
        db, type=body.type, name=body.name, slug=body.slug, description=body.description
    )
    await db.commit()
    return org


@router.get("", response_model=list[schemas.OrganizationResponse])
async def list_organizations(
    db: AsyncSession = Depends(get_db_session),
    type: OrganizationType | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[Organization]:
    return await service.list_organizations(db, type=type, limit=limit, offset=offset)


@router.get("/{organization_id}", response_model=schemas.OrganizationResponse)
async def get_organization(
    organization_id: uuid.UUID, db: AsyncSession = Depends(get_db_session)
) -> Organization:
    return await service.get_active_organization(db, organization_id=organization_id)


@router.patch("/{organization_id}", response_model=schemas.OrganizationResponse)
async def update_organization(
    organization_id: uuid.UUID,
    body: schemas.OrganizationUpdate,
    db: AsyncSession = Depends(get_db_session),
    _admin: User = Depends(require_roles_for_org(*_ORG_ADMINS)),
) -> Organization:
    org = await service.update_organization(
        db, organization_id=organization_id, **body.model_dump(exclude_unset=True)
    )
    await db.commit()
    return org


@router.post(
    "/{organization_id}/memberships",
    response_model=schemas.MembershipResponse,
    status_code=status.HTTP_201_CREATED,
)
async def assign_membership(
    organization_id: uuid.UUID,
    body: schemas.MembershipCreate,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> Membership:
    membership = await service.assign_membership(
        db,
        organization_id=organization_id,
        actor=current_user,
        target_user_id=body.user_id,
        role=body.role,
    )
    await db.commit()
    return membership


@router.post(
    "/{organization_id}/email-domains",
    response_model=schemas.EmailDomainResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_email_domain(
    organization_id: uuid.UUID,
    body: schemas.EmailDomainCreate,
    db: AsyncSession = Depends(get_db_session),
    _admin: User = Depends(require_roles_for_org(Role.SCHOOL_ADMIN, Role.ADMIN, Role.SUPER_ADMIN)),
) -> SchoolEmailDomain:
    row = await service.add_email_domain(db, organization_id=organization_id, domain=body.domain)
    await db.commit()
    return row


@router.get(
    "/{organization_id}/email-domains",
    response_model=list[schemas.EmailDomainResponse],
)
async def list_email_domains(
    organization_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    _admin: User = Depends(require_roles_for_org(Role.SCHOOL_ADMIN, Role.ADMIN, Role.SUPER_ADMIN)),
) -> list[SchoolEmailDomain]:
    return await service.list_email_domains(db, organization_id=organization_id)
