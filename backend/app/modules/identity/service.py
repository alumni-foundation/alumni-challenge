import uuid
import uuid as uuid_module
from datetime import UTC, datetime, timedelta

import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors.exceptions import ConflictError, UnauthorizedError
from app.core.mail.base import Mailer
from app.infrastructure.redis import get_redis_client
from app.modules.identity.models import Session, User, UserStatus
from app.modules.identity.security import (
    create_access_token,
    create_purpose_token,
    decode_purpose_token,
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


# Failed-login lockout: after this many wrong passwords for one email
# within the window, further attempts are rejected outright for the
# lockout period — even a correct password won't get through until it
# expires. This does mean an attacker (or a mistaken user) learns "this
# account is temporarily locked" rather than the usual generic error;
# that's an intentional, standard trade-off (OWASP's guidance) — it costs
# a little account-enumeration resistance to stop unlimited password
# guessing, which matters more.
_LOCKOUT_THRESHOLD = 5
_LOCKOUT_WINDOW_SECONDS = 15 * 60


def _fail_key(email: str) -> str:
    return f"login_fail:{email.lower()}"


def _lockout_key(email: str) -> str:
    return f"login_lockout:{email.lower()}"


async def authenticate_user(db: AsyncSession, *, email: str, password: str) -> User:
    redis = get_redis_client()
    if await redis.exists(_lockout_key(email)):
        raise UnauthorizedError(
            "Too many failed attempts for this account. Try again in a few minutes."
        )

    user = await db.scalar(select(User).where(User.email == email))
    # Same generic message whether the email doesn't exist or the
    # password is wrong — do not let a client distinguish the two.
    if user is None or not verify_password(password, user.password_hash):
        fail_key = _fail_key(email)
        count = await redis.incr(fail_key)
        if count == 1:
            await redis.expire(fail_key, _LOCKOUT_WINDOW_SECONDS)
        if count >= _LOCKOUT_THRESHOLD:
            await redis.set(_lockout_key(email), "1", ex=_LOCKOUT_WINDOW_SECONDS)
        raise UnauthorizedError("Invalid email or password.")

    if user.status != UserStatus.ACTIVE:
        raise UnauthorizedError("This account is not active.")

    await redis.delete(_fail_key(email))
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


EMAIL_VERIFY_EXPIRE_MINUTES = 24 * 60
PASSWORD_RESET_EXPIRE_MINUTES = 30


async def request_email_verification(db: AsyncSession, *, user: User, mailer: Mailer) -> None:
    """
    Always succeeds from the caller's point of view even if already
    verified — resending a verification link to an already-verified
    address is harmless, and treating it as an error would leak state
    to a caller who otherwise has no way to know.
    """
    if user.email_verified_at is not None:
        return
    token = create_purpose_token(
        user.id, purpose="email_verify", expire_minutes=EMAIL_VERIFY_EXPIRE_MINUTES
    )
    link = f"{settings.frontend_url}/verify-email?token={token}"
    await mailer.send(
        to=user.email,
        subject="Verify your Alumni Challenge email",
        body=f"Confirm your email address: {link}\n\nThis link expires in 24 hours.",
    )


async def confirm_email_verification(db: AsyncSession, *, token: str) -> User:
    try:
        payload = decode_purpose_token(token, purpose="email_verify")
    except jwt.ExpiredSignatureError as exc:
        raise UnauthorizedError("This verification link has expired.") from exc
    except jwt.InvalidTokenError as exc:
        raise UnauthorizedError("This verification link is invalid.") from exc

    user = await db.get(User, uuid_module.UUID(payload["sub"]))
    if user is None:
        raise UnauthorizedError("This verification link is invalid.")
    if user.email_verified_at is None:
        user.email_verified_at = datetime.now(UTC)
        await db.flush()

        # Switches on email-domain auto-verify for any profile already
        # declaring this school — see alumni/service.py.
        from app.modules.alumni.service import verify_email_domain_for_user

        await verify_email_domain_for_user(db, user=user)
    return user


async def request_password_reset(db: AsyncSession, *, email: str, mailer: Mailer) -> None:
    """
    Always returns normally, whether or not the email is registered —
    the response must never reveal that. If it IS registered, an email
    goes out; if not, nothing happens and the caller can't tell.
    """
    user = await db.scalar(select(User).where(User.email == email))
    if user is None:
        return
    token = create_purpose_token(
        user.id,
        purpose="password_reset",
        expire_minutes=PASSWORD_RESET_EXPIRE_MINUTES,
        extra={"stamp": str(user.security_stamp)},
    )
    link = f"{settings.frontend_url}/reset-password?token={token}"
    await mailer.send(
        to=user.email,
        subject="Reset your Alumni Challenge password",
        body=(
            f"Reset your password: {link}\n\n"
            "This link expires in 30 minutes and can only be used once."
        ),
    )


async def reset_password(db: AsyncSession, *, token: str, new_password: str) -> None:
    try:
        payload = decode_purpose_token(token, purpose="password_reset")
    except jwt.ExpiredSignatureError as exc:
        raise UnauthorizedError("This reset link has expired.") from exc
    except jwt.InvalidTokenError as exc:
        raise UnauthorizedError("This reset link is invalid.") from exc

    user = await db.get(User, uuid_module.UUID(payload["sub"]))
    # The stamp check is what makes the link single-use: resetting the
    # password rotates the stamp below, so a second attempt with the
    # same (or any other outstanding) token no longer matches.
    if user is None or payload.get("stamp") != str(user.security_stamp):
        raise UnauthorizedError("This reset link is invalid or has already been used.")

    user.password_hash = hash_password(new_password)
    user.security_stamp = uuid_module.uuid4()
    await db.flush()
    # A stolen or guessed-then-reset password shouldn't leave old
    # sessions valid — force every device to sign in again.
    await _revoke_all_sessions(db, user_id=user.id)

    from app.modules.audit.service import record as record_audit

    await record_audit(
        db,
        actor_user_id=user.id,
        action="user.password_reset",
        target_type="user",
        target_id=user.id,
    )
