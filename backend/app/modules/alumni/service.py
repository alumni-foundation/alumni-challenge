import enum
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.core.permissions.roles import Role
from app.modules.alumni.models import (
    AlumniProfile,
    ProfileVisibility,
    VerificationMethod,
    VerificationStatus,
)
from app.modules.connections.models import Connection, ConnectionStatus
from app.modules.memberships.models import Membership, MembershipStatus


class ViewerTier(enum.IntEnum):
    """
    Ordered so a higher tier always satisfies a lower tier's
    requirement — ANONYMOUS < MEMBER < CONNECTION < OWNER. This
    ordering is the whole privacy model: comparing two integers.
    """

    ANONYMOUS = 0
    MEMBER = 1
    CONNECTION = 2
    OWNER = 3


_VISIBILITY_REQUIRES: dict[ProfileVisibility, ViewerTier] = {
    ProfileVisibility.PUBLIC: ViewerTier.ANONYMOUS,
    ProfileVisibility.MEMBERS_ONLY: ViewerTier.MEMBER,
    ProfileVisibility.CONNECTIONS_ONLY: ViewerTier.CONNECTION,
    ProfileVisibility.PRIVATE: ViewerTier.OWNER,
}


async def create_own_profile(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    full_name: str,
    bio: str | None,
    graduation_year: int | None,
    school_id: uuid.UUID | None,
    country: str | None,
    profession: str | None,
    company: str | None,
    profile_visibility: ProfileVisibility,
) -> AlumniProfile:
    existing = await db.scalar(select(AlumniProfile).where(AlumniProfile.user_id == user_id))
    if existing is not None:
        raise ConflictError("A profile already exists for this account.")

    profile = AlumniProfile(
        user_id=user_id,
        full_name=full_name,
        bio=bio,
        graduation_year=graduation_year,
        school_id=school_id,
        country=country,
        profession=profession,
        company=company,
        profile_visibility=profile_visibility,
    )
    db.add(profile)
    await db.flush()
    return profile


async def get_own_profile(db: AsyncSession, *, user_id: uuid.UUID) -> AlumniProfile:
    profile = await db.scalar(select(AlumniProfile).where(AlumniProfile.user_id == user_id))
    if profile is None:
        raise NotFoundError("No profile found for this account.")
    return profile


async def update_own_profile(
    db: AsyncSession, *, user_id: uuid.UUID, **fields: object
) -> AlumniProfile:
    profile = await get_own_profile(db, user_id=user_id)
    for key, value in fields.items():
        if value is not None:
            setattr(profile, key, value)
    await db.flush()
    return profile


async def _get_profile_by_id(db: AsyncSession, *, profile_id: uuid.UUID) -> AlumniProfile:
    profile = await db.get(AlumniProfile, profile_id)
    if profile is None:
        raise NotFoundError("Profile not found.")
    return profile


async def _are_connected(db: AsyncSession, *, user_a: uuid.UUID, user_b: uuid.UUID) -> bool:
    stmt = select(Connection).where(
        Connection.status == ConnectionStatus.ACCEPTED,
        (
            ((Connection.requester_id == user_a) & (Connection.addressee_id == user_b))
            | ((Connection.requester_id == user_b) & (Connection.addressee_id == user_a))
        ),
    )
    return (await db.scalar(stmt)) is not None


async def _has_full_access_override(
    db: AsyncSession, *, viewer_user_id: uuid.UUID, profile: AlumniProfile
) -> bool:
    """
    Platform admins/super_admins always see everything. A school_admin
    sees full visibility (not full CONTACT fields — email/phone aren't
    on this model, see the module docstring) for alumni in their own
    school, regardless of the alumni's chosen visibility — per Phase 0
    privacy-rules.md override rule 3.
    """
    stmt = select(Membership.role, Membership.organization_id).where(
        Membership.user_id == viewer_user_id, Membership.status == MembershipStatus.ACTIVE
    )
    rows = (await db.execute(stmt)).all()
    for role, org_id in rows:
        if role in (Role.ADMIN, Role.SUPER_ADMIN):
            return True
        if (
            role == Role.SCHOOL_ADMIN
            and profile.school_id is not None
            and org_id == profile.school_id
        ):
            return True
    return False


async def get_profile_for_viewer(
    db: AsyncSession, *, profile_id: uuid.UUID, viewer_user_id: uuid.UUID | None
) -> AlumniProfile:
    """
    THE enforcement point. Every read of a profile — directory,
    single-profile view, anything — must go through this function.
    Raises NotFoundError (never ForbiddenError) when visibility fails,
    so a viewer can't distinguish "doesn't exist" from "not visible to
    you" — that distinction is itself information leakage.
    """
    profile = await _get_profile_by_id(db, profile_id=profile_id)

    if viewer_user_id is not None and viewer_user_id == profile.user_id:
        return profile

    if viewer_user_id is not None and await _has_full_access_override(
        db, viewer_user_id=viewer_user_id, profile=profile
    ):
        return profile

    tier = ViewerTier.ANONYMOUS
    if viewer_user_id is not None:
        tier = ViewerTier.MEMBER
        if await _are_connected(db, user_a=viewer_user_id, user_b=profile.user_id):
            tier = ViewerTier.CONNECTION

    required = _VISIBILITY_REQUIRES[profile.profile_visibility]
    if tier < required:
        raise NotFoundError("Profile not found.")

    return profile


def build_profile_response_fields(
    profile: AlumniProfile, *, viewer_user_id: uuid.UUID | None
) -> dict[str, object]:
    """
    Applies the field-by-field matrix from privacy-rules.md on top of
    a profile that has already passed get_profile_for_viewer's
    visibility gate. The only field this touches right now is
    `company` — hidden from a genuinely anonymous viewer, shown to
    everyone else who can see the profile at all (owner, any
    authenticated member, connection, or an override role).
    """
    is_owner = viewer_user_id is not None and viewer_user_id == profile.user_id
    is_anonymous = viewer_user_id is None

    fields = {
        "id": profile.id,
        "user_id": profile.user_id,
        "full_name": profile.full_name,
        "bio": profile.bio,
        "graduation_year": profile.graduation_year,
        "school_id": profile.school_id,
        "country": profile.country,
        "profession": profile.profession,
        "company": None if (is_anonymous and not is_owner) else profile.company,
        "verification_status": profile.verification_status,
        "profile_visibility": profile.profile_visibility,
        "avatar_file_id": profile.avatar_file_id,
        "created_at": profile.created_at,
    }
    return fields


async def verify_profile(
    db: AsyncSession, *, profile_id: uuid.UUID, verifier_user_id: uuid.UUID, verified: bool
) -> AlumniProfile:
    profile = await _get_profile_by_id(db, profile_id=profile_id)

    if profile.school_id is None:
        raise ForbiddenError("This profile has no school affiliation to verify against.")

    has_permission = await _has_full_access_override(
        db, viewer_user_id=verifier_user_id, profile=profile
    )
    if not has_permission:
        raise ForbiddenError("You do not have permission to verify this profile.")

    profile.verification_status = (
        VerificationStatus.VERIFIED if verified else VerificationStatus.UNVERIFIED
    )
    profile.verification_method = VerificationMethod.ADMIN if verified else None
    await db.flush()
    return profile
