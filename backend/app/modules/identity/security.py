import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.core.config import get_settings

settings = get_settings()
_hasher = PasswordHasher()


def hash_password(plain_password: str) -> str:
    return _hasher.hash(plain_password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, plain_password)
    except VerifyMismatchError:
        return False


def needs_rehash(password_hash: str) -> bool:
    """Argon2 parameters can be tuned over time; rehash on next login if stale."""
    return _hasher.check_needs_rehash(password_hash)


def create_access_token(user_id: uuid.UUID) -> str:
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(
        payload, settings.secret_key.get_secret_value(), algorithm=settings.jwt_algorithm
    )


def decode_access_token(token: str) -> uuid.UUID:
    """Raises jwt exceptions on failure — caller maps them to UnauthorizedError."""
    payload = jwt.decode(
        token, settings.secret_key.get_secret_value(), algorithms=[settings.jwt_algorithm]
    )
    if payload.get("type") != "access":
        raise jwt.InvalidTokenError("Not an access token")
    return uuid.UUID(payload["sub"])


def generate_refresh_token() -> str:
    """
    A high-entropy opaque string, not a JWT. Only its hash is stored
    (see Session.refresh_token_hash) — this way a database leak alone
    can't be used to mint sessions.
    """
    return secrets.token_urlsafe(64)


def hash_refresh_token(token: str) -> str:
    """
    Refresh tokens are high-entropy already (512 bits), so a fast hash
    is fine here — this is not a password, brute-forcing the token
    itself is infeasible. Argon2 would be needless overhead per request.
    """
    import hashlib

    return hashlib.sha256(token.encode()).hexdigest()


def create_purpose_token(
    user_id: uuid.UUID, *, purpose: str, expire_minutes: int, extra: dict[str, Any] | None = None
) -> str:
    """
    A short-lived, single-purpose JWT — email verification and password
    reset links both use this. `purpose` is checked on decode so an email
    verification link can never be replayed as a password reset token
    even though both are just JWTs signed with the same key.
    """
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "type": purpose,
        "iat": now,
        "exp": now + timedelta(minutes=expire_minutes),
        **(extra or {}),
    }
    return jwt.encode(
        payload, settings.secret_key.get_secret_value(), algorithm=settings.jwt_algorithm
    )


def decode_purpose_token(token: str, *, purpose: str) -> dict[str, Any]:
    """Raises jwt exceptions on failure — callers map them to UnauthorizedError."""
    payload = jwt.decode(
        token, settings.secret_key.get_secret_value(), algorithms=[settings.jwt_algorithm]
    )
    if payload.get("type") != purpose:
        raise jwt.InvalidTokenError("Token is not valid for this purpose.")
    return payload
