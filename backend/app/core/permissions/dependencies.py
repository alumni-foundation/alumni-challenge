import uuid
from collections.abc import Callable, Coroutine
from typing import Any

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors.exceptions import ForbiddenError
from app.core.permissions.roles import PLATFORM_WIDE_ROLES, Role
from app.infrastructure.database.session import get_db_session
from app.modules.identity.dependencies import get_current_user
from app.modules.identity.models import User
from app.modules.memberships.models import Membership, MembershipStatus


async def get_user_roles(
    db: AsyncSession, *, user_id: uuid.UUID, organization_id: uuid.UUID | None = None
) -> set[Role]:
    """
    Returns every active role this user holds that applies to the given
    scope: platform-wide roles always apply, org-scoped roles apply
    only when organization_id matches. This is the ONLY function that
    should decide "does this user have role X for org Y" — every
    endpoint's authorization goes through here, never a hand-rolled check.
    """
    stmt = select(Membership.role, Membership.organization_id).where(
        Membership.user_id == user_id, Membership.status == MembershipStatus.ACTIVE
    )
    rows = (await db.execute(stmt)).all()

    roles: set[Role] = set()
    for role, org_id in rows:
        if role in PLATFORM_WIDE_ROLES or (
            organization_id is not None and org_id == organization_id
        ):
            roles.add(role)
    return roles


def require_roles(
    *allowed_roles: Role,
) -> Callable[..., Coroutine[Any, Any, User]]:
    """
    Dependency factory for ROLE_PROTECTED endpoints. Usage:

        @router.patch("/organizations/{org_id}")
        async def update_org(
            org_id: uuid.UUID,
            user: User = Depends(require_roles(Role.SCHOOL_ADMIN, Role.ADMIN)),
        ):
            ...

    NOTE: this checks whether the user holds one of the allowed roles
    ANYWHERE (platform-wide roles) or the endpoint must separately pass
    the relevant organization_id via require_roles_for_org below for
    org-scoped checks. Using this alone for an org-scoped action is a
    bug — see require_roles_for_org.
    """

    async def _check(
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db_session),
    ) -> User:
        user_roles = await get_user_roles(db, user_id=current_user.id)
        if not user_roles.intersection(allowed_roles):
            raise ForbiddenError("You do not have permission to perform this action.")
        return current_user

    return _check


def require_roles_for_org(
    *allowed_roles: Role,
    org_id_param: str = "organization_id",
) -> Callable[..., Coroutine[Any, Any, User]]:
    """
    Dependency factory for actions scoped to one organization — e.g.
    school_admin editing their own school. Reads the organization id
    out of the request's resolved path parameters (via Starlette's
    Request, which FastAPI always populates regardless of the route's
    declared signature), so the route just needs a path param named
    org_id_param. Platform-wide roles (admin, super_admin) always pass
    regardless of organization.

    This is the enforcement point for the Phase 3 gate test case:
    "School A admin cannot touch School B" — because a school_admin's
    role only resolves as active for the organization_id on their own
    membership row, never for a different one.
    """

    async def _check(
        request: Request,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db_session),
    ) -> User:
        raw_org_id = request.path_params.get(org_id_param)
        if raw_org_id is None:
            raise ForbiddenError("Organization scope could not be determined.")

        try:
            org_id = uuid.UUID(str(raw_org_id))
        except ValueError as exc:
            raise ForbiddenError("Organization scope could not be determined.") from exc

        user_roles = await get_user_roles(db, user_id=current_user.id, organization_id=org_id)
        if not user_roles.intersection(allowed_roles):
            raise ForbiddenError("You do not have permission to perform this action.")
        return current_user

    return _check
