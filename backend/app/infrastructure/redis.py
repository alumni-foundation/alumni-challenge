"""
A single shared Redis client for the process. Not a FastAPI dependency —
rate limiting needs to run from places that aren't request handlers too
(and a plain function is simpler to call from both). Connection pooling
is handled internally by redis-py's async client, same idea as the
SQLAlchemy engine in infrastructure/database/session.py.
"""

from redis.asyncio import Redis

from app.core.config import get_settings

settings = get_settings()

_client: Redis | None = None


def get_redis_client() -> Redis:
    global _client
    if _client is None:
        _client = Redis.from_url(str(settings.redis_url), decode_responses=True)
    return _client


async def reset_redis_client_for_tests() -> None:
    """
    Test-only. The client above is a process-wide singleton bound to
    whichever asyncio event loop first created it — fine in production
    (one loop, one process), but pytest-asyncio gives each test function
    its own loop by default. Reusing the old client from a new loop
    raises RuntimeError, so tests close and drop it between runs and let
    get_redis_client() lazily build a fresh one on the new loop.
    """
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
