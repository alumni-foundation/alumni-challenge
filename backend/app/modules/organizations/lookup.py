"""
Finding a person by email address, on behalf of an organization admin.

An admin needs this to appoint a manager: they know the email, they need the account.
The danger is that it turns into a way to ask "is this person on the platform?" about
anyone. So:

* A match is only returned for someone who already belongs to THIS organization (holds a
  role in it, or, for a school, declared it as their school). Everyone else, including
  people who exist but belong elsewhere, suspended accounts and addresses nobody uses,
  gets the same empty answer.
* The queries run in the same shape whether or not the address exists.
* Every call is rate limited per admin, and audited without storing the address itself.
"""

import hashlib
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions.roles import Role
from app.core.rate_limit import hit
from app.modules.alumni.models import AlumniProfile, VerificationStatus
from app.modules.audit.service import record as record_audit
from app.modules.identity.models import User, UserStatus
from app.modules.memberships.models import Membership, MembershipStatus
from app.modules.organizations.models import Organization, OrganizationType

LOOKUP_LIMIT_PER_HOUR = 30
LOOKUP_WINDOW_SECONDS = 3600


@dataclass(frozen=True)
class LookupMatch:
    user_id: uuid.UUID
    full_name: str | None
    roles_in_organization: list[Role]
    verification_status: VerificationStatus | None


def _email_fingerprint(email: str) -> str:
    """Enough to tell two lookups of the same address apart, not enough to recover it."""
    return hashlib.sha256(email.encode()).hexdigest()[:16]


async def lookup_member_by_email(
    db: AsyncSession, *, organization: Organization, actor: User, email: str
) -> LookupMatch | None:
    await hit(
        f"ratelimit:user_lookup:{actor.id}",
        limit=LOOKUP_LIMIT_PER_HOUR,
        window_seconds=LOOKUP_WINDOW_SECONDS,
    )
    normalized = email.strip().lower()

    user = await db.scalar(
        select(User).where(User.email == normalized, User.status == UserStatus.ACTIVE)
    )
    # Run the same queries for an unknown address as for a known one.
    probe_id = user.id if user is not None else uuid.UUID(int=0)

    roles = list(
        await db.scalars(
            select(Membership.role).where(
                Membership.user_id == probe_id,
                Membership.organization_id == organization.id,
                Membership.status == MembershipStatus.ACTIVE,
            )
        )
    )
    profile = await db.scalar(select(AlumniProfile).where(AlumniProfile.user_id == probe_id))
    declared_school = (
        organization.type == OrganizationType.SCHOOL
        and profile is not None
        and profile.school_id == organization.id
    )
    in_scope = user is not None and (bool(roles) or declared_school)

    match: LookupMatch | None = None
    if in_scope and user is not None:
        match = LookupMatch(
            user_id=user.id,
            full_name=profile.full_name if profile is not None else None,
            roles_in_organization=sorted(roles),
            verification_status=profile.verification_status
            if declared_school and profile
            else None,
        )

    await record_audit(
        db,
        actor_user_id=actor.id,
        action="organization.user_lookup",
        target_type="organization",
        target_id=organization.id,
        context={
            "organization_id": str(organization.id),
            "email_fingerprint": _email_fingerprint(normalized),
            "matched": match is not None,
        },
    )
    return match
