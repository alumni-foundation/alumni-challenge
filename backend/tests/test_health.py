from collections.abc import AsyncIterator

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.core import health
from app.core.config import get_settings
from app.infrastructure.database import session as db_session_module


@pytest.fixture
async def _own_engine(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[None]:
    """The app's engine keeps pooled connections tied to an earlier test's event loop; give the
    health check a fresh one so the test is about the database, not about test ordering."""
    engine = create_async_engine(str(get_settings().database_url), poolclass=NullPool)
    monkeypatch.setattr(db_session_module, "engine", engine)
    yield
    await engine.dispose()


async def test_live_says_alive(client: AsyncClient) -> None:
    r = await client.get("/health/live")

    assert r.status_code == 200
    assert r.json() == {"status": "alive"}


async def test_live_never_looks_at_dependencies(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def _explode() -> bool:
        raise AssertionError("liveness must not check anything else")

    monkeypatch.setattr(health, "check_database_connection", _explode)
    monkeypatch.setattr(health, "_redis_is_up", _explode)

    assert (await client.get("/health/live")).status_code == 200


async def test_ready_when_the_database_is_up(client: AsyncClient, _own_engine: None) -> None:
    r = await client.get("/health/ready")

    assert r.status_code == 200
    assert r.json() == {"status": "ready", "database": "up", "redis": "up"}


async def test_not_ready_without_the_database(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def _down() -> bool:
        return False

    monkeypatch.setattr(health, "check_database_connection", _down)

    r = await client.get("/health/ready")

    assert r.status_code == 503
    assert r.json()["database"] == "down"


async def test_a_redis_outage_is_reported_but_does_not_take_the_api_out_of_service(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch, _own_engine: None
) -> None:
    async def _down() -> bool:
        return False

    monkeypatch.setattr(health, "_redis_is_up", _down)

    r = await client.get("/health/ready")

    assert r.status_code == 200
    assert r.json() == {"status": "ready", "database": "up", "redis": "down"}


async def test_a_hanging_redis_cannot_hang_the_health_check(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch, _own_engine: None
) -> None:
    class _Hangs:
        async def ping(self) -> bool:
            import asyncio

            await asyncio.sleep(30)
            return True

    monkeypatch.setattr(health, "get_redis_client", lambda: _Hangs())

    r = await client.get("/health/ready")

    assert r.status_code == 200
    assert r.json()["redis"] == "down"


async def test_a_storage_or_mail_outage_cannot_matter_to_readiness(
    client: AsyncClient, _own_engine: None
) -> None:
    """Readiness mentions only the database and Redis, by design."""
    r = await client.get("/health/ready")

    assert set(r.json()) == {"status", "database", "redis"}
