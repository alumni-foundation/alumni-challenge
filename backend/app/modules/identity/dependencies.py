import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors.exceptions import UnauthorizedError
from app.infrastructure.database.session import get_db_session
from app.modules.identity.models import User, UserStatus
from app.modules.identity.security import decode_access_token

_bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: AsyncSession = Depends(get_db_session),
) -> User:
    """
    The single place every protected endpoint gets the authenticated
    user from. Raises UnauthorizedError (-> 403 via ForbiddenError
    semantics is wrong; this is 401) on any failure — expired token,
    malformed token, or a token for a user that no longer exists/active.
    """
    if credentials is None:
        raise UnauthorizedError("Authentication required.")

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
