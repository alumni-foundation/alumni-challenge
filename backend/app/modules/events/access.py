"""
Who may see an event and who may run it. Everything that touches an event goes through here.

Seeing: a draft is visible only to the people who run it. A `members_only` event is invisible
(404) to anyone not signed in. Everything else published is public.

Running: the organization's event managers, sports managers, school or partner admins, and the
platform's admins. A platform event (no organization) is run by platform admins alone. Some
actions (publish, cancel, delete) need an admin level; managers create and edit drafts, close,
reopen and complete, and run check-in (design decision 14).

Hidden things answer 404, not 403, so a stranger cannot tell a draft from nothing.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors.exceptions import ForbiddenError, NotFoundError
from app.core.permissions.dependencies import get_user_roles
from app.core.permissions.roles import Role
from app.modules.events.models import Event, EventStatus, EventVisibility
from app.modules.identity.models import User

MANAGER_ROLES = frozenset(
    {
        Role.EVENT_MANAGER,
        Role.SPORTS_MANAGER,
        Role.SCHOOL_ADMIN,
        Role.PARTNER_ADMIN,
        Role.ADMIN,
        Role.SUPER_ADMIN,
    }
)
ADMIN_ROLES = frozenset({Role.SCHOOL_ADMIN, Role.PARTNER_ADMIN, Role.ADMIN, Role.SUPER_ADMIN})
PLATFORM_ADMIN_ROLES = frozenset({Role.ADMIN, Role.SUPER_ADMIN})


async def event_roles(
    db: AsyncSession, *, user: User | None, organization_id: uuid.UUID | None
) -> set[Role]:
    """The user's roles that apply to events of this organization (platform roles always do)."""
    if user is None:
        return set()
    return await get_user_roles(db, user_id=user.id, organization_id=organization_id)


def can_see(event: Event, *, signed_in: bool, is_manager: bool) -> bool:
    if is_manager:
        return True
    if event.status == EventStatus.DRAFT:
        return False
    return not (event.visibility == EventVisibility.MEMBERS_ONLY and not signed_in)


async def get_event_for_viewer(
    db: AsyncSession, *, event_id: uuid.UUID, viewer: User | None
) -> tuple[Event, set[Role]]:
    event = await db.get(Event, event_id)
    if event is None:
        raise NotFoundError("Event not found.")
    roles = await event_roles(db, user=viewer, organization_id=event.organization_id)
    if not can_see(event, signed_in=viewer is not None, is_manager=bool(roles & MANAGER_ROLES)):
        raise NotFoundError("Event not found.")
    return event, roles


async def get_event_for_manager(
    db: AsyncSession, *, event_id: uuid.UUID, user: User, admin_only: bool = False
) -> Event:
    """The event, if the caller may run it (admin level when `admin_only`).
    Not visible to the caller at all: 404. Visible but not theirs to run: 403."""
    event, roles = await get_event_for_viewer(db, event_id=event_id, viewer=user)
    needed = ADMIN_ROLES if admin_only else MANAGER_ROLES
    if not roles & needed:
        raise ForbiddenError("You do not have permission to manage this event.")
    return event
