import enum


class Role(enum.StrEnum):
    """
    Matches MEMBERSHIPS.role in the Phase 0 ERD. super_admin and admin
    are platform-wide (organization_id is null on their membership row);
    every other role is scoped to one organization.
    """

    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    MODERATOR = "moderator"
    SCHOOL_ADMIN = "school_admin"
    PARTNER_ADMIN = "partner_admin"
    EVENT_MANAGER = "event_manager"
    SPORTS_MANAGER = "sports_manager"
    ALUMNI = "alumni"


PLATFORM_WIDE_ROLES = {Role.SUPER_ADMIN, Role.ADMIN, Role.MODERATOR}


# Who outranks whom, for actions on other people's accounts and platform roles. Only the
# platform-wide roles rank; roles tied to one school or partner count as 0. This is the one
# place the ranking is written down.
ROLE_RANK = {Role.SUPER_ADMIN: 3, Role.ADMIN: 2, Role.MODERATOR: 1}


def rank_of(roles: set[Role]) -> int:
    return max((ROLE_RANK.get(role, 0) for role in roles), default=0)
