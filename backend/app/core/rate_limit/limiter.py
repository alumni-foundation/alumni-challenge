"""
Fixed-window rate limiting on Redis: INCR a per-window counter, set its
expiry the first time it's touched, reject once the count passes the
limit. Simple and correct for our load — a request right at the window
boundary can allow briefly more than `limit` in rare cases, which is an
accepted trade-off (a sliding-window log would cost a request per hit to
maintain and isn't justified at this traffic).
"""

from collections.abc import Awaitable, Callable

from fastapi import Request

from app.core.config import get_settings
from app.core.errors.exceptions import RateLimitedError
from app.infrastructure.redis import get_redis_client


async def hit(key: str, *, limit: int, window_seconds: int) -> None:
    redis = get_redis_client()
    current = await redis.incr(key)
    if current == 1:
        await redis.expire(key, window_seconds)
    if current > limit:
        raise RateLimitedError("Too many requests. Please try again later.")


def client_ip(request: Request) -> str:
    """
    The visitor's address. Behind a proxy the socket address is the proxy's, which would put
    every visitor in one rate-limit bucket and lock everybody out together, so a configured
    header (TRUSTED_CLIENT_IP_HEADER) is read instead. It is only read when configured, because
    anyone can send these headers to an API they can reach directly.
    """
    header = get_settings().trusted_client_ip_header
    if header != "none":
        value = request.headers.get(header)
        if value:
            # X-Forwarded-For is a list; the first entry is the original visitor.
            return value.split(",")[0].strip()[:64]
    return request.client.host if request.client else "unknown"


def rate_limit(
    scope: str, *, limit: int, window_seconds: int
) -> "Callable[[Request], Awaitable[None]]":
    """
    A FastAPI dependency factory, keyed by client IP. Add as a route
    dependency: `Depends(rate_limit("register", limit=10, window_seconds=3600))`.
    """

    async def _dependency(request: Request) -> None:
        await hit(
            f"ratelimit:{scope}:{client_ip(request)}", limit=limit, window_seconds=window_seconds
        )

    # Lets a test prove that every public write route carries a limit of its own.
    _dependency.rate_limit_scope = scope  # type: ignore[attr-defined]
    return _dependency
