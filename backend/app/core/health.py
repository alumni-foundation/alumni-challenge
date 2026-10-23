import asyncio
from typing import Any

from fastapi import APIRouter, Response, status

from app.infrastructure.database.session import check_database_connection
from app.infrastructure.redis import get_redis_client

router = APIRouter(tags=["health"])


@router.get("/health/live")
async def liveness() -> dict[str, Any]:
    """
    Is the process alive? Never checks dependencies — a slow database
    should not make Kubernetes/Coolify kill and restart a healthy process.
    """
    return {"status": "alive"}


async def _redis_is_up() -> bool:
    try:
        return bool(await asyncio.wait_for(get_redis_client().ping(), timeout=2))
    except Exception:  # noqa: BLE001 — any failure just means "down" here
        return False


@router.get("/health/ready")
async def readiness(response: Response) -> dict[str, Any]:
    """
    Can this instance actually serve traffic? Checks the database,
    since every real endpoint needs it. Deliberately does NOT check
    optional dependencies (email provider, SMS, object storage) —
    per the doc's failure-isolation principle, those going down should
    never pull a healthy API instance out of the load balancer.

    Redis is reported but does not decide readiness: with Redis down, sign-in and other
    rate-limited writes fail, but reading profiles and events still works, and restarting
    or removing every API instance would not bring Redis back.
    """
    db_ok = await check_database_connection()
    redis_ok = await _redis_is_up()
    redis = "up" if redis_ok else "down"
    if not db_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "not_ready", "database": "down", "redis": redis}
    return {"status": "ready", "database": "up", "redis": redis}
