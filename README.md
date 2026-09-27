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
