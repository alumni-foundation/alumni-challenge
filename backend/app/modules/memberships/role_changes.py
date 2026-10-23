"""
Granting and revoking roles.

Two kinds of role, two sets of rules:

Platform-wide roles (super_admin, admin, moderator) follow the rank rule. A super admin can
change any of them, another super admin's included. An admin can grant and revoke moderator,
but only for someone who ranks below admin. A moderator can change nothing. Nobody changes
their own roles, and the last super admin can never be revoked.

Roles tied to one organization (school_admin, partner_admin, event_manager, sports_manager)
follow the permission matrix in organizations.service.assign_membership: platform admins
appoint organization admins, and an organization's admin appoints its managers.

Every change is written to the audit log in the same transaction.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationError
from app.core.permissions.dependencies import get_user_roles
from app.core.permissions.roles import PLATFORM_WIDE_ROLES, ROLE_RANK, Role, rank_of
from app.modules.audit.service import record as record_audit
from app.modules.identity.models import User, UserStatus
from app.modules.memberships.models import Membership, MembershipStatus
from app.modules.organizations.models import Organization, OrganizationStatus, OrganizationType

_PLATFORM_ADMINS = {Role.ADMIN, Role.SUPER_ADMIN}
_ORG_ADMIN_ROLES = (Role.SCHOOL_ADMIN, Role.PARTNER_ADMIN)
_ORG_MANAGER_ROLES = (Role.EVENT_MANAGER, Role.SPORTS_MANAGER)


def _may_change_platform_role(*, actor_rank: int, role: Role, target_rank: int) -> bool:
    if actor_rank == ROLE_RANK[Role.SUPER_ADMIN]:
        return True
    return actor_rank > ROLE_RANK[role] and actor_rank > target_rank


async def _active_platform_membership(
    db: AsyncSession, *, user_id: uuid.UUID, role: Role
) -> Membership | None:
    return await db.scalar(
        select(Membership).where(
            Membership.user_id == user_id,
            Membership.role == role,
            Membership.organization_id.is_(None),
            Membership.status == MembershipStatus.ACTIVE,
        )
    )


async def grant_platform_role(
    db: AsyncSession, *, actor: User, target_user_id: uuid.UUID, role: Role
) -> Membership:
    if role not in PLATFORM_WIDE_ROLES:
        raise ValidationError("This is not a platform-wide role.")
    if actor.id == target_user_id:
        raise ValidationError("You cannot change your own roles.")

    target = await db.get(User, target_user_id)
    if target is None or target.status != UserStatus.ACTIVE:
        raise NotFoundError("User not found.")

    actor_rank = rank_of(await get_user_roles(db, user_id=actor.id))
    target_rank = rank_of(await get_user_roles(db, user_id=target.id))
    if not _may_change_platform_role(actor_rank=actor_rank, role=role, target_rank=target_rank):
        raise ForbiddenError("You do not have permission to grant this role.")

    existing = await db.scalar(
        select(Membership).where(
            Membership.user_id == target_user_id,
            Membership.role == role,
            Membership.organization_id.is_(None),
        )
    )
    if existing is not None and existing.status == MembershipStatus.ACTIVE:
        raise ConflictError("This user already holds that role.")
    if existing is not None:
        existing.status = MembershipStatus.ACTIVE
        membership = existing
    else:
        membership = Membership(user_id=target_user_id, organization_id=None, role=role)
        db.add(membership)
    await db.flush()

    await record_audit(
        db,
        actor_user_id=actor.id,
        action="membership.assign",
        target_type="membership",
        target_id=membership.id,
        context={"role": role.value, "target_user_id": str(target_user_id), "scope": "platform"},
    )
    return membership


async def revoke_platform_role(
    db: AsyncSession, *, actor: User, target_user_id: uuid.UUID, role: Role
) -> Membership:
    if role not in PLATFORM_WIDE_ROLES:
        raise ValidationError("This is not a platform-wide role.")
    if actor.id == target_user_id:
        raise ValidationError("You cannot change your own roles.")

    actor_rank = rank_of(await get_user_roles(db, user_id=actor.id))
    target_rank = rank_of(await get_user_roles(db, user_id=target_user_id))
    if not _may_change_platform_role(actor_rank=actor_rank, role=role, target_rank=target_rank):
        raise ForbiddenError("You do not have permission to revoke this role.")

    if role == Role.SUPER_ADMIN:
        await _lock_super_admins_and_check_one_remains(
            db, actor_id=actor.id, target_user_id=target_user_id
        )

    membership = await _active_platform_membership(db, user_id=target_user_id, role=role)
    if membership is None:
        raise NotFoundError("This user does not hold that role.")
    membership.status = MembershipStatus.REVOKED
    await db.flush()

    await record_audit(
        db,
        actor_user_id=actor.id,
        action="membership.revoke",
        target_type="membership",
        target_id=membership.id,
        context={"role": role.value, "target_user_id": str(target_user_id), "scope": "platform"},
    )
    return membership


async def _lock_super_admins_and_check_one_remains(
    db: AsyncSession, *, actor_id: uuid.UUID, target_user_id: uuid.UUID
) -> None:
    """
    Two super admins revoking each other at the same moment must not leave the platform with
    none. Every active super_admin row is locked (always in the same order, so two callers
    cannot deadlock) before anything is decided, and the caller's own standing is checked
    again under the lock: whoever goes second finds their own role already gone.
    """
    holders = {
        m.user_id
        for m in await db.scalars(
            select(Membership)
            .where(
                Membership.role == Role.SUPER_ADMIN,
                Membership.organization_id.is_(None),
                Membership.status == MembershipStatus.ACTIVE,
            )
            .order_by(Membership.id)
            .with_for_update()
        )
    }
    if actor_id not in holders:
        raise ForbiddenError("You do not have permission to revoke this role.")
    if target_user_id not in holders:
        raise NotFoundError("This user does not hold that role.")
    if not holders - {target_user_id}:
        raise ConflictError("The last super admin cannot be revoked.")


async def revoke_organization_membership(
    db: AsyncSession, *, actor: User, organization_id: uuid.UUID, membership_id: uuid.UUID
) -> Membership:
    org = await db.get(Organization, organization_id)
    if org is None or org.status != OrganizationStatus.ACTIVE:
        raise NotFoundError("Organization not found.")

    # Looked up by organization too, so a membership id from another organization is simply
    # "not found" here, never a hint that it exists.
    membership = await db.scalar(
        select(Membership).where(
            Membership.id == membership_id,
            Membership.organization_id == organization_id,
            Membership.status == MembershipStatus.ACTIVE,
        )
    )
    if membership is None:
        raise NotFoundError("Membership not found.")
    if membership.user_id == actor.id:
        raise ValidationError("You cannot change your own roles.")

    actor_roles = await get_user_roles(db, user_id=actor.id, organization_id=organization_id)
    role = membership.role
    if role in _ORG_ADMIN_ROLES:
        if not actor_roles & _PLATFORM_ADMINS:
            raise ForbiddenError("Only platform administrators can remove organization admins.")
    elif role in _ORG_MANAGER_ROLES:
        org_admin = Role.SCHOOL_ADMIN if org.type == OrganizationType.SCHOOL else Role.PARTNER_ADMIN
        if not actor_roles & (_PLATFORM_ADMINS | {org_admin}):
            raise ForbiddenError("You do not have permission to remove this role.")
    else:
        raise ValidationError("This role cannot be removed from an organization.")

    membership.status = MembershipStatus.REVOKED
    await db.flush()

    await record_audit(
        db,
        actor_user_id=actor.id,
        action="membership.revoke",
        target_type="membership",
        target_id=membership.id,
        context={
            "organization_id": str(organization_id),
            "role": role.value,
            "target_user_id": str(membership.user_id),
            "scope": "organization",
        },
    )
    return membership
