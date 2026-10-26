# Alumni Challenge

Backend for the Alumni Challenge platform. FastAPI modular monolith, PostgreSQL,
Redis, ARQ workers. See `PLAN.md` for the full build plan and phase gates.

## Local setup (WSL / Linux)

1. Copy the env file and fill in a real secret key:
   ```bash
   cp backend/.env.example backend/.env
   # edit backend/.env — set SECRET_KEY to a long random string
   ```

2. Bring the stack up:
   ```bash
   docker compose up --build
   ```

   This starts Postgres (persistent named volume — survives restarts and
   rebuilds), Redis, the API with hot reload, and a worker placeholder.

   **CPU on Windows/Mac:** the API's hot reload watches files on the bind-mounted folder, which
   is slow there, so the API idles at roughly 5% of a core (it was about 18% when it watched the
   whole project; it is 1% with reload off). It now watches only `backend/app`. The worker has no
   file watcher and idles near 0%. `docker stats` can show a wildly high one-off number for a
   container; trust a few seconds of its streamed output (`docker stats`, no `--no-stream`).
   To pick up a change to `docker-compose.yml`, run `docker compose up -d api` (recreates only
   the API). To turn reload off completely, run the API without it:
   `docker compose run --rm --service-ports api uv run uvicorn app.main:app --host 0.0.0.0 --port 8000`.
   Changes in `backend/migrations` or `backend/tests` do not restart the API.

3. Check it's alive:
   ```bash
   curl http://localhost:8000/health/live
   curl http://localhost:8000/health/ready
   ```

4. API docs (non-production only): http://localhost:8000/api/v1/docs

## Running tests / lint locally without Docker

```bash
cd backend
uv sync
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy app
```

## Database migrations

```bash
cd backend
uv run alembic revision --autogenerate -m "description"
uv run alembic upgrade head
```

## Project structure

Follows the modular monolith layout from the architecture doc — see
`backend/app/core`, `backend/app/modules` (empty until Phase 3 adds the
first domain module), and `backend/app/infrastructure`.

## Status

Phase 1 (Foundation) — backend skeleton, Docker Compose, CI. See `PLAN.md`.
