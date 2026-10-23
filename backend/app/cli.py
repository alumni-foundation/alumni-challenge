"""
Operator commands. Run inside the API container:

    docker compose exec api uv run python -m app.cli create-super-admin you@example.com
    docker compose exec api uv run python -m app.cli seed-demo

create-super-admin is the only way to create the first administrator: there is
deliberately no public endpoint that can grant platform roles.

seed-demo is for local development ONLY. It creates demo schools and partners, one account
per role (each with its own email) and sample alumni, and prints one random password, once.
It refuses to run anywhere except ENVIRONMENT=development.
"""

import argparse
import asyncio
import getpass
import secrets
import sys
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.permissions.roles import Role
from app.infrastructure.database import all_models  # noqa: F401  (registers every model)
from app.infrastructure.database.session import async_session_factory, engine
from app.modules.identity.models import User
from app.modules.identity.security import hash_password
from app.modules.memberships.models import Membership, MembershipStatus
from app.seed.demo import seed_demo

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


async def _seed_demo(*, reset_passwords: bool) -> int:
    if get_settings().environment != "development":
        print(
            "Refusing to run: seed-demo only works when ENVIRONMENT=development.",
            file=sys.stderr,
        )
        return 1
    password = secrets.token_urlsafe(12)
    async with async_session_factory() as db:
        result = await seed_demo(db, password=password, reset_passwords=reset_passwords)
        await db.commit()
    print(f"Demo data ready: {len(result.accounts)} accounts ({result.created_users} new).")
    if result.password_set_for:
        print("\nThe password below is shown once and is not stored anywhere:")
        print(f"  password: {password}")
        print("  applies to:")
        for acct in result.accounts:
            if acct.email in result.password_set_for:
                print(f"    {acct.email:<42} {acct.description}")
    kept = [a for a in result.accounts if a.email not in result.password_set_for]
    if kept:
        print(f"\n{len(kept)} existing accounts kept their password.")
        print("Run `seed-demo --reset-passwords` to give every demo account a new one.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    admin = sub.add_parser("create-super-admin", help="Create or promote a platform super admin")
    admin.add_argument("email")
    demo = sub.add_parser(
        "seed-demo",
        help="Development only: demo schools, partners, one account per role, and sample alumni",
    )
    demo.add_argument(
        "--reset-passwords",
        action="store_true",
        help="Give every existing demo account a new password (printed once)",
    )
    args = parser.parse_args()

    async def run() -> int:
        try:
            if args.command == "seed-demo":
                return await _seed_demo(reset_passwords=args.reset_passwords)
            return await _create_super_admin(args.email)
        finally:
            await engine.dispose()

    return asyncio.run(run())


if __name__ == "__main__":
    raise SystemExit(main())
