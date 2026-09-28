import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors.exceptions import UnauthorizedError
from app.infrastructure.database.session import get_db_session
from app.modules.identity.models import User, UserStatus
from app.modules.identity.security import decode_access_token

_bearer_scheme = HTTPBearer(auto_error=False)


async def _resolve_user(credentials: HTTPAuthorizationCredentials, db: AsyncSession) -> User:
    try:
        user_id = decode_access_token(credentials.credentials)
    except jwt.ExpiredSignatureError as exc:
        raise UnauthorizedError("Access token has expired.") from exc
    except jwt.InvalidTokenError as exc:
        raise UnauthorizedError("Invalid access token.") from exc

    user = await db.get(User, user_id)
    if user is None or user.status != UserStatus.ACTIVE:
        raise UnauthorizedError("Invalid or inactive account.")

    return user


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: AsyncSession = Depends(get_db_session),
) -> User:
    """
    The single place every protected endpoint gets the authenticated
    user from. Raises UnauthorizedError on any failure — no token,
    expired token, malformed token, or a token for a user that no
    longer exists/is inactive.
    """
    if credentials is None:
        raise UnauthorizedError("Authentication required.")
    return await _resolve_user(credentials, db)


async def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: AsyncSession = Depends(get_db_session),
) -> User | None:
    """
    Same resolution as get_current_user, but returns None instead of
    raising when there's no token or it's invalid — for endpoints
    (like viewing a profile) where anonymous access is legitimate and
    the handler itself decides what an anonymous viewer can see.
    A malformed/expired token here is treated as "anonymous", not an
    error — the caller asked to view public content, a bad token
    shouldn't block that.
    """
    if credentials is None:
        return None
    try:
        return await _resolve_user(credentials, db)
    except UnauthorizedError:
        return None
