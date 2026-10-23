"""
Operator commands. Run inside the API container:

    docker compose exec api uv run python -m app.cli create-super-admin you@example.com
    docker compose exec api uv run python -m app.cli create-dev-account dev@example.com

create-super-admin is the only way to create the first administrator: there is
deliberately no public endpoint that can grant platform roles.

create-dev-account is for local development ONLY. It gives one email every role so a
developer can open every part of the app with a single login. It refuses to run
anywhere except ENVIRONMENT=development.
"""

import argparse
import asyncio
import getpass
import sys
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.permissions.roles import Role
from app.infrastructure.database import all_models  # noqa: F401  (registers every model)
from app.infrastructure.database.session import async_session_factory, engine
from app.modules.alumni.models import (
    AlumniProfile,
    ProfileVisibility,
    VerificationMethod,
    VerificationStatus,
)
from app.modules.identity.models import User
from app.modules.identity.security import hash_password
from app.modules.memberships.models import Membership, MembershipStatus
from app.modules.organizations.models import Organization, OrganizationStatus, OrganizationType

MIN_PASSWORD_LENGTH = 10


async def ensure_super_admin(
    db: AsyncSession, *, email: str, password: str | None
) -> tuple[User, bool]:
    """
    Returns (user, created). Creates the account if it doesn't exist (password
    required), then makes sure it holds an active platform-wide SUPER_ADMIN
    membership. Safe to run repeatedly.
    """
    email = email.strip().lower()
    user = await db.scalar(select(User).where(User.email == email))
    created = False
    if user is None:
        if password is None or len(password) < MIN_PASSWORD_LENGTH:
            raise ValueError(
                f"A password of at least {MIN_PASSWORD_LENGTH} characters is required."
            )
        user = User(
            email=email,
            password_hash=hash_password(password),
            age_confirmed_at=datetime.now(UTC),
        )
        db.add(user)
        await db.flush()
        created = True

    membership = await db.scalar(
        select(Membership).where(
            Membership.user_id == user.id,
            Membership.organization_id.is_(None),
            Membership.role == Role.SUPER_ADMIN,
        )
    )
    if membership is None:
        db.add(Membership(user_id=user.id, organization_id=None, role=Role.SUPER_ADMIN))
    elif membership.status != MembershipStatus.ACTIVE:
        membership.status = MembershipStatus.ACTIVE
    await db.flush()
    return user, created


# The two organizations the dev account is attached to. Fixed slugs, so running the command
# again reuses them instead of making copies.
DEV_SCHOOL_SLUG = "demo-school"
DEV_PARTNER_SLUG = "demo-partner"


async def _ensure_organization(
    db: AsyncSession, *, slug: str, name: str, org_type: OrganizationType, description: str
) -> Organization:
    org = await db.scalar(select(Organization).where(Organization.slug == slug))
    if org is None:
        org = Organization(
            type=org_type,
            name=name,
            slug=slug,
            description=description,
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
    elif membership.status != MembershipStatus.ACTIVE:
        membership.status = MembershipStatus.ACTIVE


async def ensure_dev_account(
    db: AsyncSession, *, email: str, password: str | None
) -> tuple[User, bool]:
    """
    One account that can open every part of the app, for local development.

    Holds super admin, admin and moderator (platform-wide), plus school admin, event manager
    and sports manager for a demo school, and partner admin for a demo partner. Also gets a
    verified email address and a verified alumni profile, so nothing nags and the member view
    works at once. Safe to run again.

    Note: this account has the UNION of every role's powers. It is for looking at the
    screens, not for testing what a limited role is blocked from doing. Use a separate
    account per role for that.
    """
    user, created = await ensure_super_admin(db, email=email, password=password)
    user.email_verified_at = user.email_verified_at or datetime.now(UTC)

    school = await _ensure_organization(
        db,
        slug=DEV_SCHOOL_SLUG,
        name="Demo High School",
        org_type=OrganizationType.SCHOOL,
        description="A demo school for development.",
    )
    partner = await _ensure_organization(
        db,
        slug=DEV_PARTNER_SLUG,
        name="Demo Partner Ltd",
        org_type=OrganizationType.PARTNER,
        description="A demo partner for development.",
    )

    for role in (Role.SUPER_ADMIN, Role.ADMIN, Role.MODERATOR):
        await _ensure_membership(db, user_id=user.id, role=role, organization_id=None)
    for role in (Role.SCHOOL_ADMIN, Role.EVENT_MANAGER, Role.SPORTS_MANAGER):
        await _ensure_membership(db, user_id=user.id, role=role, organization_id=school.id)
    await _ensure_membership(
        db, user_id=user.id, role=Role.PARTNER_ADMIN, organization_id=partner.id
    )

    has_profile = await db.scalar(select(AlumniProfile.id).where(AlumniProfile.user_id == user.id))
    if has_profile is None:
        db.add(
            AlumniProfile(
                user_id=user.id,
                full_name="Dev Account",
                school_id=school.id,
                graduation_year=2015,
                country="Kenya",
                profession="Software Engineer",
                company="Vancelle Tech Hub",
                bio="The development account. It can open every part of the app.",
                profile_visibility=ProfileVisibility.MEMBERS_ONLY,
                verification_status=VerificationStatus.VERIFIED,
                verification_method=VerificationMethod.ADMIN,
            )
        )
    await db.flush()
    return user, created


async def _create_super_admin(email: str) -> int:
    async with async_session_factory() as db:
        exists = await db.scalar(select(User.id).where(User.email == email.strip().lower()))
        password: str | None = None
        if exists is None:
            password = getpass.getpass("Password for the new account: ")
            if password != getpass.getpass("Repeat password: "):
                print("Passwords do not match.", file=sys.stderr)
                return 1
        try:
            user, created = await ensure_super_admin(db, email=email, password=password)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        await db.commit()
    print(f"{'Created' if created else 'Updated'} {user.email} as super admin.")
    return 0


async def _create_dev_account(email: str, password: str | None) -> int:
    if get_settings().environment != "development":
        print(
            "Refusing to run: create-dev-account only works when ENVIRONMENT=development.",
            file=sys.stderr,
        )
        return 1
    async with async_session_factory() as db:
        exists = await db.scalar(select(User.id).where(User.email == email.strip().lower()))
        if exists is None and password is None:
            password = getpass.getpass("Password for the new account: ")
            if password != getpass.getpass("Repeat password: "):
                print("Passwords do not match.", file=sys.stderr)
                return 1
        try:
            user, created = await ensure_dev_account(db, email=email, password=password)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        await db.commit()
    print(f"{'Created' if created else 'Updated'} {user.email} with every role:")
    print("  platform-wide: super_admin, admin, moderator")
    print(f"  school ({DEV_SCHOOL_SLUG}): school_admin, event_manager, sports_manager")
    print(f"  partner ({DEV_PARTNER_SLUG}): partner_admin")
    print("  member view: verified alumni profile")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    admin = sub.add_parser("create-super-admin", help="Create or promote a platform super admin")
    admin.add_argument("email")
    dev = sub.add_parser(
        "create-dev-account",
        help="Development only: one account holding every role, plus a demo school and partner",
    )
    dev.add_argument("email")
    dev.add_argument(
        "--password",
        help="Skip the prompt (development only, so the password may sit in your shell history)",
    )
    args = parser.parse_args()

    async def run() -> int:
        try:
            if args.command == "create-dev-account":
                return await _create_dev_account(args.email, args.password)
            return await _create_super_admin(args.email)
        finally:
            await engine.dispose()

    return asyncio.run(run())


if __name__ == "__main__":
    raise SystemExit(main())
