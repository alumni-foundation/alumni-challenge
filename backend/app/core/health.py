from typing import Any

from fastapi import APIRouter, Response, status

from app.infrastructure.database.session import check_database_connection

router = APIRouter(tags=["health"])


@router.get("/health/live")
async def liveness() -> dict[str, Any]:
    """
    Is the process alive? Never checks dependencies — a slow database
    should not make Kubernetes/Coolify kill and restart a healthy process.
    """
    return {"status": "alive"}


@router.get("/health/ready")
async def readiness(response: Response) -> dict[str, Any]:
    """
    Can this instance actually serve traffic? Checks the database,
    since every real endpoint needs it. Deliberately does NOT check
    optional dependencies (email provider, SMS, object storage) —
    per the doc's failure-isolation principle, those going down should
    never pull a healthy API instance out of the load balancer.
    """
    db_ok = await check_database_connection()
    if not db_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "not_ready", "database": "down"}
    return {"status": "ready", "database": "up"}
