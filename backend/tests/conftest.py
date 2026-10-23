import asyncio
import subprocess
import sys
from collections.abc import AsyncGenerator, Iterator
from pathlib import Path
from urllib.parse import urlsplit

import asyncpg
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

import tests._env as test_env
from app.core.config import get_settings
from app.infrastructure.database.session import get_db_session
from app.infrastructure.redis import get_redis_client, reset_redis_client_for_tests
from app.infrastructure.storage import LocalDiskStorage, get_storage
from app.main import app

settings = get_settings()

BACKEND_DIR = Path(__file__).resolve().parent.parent


def _plain_dsn(url: str) -> str:
    return url.replace("postgresql+asyncpg://", "postgresql://", 1)


async def _ensure_database_exists(database_url: str) -> None:
    parts = urlsplit(_plain_dsn(database_url))
    name = parts.path.lstrip("/")
    maintenance_dsn = parts._replace(path="/postgres").geturl()
    conn = await asyncpg.connect(maintenance_dsn)
    try:
        exists = await conn.fetchval("SELECT 1 FROM pg_database WHERE datname = $1", name)
        if not exists:
            await conn.execute(f'CREATE DATABASE "{name}"')
    finally:
        await conn.close()


def pytest_sessionstart(session: pytest.Session) -> None:
    """
    Tests run against their own database, created on demand and brought to the latest
    migration. Nothing here can touch the development database: tests/_env.py has
    already pointed DATABASE_URL at a *_test database, and we re-check it here.
    """
    database_url = str(settings.database_url)
    test_env.assert_safe_test_targets(database_url, str(settings.redis_url))
    asyncio.run(_ensure_database_exists(database_url))
    # A subprocess keeps alembic's logging setup out of the pytest process.
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND_DIR,
        check=True,
        capture_output=True,
    )


@pytest.fixture(autouse=True)
async def _clean_redis() -> AsyncGenerator[None, None]:
    """
    Rate limiting and login-lockout state lives in Redis, outside the
    per-test database transaction that db_session rolls back. Without
    this, one test's login attempts count toward the next test's rate
    limit and lockout windows — flaky failures that have nothing to do
    with what that test is actually checking.

    The Redis client points at the dedicated test index (see tests/_env.py), so
    clearing it never touches development data. The guard below makes that a
    hard stop rather than an assumption.
    """
    test_env.assert_safe_test_targets(str(settings.database_url), str(settings.redis_url))
    await reset_redis_client_for_tests()
    redis = get_redis_client()
    await redis.flushdb()
    yield
    await reset_redis_client_for_tests()


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    A real session against the test database, fully isolated per test.

    Deliberately creates its OWN engine here instead of reusing the
    app's module-level engine. Reusing a long-lived engine across
    pytest-asyncio's per-test event loops causes asyncpg connections
    to be used from a different loop than they were created on —
    NullPool plus a fresh engine per test sidesteps that entirely, at
    the cost of a fresh connection per test (fine at this test count).

    join_transaction_mode="create_savepoint" matters separately: the
    identity endpoints call session.commit() internally, same as real
    request handling. Without this, that commit would end our outer
    transaction early and the rollback below would have nothing left
    to undo. With it, each app-level commit releases a SAVEPOINT and
    opens a new one, nested inside the outer transaction we control —
    so test data never survives past the test regardless of how many
    times the code under test commits.
    """
    test_engine = create_async_engine(str(settings.database_url), poolclass=NullPool)
    try:
        async with test_engine.connect() as connection:
            # Explicit begin/rollback. `async with connection.begin()` would COMMIT
            # on a clean exit, silently persisting every test's data.
            outer = await connection.begin()
            try:
                test_session_factory = async_sessionmaker(
                    bind=connection,
                    join_transaction_mode="create_savepoint",
                    expire_on_commit=False,
                )
                async with test_session_factory() as session:
                    yield session
            finally:
                await outer.rollback()
    finally:
        await test_engine.dispose()


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def _override_get_db_session() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db_session] = _override_get_db_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture
def storage(client: AsyncClient, tmp_path: Path) -> Iterator[LocalDiskStorage]:
    """Uploads go to a throwaway folder. Depends on `client` so the override is set after it
    and cleared with it."""
    local = LocalDiskStorage(tmp_path / "uploads")
    app.dependency_overrides[get_storage] = lambda: local
    yield local
