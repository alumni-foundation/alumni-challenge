"""
Operator commands. Run inside the API container:

    docker compose exec api uv run python -m app.cli create-super-admin you@example.com

This is the only way to create the first administrator: there is deliberately
no public endpoint that can grant platform roles.
"""

import argparse
import asyncio
import getpass
import sys
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions.roles import Role
from app.infrastructure.database import all_models  # noqa: F401  (registers every model)
from app.infrastructure.database.session import async_session_factory, engine
from app.modules.identity.models import User
from app.modules.identity.security import hash_password
from app.modules.memberships.models import Membership, MembershipStatus

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


def main() -> int:
    parser = argparse.ArgumentParser(prog="app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    admin = sub.add_parser("create-super-admin", help="Create or promote a platform super admin")
    admin.add_argument("email")
    args = parser.parse_args()

    async def run() -> int:
        try:
            return await _create_super_admin(args.email)
        finally:
            await engine.dispose()

    return asyncio.run(run())


if __name__ == "__main__":
    raise SystemExit(main())
