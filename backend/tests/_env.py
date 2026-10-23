"""
Points the whole test process at its own Postgres database and Redis index.

Imported first by conftest.py, before anything imports `app`, because the app builds
its engine and Redis client from the environment at import time. By the time any
test runs, DATABASE_URL and REDIS_URL already name the test targets, so the app and
the fixtures cannot reach the development database or the development Redis index.

Override with TEST_DATABASE_URL / TEST_REDIS_URL; otherwise they are derived from
DATABASE_URL / REDIS_URL.
"""

import os
from urllib.parse import urlsplit, urlunsplit

TEST_REDIS_DB_INDEX = 15


def derive_test_database_url(url: str) -> str:
    parts = urlsplit(url)
    name = parts.path.lstrip("/")
    if not name.endswith("_test"):
        name = f"{name}_test"
    return urlunsplit(parts._replace(path=f"/{name}"))


def derive_test_redis_url(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit(parts._replace(path=f"/{TEST_REDIS_DB_INDEX}"))


def database_name(url: str) -> str:
    return urlsplit(url).path.lstrip("/")


def redis_db_index(url: str) -> int:
    path = urlsplit(url).path.lstrip("/")
    return int(path) if path else 0


def assert_safe_test_targets(database_url: str, redis_url: str) -> None:
    if not database_name(database_url).endswith("_test"):
        raise RuntimeError(
            f"Refusing to run tests against database {database_name(database_url)!r}"
        )
    if redis_db_index(redis_url) == 0:
        raise RuntimeError("Refusing to run tests against Redis index 0 (the development index)")


def configure_test_environment() -> None:
    # Environment variables win over .env in the app's settings, so read them the same
    # way: fall back to .env only when the variable isn't set.
    from app.core.config import Settings

    dev_db = os.environ.get("DATABASE_URL") or str(Settings().database_url)
    dev_redis = os.environ.get("REDIS_URL") or str(Settings().redis_url)
    database_url = os.environ.get("TEST_DATABASE_URL") or derive_test_database_url(dev_db)
    redis_url = os.environ.get("TEST_REDIS_URL") or derive_test_redis_url(dev_redis)
    assert_safe_test_targets(database_url, redis_url)
    os.environ["DATABASE_URL"] = database_url
    os.environ["REDIS_URL"] = redis_url
    # Tests never send email, never write to a real object store, and always behave as development,
    # whatever the developer's .env or compose file says.
    os.environ["MAIL_BACKEND"] = "logging"
    os.environ["STORAGE_BACKEND"] = "local"
    os.environ["ENVIRONMENT"] = "development"


configure_test_environment()
