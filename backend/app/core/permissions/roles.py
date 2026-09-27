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
