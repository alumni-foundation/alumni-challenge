# syntax=docker/dockerfile:1
#
# One image runs three things, chosen by the command it is started with:
#   the API         (default command)
#   the worker      arq app.worker.WorkerSettings
#   the migrations  alembic upgrade head      (run once per deploy, BEFORE the API starts)
#
# Build:  docker build --target production -t alumni-api:<version> backend
# docker-compose uses the development target and replaces the command with `uv run ...`.
#
# The production stage is a fresh slim image. It copies the dependency virtualenv
# first, then only the files the process needs, so a code-only publish changes
# the last layer and a server that already has the image pulls just that layer.

FROM python:3.12-slim AS base
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /app

# Dependencies only. uv stays in this stage; the runtime image never sees it.
FROM base AS deps
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-dev --no-install-project || uv sync --no-dev --no-install-project

FROM python:3.12-slim AS production
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH=/app \
    WEB_CONCURRENCY=2
WORKDIR /app

# Empty directories only: chown after COPY would store the application twice.
RUN useradd --create-home --uid 1000 appuser \
    && mkdir -p /app/var/uploads \
    && chown -R appuser:appuser /app

# Virtualenv first, so a code change does not invalidate the dependency layer.
COPY --from=deps --chown=appuser:appuser /app/.venv /app/.venv
COPY --chown=appuser:appuser app ./app
COPY --chown=appuser:appuser migrations ./migrations
COPY --chown=appuser:appuser alembic.ini ./alembic.ini

USER appuser

EXPOSE 8000

# "Alive", not "ready": a slow database must not make the platform kill a healthy process.
# The standard library does the request, so no extra package is installed for it.
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/live')" || exit 1

# --no-access-log: the app logs each request itself (path only), and uvicorn's own access
# log would print query strings, which can carry short-lived signed-link tokens.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers ${WEB_CONCURRENCY} --no-access-log"]

# Local compose bind-mounts the source and runs `uv run`. This stage is not published.
FROM deps AS development
ENV PATH="/app/.venv/bin:$PATH"
