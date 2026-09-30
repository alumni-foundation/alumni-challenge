from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import sentry_sdk
import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.errors.handlers import register_exception_handlers
from app.core.health import router as health_router
from app.core.http.body_size_limit import BodySizeLimitMiddleware
from app.core.http.idempotency import IdempotencyMiddleware
from app.core.http.security_headers import SecurityHeadersMiddleware
from app.core.logging.middleware import RequestContextMiddleware
from app.core.logging.setup import configure_logging
from app.infrastructure.database import all_models  # noqa: F401 — registers every model

settings = get_settings()

configure_logging()
logger = structlog.get_logger("startup")

if settings.sentry_dsn:
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.environment,
        traces_sample_rate=0.1 if settings.is_production else 1.0,
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info("app_starting", environment=settings.environment)
    yield
    logger.info("app_stopping")


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    openapi_url=f"{settings.api_v1_prefix}/openapi.json",
    docs_url=f"{settings.api_v1_prefix}/docs" if not settings.is_production else None,
    lifespan=lifespan,
)

# Order matters: middleware runs outside-in on the way in, inside-out on
# the way out, so the LAST one added here is the first to see the
# request. Body size limit goes outermost so an oversized request is
# rejected before CORS or idempotency ever touch it.
app.add_middleware(IdempotencyMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(BodySizeLimitMiddleware)

register_exception_handlers(app)

app.include_router(health_router)

from app.modules.identity.router import router as identity_router  # noqa: E402

app.include_router(identity_router, prefix=settings.api_v1_prefix)

from app.modules.alumni.router import router as alumni_router  # noqa: E402
from app.modules.audit.router import router as audit_router  # noqa: E402
from app.modules.connections.router import router as connections_router  # noqa: E402
from app.modules.organizations.router import router as organizations_router  # noqa: E402

app.include_router(alumni_router, prefix=settings.api_v1_prefix)
app.include_router(audit_router, prefix=settings.api_v1_prefix)
app.include_router(connections_router, prefix=settings.api_v1_prefix)
app.include_router(organizations_router, prefix=settings.api_v1_prefix)
