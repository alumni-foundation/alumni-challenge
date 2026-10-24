from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.errors.handlers import register_exception_handlers
from app.core.health import router as health_router
from app.core.http.body_size_limit import BodySizeLimitMiddleware
from app.core.http.idempotency import IdempotencyMiddleware
from app.core.http.security_headers import SecurityHeadersMiddleware
from app.core.logging.middleware import RequestContextMiddleware
from app.core.logging.setup import configure_logging
from app.core.observability import init_sentry
from app.core.rate_limit.writes import limit_writes
from app.infrastructure.database import all_models  # noqa: F401 — registers every model
from app.modules.files.policies import UPLOAD_MAX_BODY_BYTES

settings = get_settings()

configure_logging()
logger = structlog.get_logger("startup")

init_sentry(settings)


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
    dependencies=[Depends(limit_writes)],
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
    # Without this the browser hides the header from the web app's JavaScript.
    expose_headers=["X-Total-Count"],
)
app.add_middleware(
    BodySizeLimitMiddleware,
    # Uploads are the only route allowed a body bigger than the global 2 MiB.
    route_limits={("POST", f"{settings.api_v1_prefix}/files"): UPLOAD_MAX_BODY_BYTES},
)

register_exception_handlers(app)

app.include_router(health_router)

from app.modules.identity.router import router as identity_router  # noqa: E402

app.include_router(identity_router, prefix=settings.api_v1_prefix)

from app.modules.alumni.router import router as alumni_router  # noqa: E402
from app.modules.audit.router import router as audit_router  # noqa: E402
from app.modules.bookings import day_router  # noqa: E402
from app.modules.bookings.router import events_router as event_bookings_router  # noqa: E402
from app.modules.bookings.router import router as bookings_router  # noqa: E402
from app.modules.connections.router import router as connections_router  # noqa: E402
from app.modules.domain_events import handlers as _domain_events_handlers  # noqa: E402, F401
from app.modules.events.router import router as events_router  # noqa: E402
from app.modules.events.router import series_router as event_series_router  # noqa: E402
from app.modules.files.router import router as files_router  # noqa: E402
from app.modules.identity.account_router import router as account_router  # noqa: E402
from app.modules.identity.self_service import router as self_service_router  # noqa: E402
from app.modules.memberships.router import router as roles_router  # noqa: E402
from app.modules.moderation.router import router as moderation_router  # noqa: E402
from app.modules.organizations.router import router as organizations_router  # noqa: E402
from app.modules.payments.router import router as payments_router  # noqa: E402

# Importing this module is what runs its @on(...) decorators and
# registers the handlers — needed here too (not just in worker.py)
# since tests and any synchronous drain call go through this process.
app.include_router(account_router, prefix=settings.api_v1_prefix)
app.include_router(self_service_router, prefix=settings.api_v1_prefix)
app.include_router(alumni_router, prefix=settings.api_v1_prefix)
app.include_router(audit_router, prefix=settings.api_v1_prefix)
app.include_router(connections_router, prefix=settings.api_v1_prefix)
app.include_router(events_router, prefix=settings.api_v1_prefix)
app.include_router(event_bookings_router, prefix=settings.api_v1_prefix)
app.include_router(bookings_router, prefix=settings.api_v1_prefix)
app.include_router(day_router.booking_tickets_router, prefix=settings.api_v1_prefix)
app.include_router(day_router.tickets_router, prefix=settings.api_v1_prefix)
app.include_router(day_router.organizer_router, prefix=settings.api_v1_prefix)
app.include_router(event_series_router, prefix=settings.api_v1_prefix)
app.include_router(files_router, prefix=settings.api_v1_prefix)
app.include_router(moderation_router, prefix=settings.api_v1_prefix)
app.include_router(roles_router, prefix=settings.api_v1_prefix)
app.include_router(organizations_router, prefix=settings.api_v1_prefix)
app.include_router(payments_router, prefix=settings.api_v1_prefix)
