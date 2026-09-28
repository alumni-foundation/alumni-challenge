from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.infrastructure.database.session import get_db_session
from app.main import app

settings = get_settings()


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
