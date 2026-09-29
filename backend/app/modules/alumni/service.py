import enum
import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationError
from app.core.permissions.roles import Role
from app.modules.alumni.models import (
    AlumniInterest,
    AlumniProfile,
    AlumniSkill,
    Interest,
    PeerVouch,
    ProfileVisibility,
    SchoolEmailDomain,
    Skill,
    VerificationMethod,
    VerificationStatus,
)
from app.modules.connections.models import Connection, ConnectionStatus
from app.modules.identity.models import User
from app.modules.memberships.models import Membership, MembershipStatus
from app.modules.organizations.models import Organization, OrganizationStatus, OrganizationType

# Number of verified alumni of the same school who must vouch before a profile
# is verified automatically (Phase 0 decision).
VOUCH_THRESHOLD = 3


class ViewerTier(enum.IntEnum):
    """
    Ordered so a higher tier always satisfies a lower tier's
    requirement: ANONYMOUS < MEMBER < CONNECTION < OWNER. This
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


async def _validate_school(db: AsyncSession, school_id: uuid.UUID) -> None:
    org = await db.get(Organization, school_id)
    if (
        org is None
        or org.type != OrganizationType.SCHOOL
        or org.status != OrganizationStatus.ACTIVE
    ):
        raise ValidationError("The selected school does not exist.")


async def _maybe_verify_by_email_domain(
    db: AsyncSession, *, profile: AlumniProfile, user: User
) -> None:
    """
    Auto-verify when the user's VERIFIED email address is on a domain the
    school has registered. Requires email_verified_at: without proof of
    ownership of the mailbox, anyone could type a school address at signup
    and claim the badge.
    """
    if profile.school_id is None or user.email_verified_at is None:
        return
    if profile.verification_status == VerificationStatus.VERIFIED:
        return
    domain = user.email.rsplit("@", 1)[-1].lower()
    match = await db.scalar(
        select(SchoolEmailDomain).where(
            SchoolEmailDomain.organization_id == profile.school_id,
            SchoolEmailDomain.domain == domain,
        )
    )
    if match is not None:
        profile.verification_status = VerificationStatus.VERIFIED
        profile.verification_method = VerificationMethod.EMAIL_DOMAIN


async def verify_email_domain_for_user(db: AsyncSession, *, user: User) -> None:
    """
    Called right after a user's email is confirmed (identity/service.py),
    so a profile that already declared a matching school gets its
    email-domain verification the moment it becomes possible, instead of
    waiting for the person to touch their profile again.
    """
    profile = await db.scalar(select(AlumniProfile).where(AlumniProfile.user_id == user.id))
    if profile is None:
        return
    await _maybe_verify_by_email_domain(db, profile=profile, user=user)
    await db.flush()


async def create_own_profile(
    db: AsyncSession,
    *,
    user: User,
    full_name: str,
    bio: str | None,
    graduation_year: int | None,
    school_id: uuid.UUID | None,
    country: str | None,
    profession: str | None,
    company: str | None,
    profile_visibility: ProfileVisibility,
) -> AlumniProfile:
    existing = await db.scalar(select(AlumniProfile).where(AlumniProfile.user_id == user.id))
    if existing is not None:
        raise ConflictError("A profile already exists for this account.")
    if school_id is not None:
        await _validate_school(db, school_id)

    profile = AlumniProfile(
        user_id=user.id,
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
    await _maybe_verify_by_email_domain(db, profile=profile, user=user)
    await db.flush()
    return profile


async def get_own_profile(db: AsyncSession, *, user_id: uuid.UUID) -> AlumniProfile:
    profile = await db.scalar(select(AlumniProfile).where(AlumniProfile.user_id == user_id))
    if profile is None:
        raise NotFoundError("No profile found for this account.")
    return profile


# Columns that cannot be cleared: sending null for these is ignored.
_NOT_NULLABLE = {"full_name", "profile_visibility"}


async def update_own_profile(db: AsyncSession, *, user: User, **fields: object) -> AlumniProfile:
    profile = await get_own_profile(db, user_id=user.id)

    school_changed = "school_id" in fields and fields["school_id"] != profile.school_id
    if school_changed and fields["school_id"] is not None:
        assert isinstance(fields["school_id"], uuid.UUID)
        await _validate_school(db, fields["school_id"])

    for key, value in fields.items():
        if value is None and key in _NOT_NULLABLE:
            continue
        setattr(profile, key, value)

    if school_changed:
        # Verification belongs to a specific school. Moving to another one
        # must not carry the badge along.
        profile.verification_status = VerificationStatus.UNVERIFIED
        profile.verification_method = None
        await db.flush()
        await _maybe_verify_by_email_domain(db, profile=profile, user=user)

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
    sees full visibility for alumni in their own school, regardless of the
    alumni's chosen visibility (privacy-rules.md override rule 3).
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
    THE enforcement point. Every read of a profile must go through this
    function. Raises NotFoundError (never ForbiddenError) when visibility
    fails, so a viewer can't distinguish "doesn't exist" from "not visible
    to you".
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

    if tier < _VISIBILITY_REQUIRES[profile.profile_visibility]:
        raise NotFoundError("Profile not found.")

    return profile


def build_profile_response_fields(
    profile: AlumniProfile,
    *,
    viewer_user_id: uuid.UUID | None,
    skills: list[str] | None = None,
    interests: list[str] | None = None,
    vouch_count: int | None = None,
) -> dict[str, object]:
    """
    Field-by-field matrix from privacy-rules.md, applied to a profile that
    already passed get_profile_for_viewer. `company` and `vouch_count` are
    hidden from genuinely anonymous viewers.
    """
    is_owner = viewer_user_id is not None and viewer_user_id == profile.user_id
    hide = viewer_user_id is None and not is_owner
    return {
        "id": profile.id,
        "user_id": profile.user_id,
        "full_name": profile.full_name,
        "bio": profile.bio,
        "graduation_year": profile.graduation_year,
        "school_id": profile.school_id,
        "country": profile.country,
        "profession": profile.profession,
        "company": None if hide else profile.company,
        "verification_status": profile.verification_status,
        "profile_visibility": profile.profile_visibility,
        "avatar_file_id": profile.avatar_file_id,
        "created_at": profile.created_at,
        "skills": skills or [],
        "interests": interests or [],
        "vouch_count": None if hide else vouch_count,
    }


async def _count_valid_vouches(db: AsyncSession, *, profile: AlumniProfile) -> int:
    """Vouches from currently-verified alumni of the same school as the profile."""
    if profile.school_id is None:
        return 0
    stmt = (
        select(func.count())
        .select_from(PeerVouch)
        .join(AlumniProfile, AlumniProfile.user_id == PeerVouch.voucher_user_id)
        .where(
            PeerVouch.vouched_user_id == profile.user_id,
            AlumniProfile.verification_status == VerificationStatus.VERIFIED,
            AlumniProfile.school_id == profile.school_id,
        )
    )
    return int(await db.scalar(stmt) or 0)


async def build_profile_response(
    db: AsyncSession, *, profile: AlumniProfile, viewer_user_id: uuid.UUID | None
) -> dict[str, object]:
    skills = list(
        (
            await db.scalars(
                select(Skill.name)
                .join(AlumniSkill, AlumniSkill.skill_id == Skill.id)
                .where(AlumniSkill.alumni_profile_id == profile.id)
                .order_by(Skill.name)
            )
        ).all()
    )
    interests = list(
        (
            await db.scalars(
                select(Interest.name)
                .join(AlumniInterest, AlumniInterest.interest_id == Interest.id)
                .where(AlumniInterest.alumni_profile_id == profile.id)
                .order_by(Interest.name)
            )
        ).all()
    )
    return build_profile_response_fields(
        profile,
        viewer_user_id=viewer_user_id,
        skills=skills,
        interests=interests,
        vouch_count=await _count_valid_vouches(db, profile=profile),
    )


async def set_skills(db: AsyncSession, *, user_id: uuid.UUID, names: list[str]) -> AlumniProfile:
    profile = await get_own_profile(db, user_id=user_id)
    await db.execute(delete(AlumniSkill).where(AlumniSkill.alumni_profile_id == profile.id))
    if names:
        # ON CONFLICT DO NOTHING keeps this safe when two users add the same new skill at once.
        await db.execute(
            pg_insert(Skill)
            .values([{"id": uuid.uuid4(), "name": n} for n in names])
            .on_conflict_do_nothing(index_elements=["name"])
        )
        ids = (await db.scalars(select(Skill.id).where(Skill.name.in_(names)))).all()
        db.add_all([AlumniSkill(alumni_profile_id=profile.id, skill_id=i) for i in ids])
    await db.flush()
    return profile


async def set_interests(db: AsyncSession, *, user_id: uuid.UUID, names: list[str]) -> AlumniProfile:
    profile = await get_own_profile(db, user_id=user_id)
    await db.execute(delete(AlumniInterest).where(AlumniInterest.alumni_profile_id == profile.id))
    if names:
        await db.execute(
            pg_insert(Interest)
            .values([{"id": uuid.uuid4(), "name": n} for n in names])
            .on_conflict_do_nothing(index_elements=["name"])
        )
        ids = (await db.scalars(select(Interest.id).where(Interest.name.in_(names)))).all()
        db.add_all([AlumniInterest(alumni_profile_id=profile.id, interest_id=i) for i in ids])
    await db.flush()
    return profile


async def vouch_for_profile(
    db: AsyncSession, *, profile_id: uuid.UUID, voucher_user_id: uuid.UUID
) -> AlumniProfile:
    # The voucher must be able to see the profile at all; otherwise 404 like any other viewer.
    target = await get_profile_for_viewer(db, profile_id=profile_id, viewer_user_id=voucher_user_id)
    if target.user_id == voucher_user_id:
        raise ValidationError("You cannot vouch for yourself.")

    voucher = await db.scalar(select(AlumniProfile).where(AlumniProfile.user_id == voucher_user_id))
    if voucher is None or voucher.verification_status != VerificationStatus.VERIFIED:
        raise ForbiddenError("Only verified alumni can vouch for others.")
    if target.school_id is None or voucher.school_id != target.school_id:
        raise ForbiddenError("You can only vouch for alumni of your own school.")

    try:
        async with db.begin_nested():
            db.add(PeerVouch(vouched_user_id=target.user_id, voucher_user_id=voucher_user_id))
            await db.flush()
    except IntegrityError as exc:
        raise ConflictError("You have already vouched for this person.") from exc

    if (
        target.verification_status != VerificationStatus.VERIFIED
        and await _count_valid_vouches(db, profile=target) >= VOUCH_THRESHOLD
    ):
        target.verification_status = VerificationStatus.VERIFIED
        target.verification_method = VerificationMethod.PEER
        await db.flush()
    return target


async def verify_profile(
    db: AsyncSession, *, profile_id: uuid.UUID, verifier_user_id: uuid.UUID, verified: bool
) -> AlumniProfile:
    profile = await _get_profile_by_id(db, profile_id=profile_id)

    if profile.school_id is None:
        raise ForbiddenError("This profile has no school affiliation to verify against.")

    if not await _has_full_access_override(db, viewer_user_id=verifier_user_id, profile=profile):
        raise ForbiddenError("You do not have permission to verify this profile.")

    profile.verification_status = (
        VerificationStatus.VERIFIED if verified else VerificationStatus.UNVERIFIED
    )
    profile.verification_method = VerificationMethod.ADMIN if verified else None
    await db.flush()
    return profile
