import uuid

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions.dependencies import require_roles, require_roles_for_org
from app.core.permissions.roles import Role
from app.core.rate_limit import rate_limit
from app.infrastructure.database.session import get_db_session
from app.modules.alumni.models import SchoolEmailDomain
from app.modules.identity.dependencies import get_current_user
from app.modules.identity.models import User
from app.modules.memberships import role_changes
from app.modules.memberships.models import Membership
from app.modules.organizations import lookup, schemas, service
from app.modules.organizations.models import Organization, OrganizationType

router = APIRouter(prefix="/organizations", tags=["organizations"])

_ORG_ADMINS = (Role.SCHOOL_ADMIN, Role.PARTNER_ADMIN, Role.ADMIN, Role.SUPER_ADMIN)


@router.post("", response_model=schemas.OrganizationResponse, status_code=status.HTTP_201_CREATED)
async def create_organization(
    body: schemas.OrganizationCreate,
    db: AsyncSession = Depends(get_db_session),
    admin: User = Depends(require_roles(Role.ADMIN, Role.SUPER_ADMIN)),
) -> Organization:
    org = await service.create_organization(
        db,
        actor=admin,
        type=body.type,
        name=body.name,
        slug=body.slug,
        description=body.description,
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
    admin: User = Depends(require_roles_for_org(Role.SCHOOL_ADMIN, Role.ADMIN, Role.SUPER_ADMIN)),
) -> SchoolEmailDomain:
    row = await service.add_email_domain(
        db, organization_id=organization_id, domain=body.domain, actor=admin
    )
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


@router.post(
    "/{organization_id}/user-lookup",
    response_model=schemas.UserLookupResponse,
    dependencies=[Depends(rate_limit("user_lookup_ip", limit=120, window_seconds=3600))],
)
async def look_up_member(
    organization_id: uuid.UUID,
    body: schemas.UserLookupRequest,
    db: AsyncSession = Depends(get_db_session),
    admin: User = Depends(require_roles_for_org(*_ORG_ADMINS)),
) -> schemas.UserLookupResponse:
    """
    Find a member of THIS organization by email, for example to appoint them as a manager.
    Always answers 200. Anyone who is not a member of this organization, including people
    with accounts elsewhere and addresses nobody uses, gets `{"match": null}`, so this cannot
    be used to find out who is on the platform. Limited to 30 lookups an hour per admin.
    The address is a POST body (not a URL) so it stays out of access logs, and the audit
    entry keeps only a fingerprint of it.
    """
    organization = await service.get_active_organization(db, organization_id=organization_id)
    found = await lookup.lookup_member_by_email(
        db, organization=organization, actor=admin, email=body.email
    )
    await db.commit()
    if found is None:
        return schemas.UserLookupResponse(match=None)
    return schemas.UserLookupResponse(
        match=schemas.UserLookupMatch(
            user_id=found.user_id,
            full_name=found.full_name,
            roles_in_organization=found.roles_in_organization,
            verification_status=found.verification_status,
        )
    )


@router.delete(
    "/{organization_id}/memberships/{membership_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def revoke_membership(
    organization_id: uuid.UUID,
    membership_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    admin: User = Depends(require_roles_for_org(*_ORG_ADMINS)),
) -> Response:
    """
    Remove a role from this organization. School and partner admins can remove their own
    managers (event_manager, sports_manager); only platform admins can remove an
    organization admin. Nobody can remove their own role.
    """
    await role_changes.revoke_organization_membership(
        db, actor=admin, organization_id=organization_id, membership_id=membership_id
    )
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
