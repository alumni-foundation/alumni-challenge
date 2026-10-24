"""
A person's rights over their own data: getting a copy of it, and having it erased.

Erasure here means anonymization, because some records have to outlive the person (a
moderation report, an audit trail of who did what). The rule is: everything that says who the
person was is removed or replaced, and everything that only records that something happened
stays.

* Removed: email address, password, profile details, skills, interests, vouches, connections,
  avatar picture, device and network details of their sessions, queued emails about them.
* Kept, with the identity taken out: the audit log (actor and subject are cleared), reports they
  filed (the reporter is now an anonymous, deleted account), files that belong to an
  organization (a logo), and the user row itself, now holding no personal data, so records that
  point at it stay valid.
* The account can never sign in again, and the same email address can be used to register anew.
"""

import secrets
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, or_, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors.exceptions import ConflictError, ValidationError
from app.core.permissions.dependencies import get_user_roles
from app.core.permissions.roles import Role
from app.core.rate_limit import hit
from app.infrastructure.redis import get_redis_client
from app.modules.alumni.models import (
    AlumniInterest,
    AlumniProfile,
    AlumniSkill,
    Interest,
    PeerVouch,
    ProfileVisibility,
    Skill,
    VerificationStatus,
)
from app.modules.audit.models import AuditLogEntry
from app.modules.audit.service import record as record_audit
from app.modules.connections.models import Connection
from app.modules.domain_events import service as domain_events_service
from app.modules.files.models import File
from app.modules.identity.models import Session, User, UserStatus
from app.modules.identity.security import hash_password_async, verify_password_async
from app.modules.memberships.models import Membership, MembershipStatus
from app.modules.memberships.role_changes import lock_super_admins_and_check_one_remains
from app.modules.moderation.models import Report
from app.modules.organizations.models import Organization

EXPORT_LIMIT_PER_HOUR = 3
DELETE_LIMIT = 5
DELETE_WINDOW_SECONDS = 900


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


async def export_my_data(db: AsyncSession, *, user: User) -> dict[str, Any]:
    """
    Everything we hold about this one person, as plain data. Left out on purpose: the password
    hash, tokens, internal storage keys, and anything that belongs to someone else (other
    people's names, emails or profiles; only their anonymous ids appear, so connections can be
    listed).
    """
    from app.modules.bookings.service import export_bookings

    await hit(f"ratelimit:data_export:{user.id}", limit=EXPORT_LIMIT_PER_HOUR, window_seconds=3600)

    profile = await db.scalar(select(AlumniProfile).where(AlumniProfile.user_id == user.id))
    profile_data: dict[str, Any] | None = None
    if profile is not None:
        school_name = None
        if profile.school_id is not None:
            school = await db.get(Organization, profile.school_id)
            school_name = school.name if school is not None else None
        skills = list(
            await db.scalars(
                select(Skill.name)
                .join(AlumniSkill, AlumniSkill.skill_id == Skill.id)
                .where(AlumniSkill.alumni_profile_id == profile.id)
                .order_by(Skill.name)
            )
        )
        interests = list(
            await db.scalars(
                select(Interest.name)
                .join(AlumniInterest, AlumniInterest.interest_id == Interest.id)
                .where(AlumniInterest.alumni_profile_id == profile.id)
                .order_by(Interest.name)
            )
        )
        vouches_given = list(
            await db.scalars(
                select(PeerVouch.vouched_user_id).where(PeerVouch.voucher_user_id == user.id)
            )
        )
        vouches_received = list(
            await db.scalars(
                select(PeerVouch.voucher_user_id).where(PeerVouch.vouched_user_id == user.id)
            )
        )
        profile_data = {
            "id": str(profile.id),
            "full_name": profile.full_name,
            "bio": profile.bio,
            "graduation_year": profile.graduation_year,
            "school_id": str(profile.school_id) if profile.school_id else None,
            "school_name": school_name,
            "country": profile.country,
            "profession": profile.profession,
            "company": profile.company,
            "profile_visibility": profile.profile_visibility.value,
            "verification_status": profile.verification_status.value,
            "verification_method": (
                profile.verification_method.value if profile.verification_method else None
            ),
            "avatar_file_id": str(profile.avatar_file_id) if profile.avatar_file_id else None,
            "created_at": _iso(profile.created_at),
            "skills": skills,
            "interests": interests,
            "vouched_for_user_ids": [str(v) for v in vouches_given],
            "vouched_by_user_ids": [str(v) for v in vouches_received],
        }

    memberships = (
        await db.execute(
            select(Membership, Organization.name)
            .outerjoin(Organization, Organization.id == Membership.organization_id)
            .where(Membership.user_id == user.id)
            .order_by(Membership.created_at)
        )
    ).all()
    connections = list(
        await db.scalars(
            select(Connection)
            .where(or_(Connection.requester_id == user.id, Connection.addressee_id == user.id))
            .order_by(Connection.created_at)
        )
    )
    sessions = list(
        await db.scalars(
            select(Session)
            .where(Session.user_id == user.id, Session.revoked_at.is_(None))
            .order_by(Session.created_at)
        )
    )
    files = list(
        await db.scalars(
            select(File).where(File.owner_user_id == user.id).order_by(File.created_at)
        )
    )
    reports = list(
        await db.scalars(
            select(Report).where(Report.reporter_user_id == user.id).order_by(Report.created_at)
        )
    )
    activity = list(
        await db.scalars(
            select(AuditLogEntry)
            .where(AuditLogEntry.actor_user_id == user.id)
            .order_by(AuditLogEntry.created_at)
        )
    )

    return {
        "exported_at": datetime.now(UTC).isoformat(),
        "account": {
            "id": str(user.id),
            "email": user.email,
            "status": user.status.value,
            "email_verified_at": _iso(user.email_verified_at),
            "age_confirmed_at": _iso(user.age_confirmed_at),
            "created_at": _iso(user.created_at),
        },
        "profile": profile_data,
        "roles": [
            {
                "role": m.role.value,
                "organization_id": str(m.organization_id) if m.organization_id else None,
                "organization_name": org_name,
                "status": m.status.value,
                "since": _iso(m.created_at),
            }
            for m, org_name in memberships
        ],
        "connections": [
            {
                "id": str(c.id),
                "direction": "sent" if c.requester_id == user.id else "received",
                "other_user_id": str(
                    c.addressee_id if c.requester_id == user.id else c.requester_id
                ),
                "status": c.status.value,
                "since": _iso(c.created_at),
            }
            for c in connections
        ],
        "event_bookings": await export_bookings(db, user=user),
        "signed_in_devices": [
            {
                "device": s.device_label,
                "ip_address": s.ip_address,
                "signed_in_at": _iso(s.created_at),
                "last_used_at": _iso(s.last_used_at),
            }
            for s in sessions
        ],
        "uploaded_files": [
            {
                "id": str(f.id),
                "purpose": f.purpose.value,
                "type": f.mime_type,
                "size_bytes": f.size_bytes,
                "width": f.width,
                "height": f.height,
                "uploaded_at": _iso(f.created_at),
            }
            for f in files
        ],
        "reports_you_filed": [
            {
                "id": str(r.id),
                "about": r.target_type.value,
                "reason": r.reason,
                "status": r.status.value,
                "filed_at": _iso(r.created_at),
            }
            for r in reports
        ],
        "your_activity": [
            {"action": a.action, "about": a.target_type, "at": _iso(a.created_at)} for a in activity
        ],
    }


async def delete_account(db: AsyncSession, *, user: User, password: str) -> list[str]:
    """
    Anonymizes the account (see the module docstring). Returns the storage keys of the files
    that were deleted; the caller removes those bytes AFTER the commit.
    """
    await hit(
        f"ratelimit:account_delete:{user.id}",
        limit=DELETE_LIMIT,
        window_seconds=DELETE_WINDOW_SECONDS,
    )
    if not await verify_password_async(password, user.password_hash):
        raise ValidationError("Your password is not correct.", code="invalid_current_password")

    # The platform must never be left without a super admin.
    if Role.SUPER_ADMIN in await get_user_roles(db, user_id=user.id):
        try:
            await lock_super_admins_and_check_one_remains(
                db, actor_id=user.id, target_user_id=user.id
            )
        except ConflictError:
            raise ConflictError(
                "You are the only super admin. Appoint another one before deleting your account."
            ) from None

    # Local import: bookings depends on events, which depend on identity.
    from app.modules.bookings.service import settle_bookings_for_deletion

    await settle_bookings_for_deletion(db, user=user)

    uid = user.id
    old_email = user.email
    now = datetime.now(UTC)

    # Personal files go (avatars). Files that belong to an organization, such as its logo,
    # stay, no longer owned by this person.
    own_files = list(
        await db.scalars(
            select(File).where(File.owner_user_id == uid, File.organization_id.is_(None))
        )
    )
    storage_keys = [f.storage_key for f in own_files]
    for f in own_files:
        await db.delete(f)
    await db.execute(update(File).where(File.owner_user_id == uid).values(owner_user_id=None))

    profile = await db.scalar(select(AlumniProfile).where(AlumniProfile.user_id == uid))
    if profile is not None:
        await db.execute(delete(AlumniSkill).where(AlumniSkill.alumni_profile_id == profile.id))
        await db.execute(
            delete(AlumniInterest).where(AlumniInterest.alumni_profile_id == profile.id)
        )
        profile.full_name = "Deleted user"
        profile.bio = None
        profile.graduation_year = None
        profile.school_id = None
        profile.country = None
        profile.profession = None
        profile.company = None
        profile.avatar_file_id = None
        profile.profile_visibility = ProfileVisibility.PRIVATE
        profile.verification_status = VerificationStatus.UNVERIFIED
        profile.verification_method = None
    await db.execute(
        delete(PeerVouch).where(
            or_(PeerVouch.vouched_user_id == uid, PeerVouch.voucher_user_id == uid)
        )
    )
    await db.execute(
        delete(Connection).where(
            or_(Connection.requester_id == uid, Connection.addressee_id == uid)
        )
    )
    await db.execute(
        update(Membership).where(Membership.user_id == uid).values(status=MembershipStatus.REVOKED)
    )
    await db.execute(
        update(Session)
        .where(Session.user_id == uid)
        .values(
            revoked_at=now,
            device_label=None,
            ip_address=None,
        )
    )

    user.email = f"deleted-{uid}@deleted.invalid"
    # Not a password anyone knows or could guess; the status below stops sign-in anyway.
    user.password_hash = await hash_password_async(secrets.token_urlsafe(32))
    user.email_verified_at = None
    user.age_confirmed_at = None
    user.security_stamp = uuid.uuid4()
    user.status = UserStatus.DELETED
    await db.flush()

    # The audit log keeps what happened but not to whom or by whom.
    await db.execute(
        update(AuditLogEntry).where(AuditLogEntry.actor_user_id == uid).values(actor_user_id=None)
    )
    await db.execute(
        update(AuditLogEntry)
        .where(AuditLogEntry.target_type == "user", AuditLogEntry.target_id == uid)
        .values(target_id=None)
    )
    await db.execute(
        text(
            "UPDATE audit_log SET metadata = (metadata - 'target_user_id') "
            "|| '{\"subject_deleted\": true}'::jsonb WHERE metadata->>'target_user_id' = :uid"
        ),
        {"uid": str(uid)},
    )
    # Queued emails about this person: unsent ones are pointless now, sent ones keep no id.
    await db.execute(
        text("DELETE FROM domain_events WHERE status = 'pending' AND payload->>'user_id' = :uid"),
        {"uid": str(uid)},
    )
    await db.execute(
        text("UPDATE domain_events SET payload = '{}'::jsonb WHERE payload->>'user_id' = :uid"),
        {"uid": str(uid)},
    )

    redis = get_redis_client()
    await redis.delete(f"login_fail:{old_email.lower()}", f"login_lockout:{old_email.lower()}")

    await record_audit(
        db,
        actor_user_id=None,
        action="user.delete",
        target_type="user",
        target_id=None,
        context={"self_service": True},
    )
    await domain_events_service.publish(
        db, event_type="email.account_deleted", payload={"email": old_email}
    )
    return storage_keys
