# Update: real ARQ worker + domain event mechanism

## Apply (WSL, from repo root)

    unzip -o /mnt/c/Users/Administrator/Downloads/alumni-challenge-update-6.zip -d ~/projects/alumni-challenge/
    cd ~/projects/alumni-challenge
    docker compose up -d --build
    docker compose exec api uv run alembic upgrade head
    git add . && git commit -m "Real ARQ worker: domain event outbox, retries, dead-letter, cron" && git push

Paste back: the migration output and `docker compose logs worker` a minute or so after it starts — you should see `worker_started` then, every ~5 seconds, the cron tick running (silent when there's nothing to do, `domain_events_drained` when there is).

## What changed

73/73 backend tests pass (5 new), ruff + mypy clean. Two mutation checks (disabled the dead-letter threshold, disabled the pending-only filter) both correctly failed the relevant test.

**The worker container does something real now.** `docker-compose.yml`'s `worker` service no longer runs `sleep infinity` — it runs `uv run arq app.worker.WorkerSettings`, a real ARQ worker with a scheduled job that ticks every 5 seconds.

**Domain events, as a transactional outbox** (`app/modules/events/`): publishing an event writes a row to a `domain_events` table in the SAME database transaction as whatever triggered it — there's no separate "tell the queue" step that could fail independently and silently drop the event. A background poller (the ARQ cron job) finds pending rows and runs whatever handlers are registered for that event type.

**Retries and dead-lettering, at the event level, not just ARQ's:** a handler that raises leaves its event `PENDING` with `attempts` incremented, so the next poll retries it — up to 5 times, after which the row flips to `FAILED` and is never picked up again. That row isn't deleted, so `SELECT * FROM domain_events WHERE status = 'failed'` is always a real, inspectable list of what needs a human to look at it — the dead-letter queue the plan asked for, just implemented as a queryable table column instead of a separate queue. (ARQ's own `max_tries=3` sits one layer further out, for the poller job itself crashing — a DB hiccup, say — which is a different failure than a handler's own logic failing.)

**One event wired end to end, as the real example:** registering an account now publishes `user.registered`; a handler (decoupled from the register endpoint — it has no idea a welcome email is one of the things that happens afterward) sends a welcome email through the same `Mailer` abstraction from the last update. Every other event PLAN.md lists (`ConnectionCreated`, `AlumniProfileCompleted`, etc.) can be added later with a `@on("event.type")` decorator and a `publish(...)` call at the point it happens — the mechanism doesn't change.

**Migration:** adds the `domain_events` table (`event_type`, `payload` JSONB, `status`, `attempts`, `last_error`, timestamps).

## Not in this batch

Prometheus/Grafana/OpenTelemetry — the last item on PLAN.md's Phase 2 list — needs actual metrics infrastructure (a Prometheus/Grafana deployment), not just application code, so it's a better fit alongside the Phase 1 deployment work (Coolify, backups) than folded in here. Everything else on the Phase 2 checklist is now done.
