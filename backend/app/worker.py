"""
The real ARQ worker entry point, replacing the docker-compose placeholder.
Run with: uv run arq app.worker.WorkerSettings

Retries and dead-lettering happen at the domain-event level (see
events/service.py's drain_pending — a handler that keeps failing gets
its event marked FAILED after MAX_ATTEMPTS, which is the durable,
inspectable dead-letter). ARQ's own `max_tries` below is a second,
outer safety net for the drain job ITSELF crashing (a DB connection
blip, say) — separate from an individual event's own handler failing.
"""

import logging
from typing import Any

from arq import cron
from arq.connections import RedisSettings

from app.core.config import get_settings
from app.infrastructure.database.session import async_session_factory
from app.modules.events import handlers  # noqa: F401 — import registers the @on(...) handlers
from app.modules.events.service import drain_pending

settings = get_settings()
logger = logging.getLogger("worker")


async def drain_domain_events(ctx: dict[str, Any]) -> int:
    """
    Scheduled job (see WorkerSettings.cron_jobs below): polls the
    domain_events outbox every 5 seconds and dispatches whatever is
    pending. Also callable on demand via `job.enqueue_job` if something
    wants a faster dispatch than waiting for the next tick.
    """
    async with async_session_factory() as db:
        count = await drain_pending(db)
        await db.commit()
        if count:
            logger.info("domain_events_drained", extra={"count": count})
        return count


async def on_startup(ctx: dict[str, Any]) -> None:
    logger.info("worker_started")


async def on_shutdown(ctx: dict[str, Any]) -> None:
    logger.info("worker_stopped")


class WorkerSettings:
    functions = [drain_domain_events]
    cron_jobs = [cron(drain_domain_events, second=set(range(0, 60, 5)), run_at_startup=True)]
    redis_settings = RedisSettings.from_dsn(str(settings.redis_url))
    on_startup = on_startup
    on_shutdown = on_shutdown
    # A job (this cron tick or a manually enqueued one) gets retried up to
    # this many times by ARQ itself if it raises — separate from, and
    # outer to, the per-event attempt counting inside drain_pending.
    max_tries = 3
    job_timeout = 60
