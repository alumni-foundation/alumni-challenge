# syntax=docker/dockerfile:1
#
# One image runs three things, chosen by the command it is started with:
#   the API         (default command)
#   the worker      arq app.worker.WorkerSettings
#   the migrations  alembic upgrade head      (run once per deploy, BEFORE the API starts)
#
# Build:  docker build --target production -t alumni-api:<version> backend
# docker-compose uses this same file and replaces the command with `uv run ... --reload`.

FROM python:3.12-slim AS base
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Dependencies first, so a code-only change does not reinstall them.
FROM base AS deps
COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-dev --no-install-project || uv sync --no-dev --no-install-project

FROM deps AS production
# The virtualenv was built above; put it first so `uvicorn`, `arq` and `alembic` just work.
ENV PATH="/app/.venv/bin:$PATH" \
    WEB_CONCURRENCY=2
COPY . .
RUN uv sync --frozen --no-dev || uv sync --no-dev

# Never run as root.
RUN useradd --create-home --uid 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# "Alive", not "ready": a slow database must not make the platform kill a healthy process.
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health/live || exit 1

# --no-access-log: the app logs each request itself (path only), and uvicorn's own access
# log would print query strings, which can carry short-lived signed-link tokens.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers ${WEB_CONCURRENCY} --no-access-log"]
