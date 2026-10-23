"""
Who belongs to an organization, for that organization's admins.

Two lists, both always filtered by the organization in the URL (the route's own permission
check is the first gate, this filter is the second, so a mistake in either one alone cannot
show one school's people to another):

* members: the people who hold a role in the organization (its admins and managers).
* roster: a school's alumni, meaning the profiles that declared this school, with a filter for
  the ones still waiting to be verified.

The roster shows what an admin needs to verify someone and nothing more: name, graduation
year, country and verification state. No email address, company, profession or bio. A profile
set to private still appears in its own school's roster (the permission matrix says a school
admin always sees their own school's roster) but only with those fields.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors.exceptions import ValidationError
from app.core.permissions.roles import Role
from app.modules.alumni.models import (
    AlumniProfile,
    VerificationMethod,
    VerificationStatus,
)
from app.modules.identity.models import User, UserStatus
from app.modules.memberships.models import Membership, MembershipStatus
from app.modules.organizations.models import Organization, OrganizationType


@dataclass(frozen=True)
class MemberRow:
    membership_id: uuid.UUID
    user_id: uuid.UUID
    email: str
    full_name: str | None
    role: Role
    status: MembershipStatus
    account_status: UserStatus
    since: datetime


@dataclass(frozen=True)
class RosterRow:
    profile_id: uuid.UUID
    user_id: uuid.UUID
    full_name: str
    graduation_year: int | None
    country: str | None
    verification_status: VerificationStatus
    verification_method: VerificationMethod | None
    email_verified: bool
    joined_at: datetime


async def list_members(
    db: AsyncSession,
    *,
    organization: Organization,
    role: Role | None,
    include_revoked: bool,
    limit: int,
    offset: int,
) -> tuple[list[MemberRow], int]:
    conditions = [Membership.organization_id == organization.id]
    if not include_revoked:
        conditions.append(Membership.status == MembershipStatus.ACTIVE)
    if role is not None:
        conditions.append(Membership.role == role)

    total = await db.scalar(select(func.count()).select_from(Membership).where(*conditions))
    stmt = (
        select(Membership, User, AlumniProfile.full_name)
        .join(User, User.id == Membership.user_id)
        .outerjoin(AlumniProfile, AlumniProfile.user_id == Membership.user_id)
        .where(*conditions)
        .order_by(Membership.created_at, Membership.id)
        .limit(limit)
        .offset(offset)
    )
    rows = [
        MemberRow(
            membership_id=m.id,
            user_id=u.id,
            email=u.email,
            full_name=full_name,
            role=m.role,
            status=m.status,
            account_status=u.status,
            since=m.created_at,
        )
        for m, u, full_name in (await db.execute(stmt)).all()
    ]
    return rows, int(total or 0)


async def list_school_roster(
    db: AsyncSession,
    *,
    organization: Organization,
    verification: VerificationStatus | None,
    graduation_year: int | None,
    limit: int,
    offset: int,
) -> tuple[list[RosterRow], int]:
    if organization.type != OrganizationType.SCHOOL:
        raise ValidationError("Only a school has an alumni roster.")

    conditions = [
        AlumniProfile.school_id == organization.id,
        User.status == UserStatus.ACTIVE,
    ]
    if verification is not None:
        conditions.append(AlumniProfile.verification_status == verification)
    if graduation_year is not None:
        conditions.append(AlumniProfile.graduation_year == graduation_year)

    total = await db.scalar(
        select(func.count())
        .select_from(AlumniProfile)
        .join(User, User.id == AlumniProfile.user_id)
        .where(*conditions)
    )
    stmt = (
        select(AlumniProfile, User.email_verified_at)
        .join(User, User.id == AlumniProfile.user_id)
        .where(*conditions)
        .order_by(AlumniProfile.full_name, AlumniProfile.id)
        .limit(limit)
        .offset(offset)
    )
    rows = [
        RosterRow(
            profile_id=p.id,
            user_id=p.user_id,
            full_name=p.full_name,
            graduation_year=p.graduation_year,
            country=p.country,
            verification_status=p.verification_status,
            verification_method=p.verification_method,
            email_verified=verified_at is not None,
            joined_at=p.created_at,
        )
        for p, verified_at in (await db.execute(stmt)).all()
    ]
    return rows, int(total or 0)
