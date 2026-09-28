import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationError
from app.core.permissions.dependencies import get_user_roles
from app.core.permissions.roles import Role
from app.modules.alumni.models import SchoolEmailDomain
from app.modules.identity.models import User, UserStatus
from app.modules.memberships.models import Membership, MembershipStatus
from app.modules.organizations.models import Organization, OrganizationStatus, OrganizationType

# Free public mailbox providers. A school must never be able to register one of
# these: every account holder would qualify for automatic verification.
PUBLIC_EMAIL_DOMAINS = frozenset(
    {
        "gmail.com", "googlemail.com", "yahoo.com", "yahoo.co.uk", "outlook.com", "hotmail.com",
        "live.com", "msn.com", "icloud.com", "me.com", "aol.com", "proton.me", "protonmail.com",
        "gmx.com", "mail.com", "zoho.com", "yandex.com",
    }
)  # fmt: skip

_PLATFORM_ADMINS = {Role.ADMIN, Role.SUPER_ADMIN}


async def create_organization(
    db: AsyncSession,
    *,
    type: OrganizationType,
    name: str,
    slug: str,
    description: str | None,
) -> Organization:
    if await db.scalar(select(Organization.id).where(Organization.slug == slug)) is not None:
        raise ConflictError("That slug is already taken.")
    org = Organization(type=type, name=name, slug=slug, description=description)
    try:
        async with db.begin_nested():
            db.add(org)
            await db.flush()
    except IntegrityError as exc:
        raise ConflictError("That slug is already taken.") from exc
    return org


async def get_active_organization(db: AsyncSession, *, organization_id: uuid.UUID) -> Organization:
    org = await db.get(Organization, organization_id)
    if org is None or org.status != OrganizationStatus.ACTIVE:
        raise NotFoundError("Organization not found.")
    return org


async def list_organizations(
    db: AsyncSession, *, type: OrganizationType | None, limit: int, offset: int
) -> list[Organization]:
    stmt = select(Organization).where(Organization.status == OrganizationStatus.ACTIVE)
    if type is not None:
        stmt = stmt.where(Organization.type == type)
    stmt = stmt.order_by(Organization.name, Organization.id).limit(limit).offset(offset)
    return list((await db.scalars(stmt)).all())


async def update_organization(
    db: AsyncSession, *, organization_id: uuid.UUID, **fields: object
) -> Organization:
    org = await get_active_organization(db, organization_id=organization_id)
    for key, value in fields.items():
        if value is None and key == "name":
            continue
        setattr(org, key, value)
    await db.flush()
    return org


async def assign_membership(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    actor: User,
    target_user_id: uuid.UUID,
    role: Role,
) -> Membership:
    """
    Who may grant what (permission matrix):
      school_admin / partner_admin  -> platform admins only
      event_manager / sports_manager -> that organization's admin, or a platform admin
    Everything else (alumni, moderator, platform roles) is not assignable here.
    """
    org = await get_active_organization(db, organization_id=organization_id)
    actor_roles = await get_user_roles(db, user_id=actor.id, organization_id=organization_id)

    if role in (Role.SCHOOL_ADMIN, Role.PARTNER_ADMIN):
        if not actor_roles & _PLATFORM_ADMINS:
            raise ForbiddenError("Only platform administrators can appoint organization admins.")
        expected = (
            OrganizationType.SCHOOL if role == Role.SCHOOL_ADMIN else OrganizationType.PARTNER
        )
        if org.type != expected:
            raise ValidationError(f"The {role.value} role only applies to a {expected.value}.")
    elif role in (Role.EVENT_MANAGER, Role.SPORTS_MANAGER):
        org_admin = Role.SCHOOL_ADMIN if org.type == OrganizationType.SCHOOL else Role.PARTNER_ADMIN
        if not actor_roles & (_PLATFORM_ADMINS | {org_admin}):
            raise ForbiddenError("You do not have permission to assign this role.")
    else:
        raise ValidationError("This role cannot be assigned to an organization member.")

    target = await db.get(User, target_user_id)
    if target is None or target.status != UserStatus.ACTIVE:
        raise NotFoundError("User not found.")

    existing = await db.scalar(
        select(Membership).where(
            Membership.user_id == target_user_id,
            Membership.organization_id == organization_id,
            Membership.role == role,
        )
    )
    if existing is not None:
        if existing.status == MembershipStatus.ACTIVE:
            raise ConflictError("This user already holds that role.")
        existing.status = MembershipStatus.ACTIVE
        await db.flush()
        return existing

    membership = Membership(user_id=target_user_id, organization_id=organization_id, role=role)
    db.add(membership)
    await db.flush()
    return membership


async def add_email_domain(
    db: AsyncSession, *, organization_id: uuid.UUID, domain: str
) -> SchoolEmailDomain:
    org = await get_active_organization(db, organization_id=organization_id)
    if org.type != OrganizationType.SCHOOL:
        raise ValidationError("Email domains can only be registered for schools.")
    if domain in PUBLIC_EMAIL_DOMAINS:
        raise ValidationError("Public email providers cannot be used for verification.")
    if await db.scalar(select(SchoolEmailDomain.id).where(SchoolEmailDomain.domain == domain)):
        raise ConflictError("That domain is already registered.")
    row = SchoolEmailDomain(organization_id=organization_id, domain=domain)
    try:
        async with db.begin_nested():
            db.add(row)
            await db.flush()
    except IntegrityError as exc:
        raise ConflictError("That domain is already registered.") from exc
    return row


async def list_email_domains(
    db: AsyncSession, *, organization_id: uuid.UUID
) -> list[SchoolEmailDomain]:
    await get_active_organization(db, organization_id=organization_id)
    stmt = (
        select(SchoolEmailDomain)
        .where(SchoolEmailDomain.organization_id == organization_id)
        .order_by(SchoolEmailDomain.domain)
    )
    return list((await db.scalars(stmt)).all())
