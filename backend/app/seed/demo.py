"""
Demo data for local development: one account per role, a few schools and partners,
about 40 alumni with mixed privacy and verification, some connections and reports.

Everything here is invented. Accounts use addresses under example.com, which is reserved
for documentation and cannot receive mail. Nothing in this module holds a password: the
caller supplies one, uses it, and shows it to the developer once.

Running it again changes nothing that already exists. Demo events live in demo_events.py.
"""

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions.roles import Role
from app.modules.alumni.models import (
    AlumniProfile,
    ProfileVisibility,
    SchoolEmailDomain,
    VerificationMethod,
    VerificationStatus,
)
from app.modules.connections.models import Connection, ConnectionStatus
from app.modules.identity.models import User
from app.modules.identity.security import hash_password
from app.modules.memberships.models import Membership, MembershipStatus
from app.modules.moderation.models import Report, ReportStatus, ReportTargetType
from app.modules.organizations.models import Organization, OrganizationStatus, OrganizationType
from app.seed.demo_events import ensure_demo_events

DEMO_EMAIL_DOMAIN = "example.com"
DEMO_EMAIL_PREFIX = "demo."

SCHOOLS = [
    ("demo-school-a", "Demo School A"),
    ("demo-school-b", "Demo School B"),
    ("demo-school-c", "Demo School C"),
]
PARTNERS = [
    ("demo-partner-1", "Demo Partner One"),
    ("demo-partner-2", "Demo Partner Two"),
]

ALUMNI_COUNT = 40

_FIRST_NAMES = [
    "Amani", "Baraka", "Chebet", "Dalila", "Eshe", "Faraji", "Gathoni", "Halima", "Imani",
    "Jabari", "Kamau", "Lulu", "Mwende", "Njeri", "Omari", "Pendo", "Rehema", "Sefu",
    "Tabu", "Wanjiru",
]  # fmt: skip
_LAST_NAMES = ["Test", "Sample", "Example", "Demo"]
_PROFESSIONS = ["Engineer", "Teacher", "Accountant", "Doctor", "Farmer", "Designer", "Lawyer"]
_COMPANIES = ["Acme Demo Ltd", "Sample Works", "Example & Co", "Placeholder Group"]
_COUNTRIES = ["Kenya", "Kenya", "Kenya", "Uganda", "United Kingdom"]
_VISIBILITIES = [
    ProfileVisibility.MEMBERS_ONLY,
    ProfileVisibility.PUBLIC,
    ProfileVisibility.CONNECTIONS_ONLY,
    ProfileVisibility.PRIVATE,
]


def demo_email(*parts: str) -> str:
    return f"{DEMO_EMAIL_PREFIX}{'.'.join(parts)}@{DEMO_EMAIL_DOMAIN}"


@dataclass(frozen=True)
class DemoAccount:
    email: str
    description: str


@dataclass
class SeedResult:
    accounts: list[DemoAccount] = field(default_factory=list)
    # Accounts whose password was set by this run. Existing accounts keep the password they
    # already have unless the run was asked to reset passwords.
    password_set_for: set[str] = field(default_factory=set)
    created_users: int = 0


async def _ensure_org(
    db: AsyncSession, *, slug: str, name: str, org_type: OrganizationType
) -> Organization:
    org = await db.scalar(select(Organization).where(Organization.slug == slug))
    if org is None:
        org = Organization(
            type=org_type,
            name=name,
            slug=slug,
            description="Demo data for development.",
            status=OrganizationStatus.ACTIVE,
        )
        db.add(org)
        await db.flush()
    return org


async def _ensure_membership(
    db: AsyncSession, *, user_id: uuid.UUID, role: Role, organization_id: uuid.UUID | None
) -> None:
    stmt = select(Membership).where(Membership.user_id == user_id, Membership.role == role)
    if organization_id is None:
        stmt = stmt.where(Membership.organization_id.is_(None))
    else:
        stmt = stmt.where(Membership.organization_id == organization_id)
    membership = await db.scalar(stmt)
    if membership is None:
        db.add(Membership(user_id=user_id, organization_id=organization_id, role=role))
        await db.flush()
    elif membership.status != MembershipStatus.ACTIVE:
        membership.status = MembershipStatus.ACTIVE


async def _ensure_user(
    db: AsyncSession,
    *,
    email: str,
    password_hash: str,
    reset_password: bool,
    result: SeedResult,
) -> User:
    user = await db.scalar(select(User).where(User.email == email))
    if user is None:
        now = datetime.now(UTC)
        user = User(
            email=email,
            password_hash=password_hash,
            email_verified_at=now,
            age_confirmed_at=now,
        )
        db.add(user)
        await db.flush()
        result.created_users += 1
        result.password_set_for.add(email)
    elif reset_password:
        user.password_hash = password_hash
        user.security_stamp = uuid.uuid4()
        result.password_set_for.add(email)
    return user


async def _ensure_profile(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    full_name: str,
    school_id: uuid.UUID | None,
    graduation_year: int,
    visibility: ProfileVisibility,
    verification: tuple[VerificationStatus, VerificationMethod | None],
    index: int,
) -> AlumniProfile:
    profile = await db.scalar(select(AlumniProfile).where(AlumniProfile.user_id == user_id))
    if profile is None:
        status, method = verification
        profile = AlumniProfile(
            user_id=user_id,
            full_name=full_name,
            school_id=school_id,
            graduation_year=graduation_year,
            country=_COUNTRIES[index % len(_COUNTRIES)],
            profession=_PROFESSIONS[index % len(_PROFESSIONS)],
            company=_COMPANIES[index % len(_COMPANIES)],
            bio="Demo profile for development.",
            profile_visibility=visibility,
            verification_status=status,
            verification_method=method,
        )
        db.add(profile)
        await db.flush()
    return profile


def _signup_time(index: int) -> datetime:
    """A sign-up time within the last 60 days, different for each demo member, never in the
    future (at least an hour ago), so the dashboard's sign-up chart and "new members" look real."""
    days = (index * 7) % 60
    hours = 1 + (index * 5) % 23
    return datetime.now(UTC) - timedelta(days=days, hours=hours)


def _verification_for(index: int) -> tuple[VerificationStatus, VerificationMethod | None]:
    if index % 3 == 0:
        return VerificationStatus.VERIFIED, VerificationMethod.ADMIN
    if index % 5 == 0:
        return VerificationStatus.VERIFIED, VerificationMethod.EMAIL_DOMAIN
    return VerificationStatus.UNVERIFIED, None


async def _ensure_connection(
    db: AsyncSession,
    *,
    requester: uuid.UUID,
    addressee: uuid.UUID,
    status: ConnectionStatus,
) -> None:
    exists = await db.scalar(
        select(Connection.id).where(
            Connection.requester_id.in_((requester, addressee)),
            Connection.addressee_id.in_((requester, addressee)),
        )
    )
    if exists is None:
        db.add(
            Connection(
                requester_id=requester,
                addressee_id=addressee,
                status=status,
                blocked_by=requester if status == ConnectionStatus.BLOCKED else None,
            )
        )
        await db.flush()


async def _ensure_report(
    db: AsyncSession,
    *,
    reporter: uuid.UUID,
    target_profile_id: uuid.UUID,
    status: ReportStatus,
    reviewer: uuid.UUID | None,
) -> None:
    exists = await db.scalar(
        select(Report.id).where(
            Report.reporter_user_id == reporter, Report.target_id == target_profile_id
        )
    )
    if exists is None:
        db.add(
            Report(
                reporter_user_id=reporter,
                target_type=ReportTargetType.PROFILE,
                target_id=target_profile_id,
                reason="Demo report for development.",
                status=status,
                reviewed_by=reviewer,
            )
        )
        await db.flush()


async def seed_demo(
    db: AsyncSession, *, password: str, reset_passwords: bool = False
) -> SeedResult:
    result = SeedResult()
    # One hash for every demo account: same password, and hashing 60 times is slow.
    password_hash = hash_password(password)

    async def account(email: str, description: str) -> User:
        user = await _ensure_user(
            db,
            email=email,
            password_hash=password_hash,
            reset_password=reset_passwords,
            result=result,
        )
        result.accounts.append(DemoAccount(email=email, description=description))
        return user

    schools = [
        await _ensure_org(db, slug=slug, name=name, org_type=OrganizationType.SCHOOL)
        for slug, name in SCHOOLS
    ]
    partners = [
        await _ensure_org(db, slug=slug, name=name, org_type=OrganizationType.PARTNER)
        for slug, name in PARTNERS
    ]
    for school in schools:
        domain = f"{school.slug}.example.com"
        if await db.scalar(select(SchoolEmailDomain.id).where(SchoolEmailDomain.domain == domain)):
            continue
        db.add(SchoolEmailDomain(organization_id=school.id, domain=domain))
        await db.flush()

    # Platform-wide staff: one account per role.
    moderator: User | None = None
    for role in (Role.SUPER_ADMIN, Role.ADMIN, Role.MODERATOR):
        user = await account(demo_email(role.value.replace("_", "-")), f"{role.value} (platform)")
        await _ensure_membership(db, user_id=user.id, role=role, organization_id=None)
        if role == Role.MODERATOR:
            moderator = user
    assert moderator is not None

    # Organization staff: each one is scoped to exactly one organization.
    school_admins: list[User] = []
    for school, suffix in zip(schools, "abc", strict=True):
        user = await account(demo_email("school-admin", suffix), f"school_admin ({school.name})")
        await _ensure_membership(
            db, user_id=user.id, role=Role.SCHOOL_ADMIN, organization_id=school.id
        )
        school_admins.append(user)
    for index, partner in enumerate(partners, start=1):
        user = await account(
            demo_email("partner-admin", str(index)), f"partner_admin ({partner.name})"
        )
        await _ensure_membership(
            db, user_id=user.id, role=Role.PARTNER_ADMIN, organization_id=partner.id
        )
    manager = await account(demo_email("event-manager"), f"event_manager ({schools[0].name})")
    await _ensure_membership(
        db, user_id=manager.id, role=Role.EVENT_MANAGER, organization_id=schools[0].id
    )
    sports = await account(demo_email("sports-manager"), f"sports_manager ({schools[0].name})")
    await _ensure_membership(
        db, user_id=sports.id, role=Role.SPORTS_MANAGER, organization_id=schools[0].id
    )

    await ensure_demo_events(db, school=schools[0], manager=manager, admin=school_admins[0])

    # Ordinary alumni, spread across the schools, with every privacy level and a mix of
    # verified and unverified profiles.
    alumni: list[tuple[User, AlumniProfile]] = []
    for i in range(ALUMNI_COUNT):
        school = schools[i % len(schools)]
        user = await account(demo_email("alumni", f"{i + 1:02d}"), f"alumni ({school.name})")
        await _ensure_membership(db, user_id=user.id, role=Role.ALUMNI, organization_id=None)
        profile = await _ensure_profile(
            db,
            user_id=user.id,
            full_name=f"{_FIRST_NAMES[i % len(_FIRST_NAMES)]} {_LAST_NAMES[i % len(_LAST_NAMES)]}",
            school_id=school.id,
            graduation_year=2005 + (i % 18),
            visibility=_VISIBILITIES[i % len(_VISIBILITIES)],
            verification=_verification_for(i),
            index=i,
        )
        signed_up = _signup_time(i)
        user.created_at = profile.created_at = profile.updated_at = signed_up
        alumni.append((user, profile))

    # A little social graph: accepted, pending, declined and blocked connections.
    pairs = [
        (0, 1, ConnectionStatus.ACCEPTED),
        (0, 2, ConnectionStatus.ACCEPTED),
        (1, 2, ConnectionStatus.ACCEPTED),
        (3, 0, ConnectionStatus.PENDING),
        (4, 0, ConnectionStatus.DECLINED),
        (5, 6, ConnectionStatus.BLOCKED),
        (7, 8, ConnectionStatus.ACCEPTED),
    ]
    for a, b, status in pairs:
        await _ensure_connection(
            db, requester=alumni[a][0].id, addressee=alumni[b][0].id, status=status
        )

    # A few reports, so the moderation queue is not empty.
    await _ensure_report(
        db,
        reporter=alumni[10][0].id,
        target_profile_id=alumni[20][1].id,
        status=ReportStatus.OPEN,
        reviewer=None,
    )
    await _ensure_report(
        db,
        reporter=alumni[11][0].id,
        target_profile_id=alumni[21][1].id,
        status=ReportStatus.REVIEWING,
        reviewer=moderator.id,
    )
    await _ensure_report(
        db,
        reporter=alumni[12][0].id,
        target_profile_id=alumni[22][1].id,
        status=ReportStatus.OPEN,
        reviewer=None,
    )

    await db.flush()
    return result
