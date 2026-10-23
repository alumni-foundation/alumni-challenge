import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors.exceptions import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ValidationError,
)
from app.core.permissions.dependencies import get_user_roles
from app.core.permissions.roles import rank_of
from app.modules.audit import service as audit_service
from app.modules.identity.models import User, UserStatus
from app.modules.identity.service import _revoke_all_sessions

# Who may act on whom: you can only change the status of an account ranked strictly below
# you, so a moderator cannot touch another moderator or an admin, an admin cannot touch
# another admin, and nobody can touch a super admin through the API (that stays a
# command-line job). The ranking itself lives in core.permissions.roles.
_rank = rank_of


async def _load_target(
    db: AsyncSession, *, actor_id: uuid.UUID, target_user_id: uuid.UUID, reason: str
) -> tuple[User, str]:
    reason = reason.strip()
    if not reason:
        raise ValidationError("A reason is required.")
    if actor_id == target_user_id:
        raise ValidationError("You cannot change the status of your own account.")

    target = await db.get(User, target_user_id)
    if target is None:
        raise NotFoundError("User not found.")

    actor_rank = _rank(await get_user_roles(db, user_id=actor_id))
    target_rank = _rank(await get_user_roles(db, user_id=target.id))
    if actor_rank <= target_rank:
        raise ForbiddenError("You cannot change the status of an account at or above your level.")
    return target, reason


async def suspend_user(
    db: AsyncSession, *, actor_id: uuid.UUID, target_user_id: uuid.UUID, reason: str
) -> User:
    target, reason = await _load_target(
        db, actor_id=actor_id, target_user_id=target_user_id, reason=reason
    )
    if target.status == UserStatus.DELETED:
        raise ConflictError("This account has been deleted.")
    if target.status == UserStatus.SUSPENDED:
        raise ConflictError("This account is already suspended.")

    target.status = UserStatus.SUSPENDED
    # Access tokens stop working at once because every request re-checks the account status.
    # Revoking the sessions also kills the refresh tokens, and they stay dead if the account
    # is reactivated later: the person has to log in again.
    await _revoke_all_sessions(db, user_id=target.id)
    await db.flush()

    await audit_service.record(
        db,
        actor_user_id=actor_id,
        action="user.suspend",
        target_type="user",
        target_id=target.id,
        context={"reason": reason},
    )
    return target


async def reactivate_user(
    db: AsyncSession, *, actor_id: uuid.UUID, target_user_id: uuid.UUID, reason: str
) -> User:
    target, reason = await _load_target(
        db, actor_id=actor_id, target_user_id=target_user_id, reason=reason
    )
    if target.status != UserStatus.SUSPENDED:
        raise ConflictError("Only a suspended account can be reactivated.")

    target.status = UserStatus.ACTIVE
    await db.flush()

    await audit_service.record(
        db,
        actor_user_id=actor_id,
        action="user.reactivate",
        target_type="user",
        target_id=target.id,
        context={"reason": reason},
    )
    return target
