import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors.exceptions import ConflictError, UnauthorizedError
from app.modules.identity.models import Session, User, UserStatus
from app.modules.identity.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)

settings = get_settings()


async def register_user(db: AsyncSession, *, email: str, password: str) -> User:
    existing = await db.scalar(select(User).where(User.email == email))
    if existing is not None:
        # Deliberately vague — do not reveal whether an email is already
        # registered. Prevents account enumeration.
        raise ConflictError("Unable to register with the provided details.")

    user = User(
        email=email,
        password_hash=hash_password(password),
        age_confirmed_at=datetime.now(UTC),
    )
    db.add(user)
    await db.flush()
    return user


async def authenticate_user(db: AsyncSession, *, email: str, password: str) -> User:
    user = await db.scalar(select(User).where(User.email == email))
    # Same generic message whether the email doesn't exist or the
    # password is wrong — do not let a client distinguish the two.
    if user is None or not verify_password(password, user.password_hash):
        raise UnauthorizedError("Invalid email or password.")
    if user.status != UserStatus.ACTIVE:
        raise UnauthorizedError("This account is not active.")
    return user


async def issue_token_pair(
    db: AsyncSession,
    *,
    user: User,
    device_label: str | None = None,
    ip_address: str | None = None,
) -> tuple[str, str]:
    """Creates a new session (refresh token) and a fresh access token."""
    refresh_token = generate_refresh_token()
    session = Session(
        user_id=user.id,
        refresh_token_hash=hash_refresh_token(refresh_token),
        device_label=device_label,
        ip_address=ip_address,
    )
    db.add(session)
    await db.flush()

    access_token = create_access_token(user.id)
    return access_token, refresh_token


async def refresh_token_pair(db: AsyncSession, *, refresh_token: str) -> tuple[str, str]:
    """
    Rotates the refresh token: the old one is revoked and a new one
    issued on every use. Reusing an already-revoked refresh token
    revokes the entire session chain — a signal the token was stolen.
    """
    token_hash = hash_refresh_token(refresh_token)
    session = await db.scalar(select(Session).where(Session.refresh_token_hash == token_hash))

    if session is None:
        raise UnauthorizedError("Invalid refresh token.")

    if not session.is_active:
        # Reuse of a revoked token — treat as compromised and kill every
        # active session for this user, not just this one.
        await _revoke_all_sessions(db, user_id=session.user_id)
        raise UnauthorizedError("This session has been revoked.")

    expires_at = session.created_at + timedelta(days=settings.refresh_token_expire_days)
    if datetime.now(UTC) > expires_at:
        session.revoked_at = datetime.now(UTC)
        await db.flush()
        raise UnauthorizedError("Session has expired, please log in again.")

    user = await db.get(User, session.user_id)
    if user is None or user.status != UserStatus.ACTIVE:
        raise UnauthorizedError("This account is not active.")

    # Rotate: revoke the used token, issue a new session.
    session.revoked_at = datetime.now(UTC)
    session.last_used_at = datetime.now(UTC)
    await db.flush()

    return await issue_token_pair(
        db, user=user, device_label=session.device_label, ip_address=session.ip_address
    )


async def revoke_session(db: AsyncSession, *, user_id: uuid.UUID, session_id: uuid.UUID) -> None:
    session = await db.get(Session, session_id)
    if session is None or session.user_id != user_id:
        # Same 404-shaped response whether it doesn't exist or belongs
        # to someone else — never confirm existence of another user's data.
        from app.core.errors.exceptions import NotFoundError

        raise NotFoundError("Session not found.")
    session.revoked_at = datetime.now(UTC)
    await db.flush()


async def revoke_session_by_token(db: AsyncSession, *, refresh_token: str) -> None:
    """Used by logout — revokes by the token itself, no user_id ownership check needed."""
    token_hash = hash_refresh_token(refresh_token)
    session = await db.scalar(select(Session).where(Session.refresh_token_hash == token_hash))
    if session is not None:
        session.revoked_at = datetime.now(UTC)
        await db.flush()


async def _revoke_all_sessions(db: AsyncSession, *, user_id: uuid.UUID) -> None:
    sessions = (
        await db.scalars(
            select(Session).where(Session.user_id == user_id, Session.revoked_at.is_(None))
        )
    ).all()
    now = datetime.now(UTC)
    for s in sessions:
        s.revoked_at = now
    await db.flush()


async def list_active_sessions(db: AsyncSession, *, user_id: uuid.UUID) -> list[Session]:
    result = await db.scalars(
        select(Session)
        .where(Session.user_id == user_id, Session.revoked_at.is_(None))
        .order_by(Session.last_used_at.desc())
    )
    return list(result.all())
