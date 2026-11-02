import asyncio
import secrets
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.core.config import get_settings

settings = get_settings()
# One lane (parallelism=1), not the library default of 4. With four lanes the Argon2 library
# was seen to return a wrong answer about 2.5% of the time in our Linux container (20 of 800
# hash-then-verify rounds: some verifies failed on a good hash, some hashes never verified),
# which shows up as "Invalid email or password" for the right password. One lane: 0 of 800 in
# that probe, but wrong answers were later seen in full suite runs on that machine even with one
# lane. Cause there NOT confirmed; GitHub CI never showed it. See DEPLOYMENT.md, step 16.
# Memory (64 MiB) and time cost (3) are unchanged, so it is as costly to guess; hashes made
# earlier carry their own parameters and still verify (they are not re-hashed automatically).
_hasher = PasswordHasher(parallelism=1)

# Tolerance for ordinary clock drift between the machines that issue and check tokens.
# Deliberately small and a constant, not a setting: a wide leeway keeps expired and
# not-yet-valid tokens alive, so it must never be raised to paper over a wrong clock.
JWT_LEEWAY_SECONDS = 10


def hash_password(plain_password: str) -> str:
    return _hasher.hash(plain_password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, plain_password)
    except VerifyMismatchError:
        return False


# Hashing takes about a quarter of a second and 64 MiB. Request handlers use the async versions
# below, which run it in a small thread pool of their own, so that (1) the event loop keeps
# serving other requests meanwhile (Argon2's C code lets go of the GIL), and (2) no more than
# `password_hash_concurrency` hashes run at once, which caps the memory they can take at that
# many times 64 MiB. A request over the cap waits its turn in the pool's queue; it is never
# refused. The synchronous functions above are for the command line, the seed and tests.
_pool: ThreadPoolExecutor | None = None


def _hash_pool() -> ThreadPoolExecutor:
    global _pool
    if _pool is None:
        _pool = ThreadPoolExecutor(
            max_workers=settings.password_hash_concurrency, thread_name_prefix="argon2"
        )
    return _pool


async def hash_password_async(plain_password: str) -> str:
    return await asyncio.get_running_loop().run_in_executor(
        _hash_pool(), hash_password, plain_password
    )


async def verify_password_async(plain_password: str, password_hash: str) -> bool:
    return await asyncio.get_running_loop().run_in_executor(
        _hash_pool(), verify_password, plain_password, password_hash
    )


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
        token,
        settings.secret_key.get_secret_value(),
        algorithms=[settings.jwt_algorithm],
        leeway=JWT_LEEWAY_SECONDS,
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
        token,
        settings.secret_key.get_secret_value(),
        algorithms=[settings.jwt_algorithm],
        leeway=JWT_LEEWAY_SECONDS,
    )
    if payload.get("type") != purpose:
        raise jwt.InvalidTokenError("Token is not valid for this purpose.")
    return payload
