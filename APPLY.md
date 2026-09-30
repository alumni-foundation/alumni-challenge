# Update: Phase 2 leftovers — audit log, security headers, request size limit, Idempotency-Key

## Apply (WSL, from repo root)

    unzip -o /mnt/c/Users/Administrator/Downloads/alumni-challenge-update-4.zip -d ~/projects/alumni-challenge/
    cd ~/projects/alumni-challenge
    docker compose up -d --build
    docker compose exec api uv run alembic upgrade head
    git add . && git commit -m "Phase 2: audit log, security headers, body size limit, Idempotency-Key" && git push

Paste back: the migration output and the GitHub Actions result.

## What changed

68/68 backend tests pass (11 new), ruff + mypy clean. Two deliberate mutation checks (disabled the audit org-filter, disabled the idempotency lock) both correctly failed the relevant test — confirms these aren't passing by accident.

**Audit log** (`GET /api/v1/audit-log`) — the table from the ERD, finally built. Platform admins (`admin`/`super_admin`) see everything; a `school_admin`/`partner_admin` sees only entries tagged with an organization they administer; everyone else gets 403. Wired into five real actions: creating an organization, granting a membership, adding a school email domain, verifying an alumni profile, and resetting a password. Each entry is written in the same database transaction as the action itself, so a rolled-back action never leaves a phantom audit row.

**Security headers** — `X-Content-Type-Options`, `X-Frame-Options`, a `Content-Security-Policy` scoped for a JSON API (with the Swagger UI's own asset host allowed), `Referrer-Policy`, `Permissions-Policy`. `Strict-Transport-Security` only sends when `ENVIRONMENT=production`.

**Request body size limit** — 2 MiB cap (nothing accepts file uploads yet). Rejects on the declared `Content-Length` before any other middleware or the route handler runs, with a streaming byte-counter as a second layer for a client that lies about or omits the header.

**Idempotency-Key** — send an `Idempotency-Key` header on any `POST`/`PUT`/`PATCH`/`DELETE` and a retry with the same key replays the original response instead of re-running the handler; a second request arriving *while the first is still in flight* gets `409 idempotency_in_progress` instead of racing it. No client is required to send the header — everything works exactly as before if they don't. This is the exact mechanism the payments gate (Phase 6) needs for "duplicate callbacks can't create duplicate payments," built once and already reusable by every route.

**Migration:** adds the `audit_log` table (`metadata` column mapped to a Python attribute named `context`, since `metadata` is reserved on every SQLAlchemy model — noted in the model's docstring so it doesn't get "fixed" back into a conflict later).

## Not in this batch (from PLAN.md Phase 2, deliberately left for a separate pass)

Prometheus/Grafana/OpenTelemetry, the real ARQ worker (retries, dead-letter, scheduled jobs — the container still runs but isn't doing anything yet), and the domain-event mechanism (`UserRegistered`, `ConnectionCreated`, etc.). These are the largest remaining Phase 2 items and are closer to infrastructure setup than the code-only work in this delivery — worth their own focused pass rather than folding into this one.
