from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings

settings = get_settings()

# Pool sized deliberately, not left at defaults — per the architecture
# doc's requirement: API replicas x workers x connections must never
# overload Postgres. pool_size + max_overflow is the ceiling PER
# process; multiply by however many uvicorn workers/replicas run.
engine = create_async_engine(
    str(settings.database_url),
    pool_size=settings.database_pool_size,
    max_overflow=settings.database_max_overflow,
    pool_pre_ping=True,  # detects dead connections instead of failing requests on them
    echo=settings.debug,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Every ORM model inherits from this."""


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency — yields a session, always closed after the request."""
    async with async_session_factory() as session:
        yield session


async def check_database_connection() -> bool:
    """Used by the readiness health check."""
    from sqlalchemy import text

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
