"""
docs/DEPLOYMENT.md is the only thing the person setting up the servers has. It must not drift:
every setting the app reads must be in its table, and the table must not list ones that do not
exist. (Set DEPLOYMENT_DOC to the file's path to run this where docs/ is not mounted.)
"""

import os
import re
from pathlib import Path

import pytest

from app.core.config import Settings

BACKEND = Path(__file__).resolve().parents[1]
DOC = Path(os.environ.get("DEPLOYMENT_DOC", BACKEND.parent / "docs" / "DEPLOYMENT.md"))

# Read by the image or the platform, not by Settings.
NOT_SETTINGS = {"WEB_CONCURRENCY"}
# Secret values must be marked as such in the table.
SECRET_FIELDS = {
    "SECRET_KEY",
    "DATABASE_URL",
    "REDIS_URL",
    "STORAGE_ACCESS_KEY",
    "STORAGE_SECRET_KEY",
    "SMTP_PASSWORD",
    "RESEND_API_KEY",
    "SENTRY_DSN",
}


def _doc() -> str:
    if not DOC.is_file():
        if os.environ.get("CI"):
            pytest.fail(f"{DOC} must exist in CI")
        pytest.skip(f"{DOC} is not visible from here (set DEPLOYMENT_DOC)")
    return DOC.read_text(encoding="utf-8")


def _table_rows() -> dict[str, list[str]]:
    rows: dict[str, list[str]] = {}
    for line in _doc().splitlines():
        match = re.match(r"\|\s*`([A-Z][A-Z0-9_]+)`\s*\|(.*)\|\s*$", line)
        if match:
            rows[match.group(1)] = [cell.strip() for cell in match.group(2).split("|")]
    return rows


def test_every_setting_is_documented() -> None:
    settings = {name.upper() for name in Settings.model_fields}

    assert settings - set(_table_rows()) == set()


def test_the_table_lists_nothing_that_does_not_exist() -> None:
    settings = {name.upper() for name in Settings.model_fields}

    assert set(_table_rows()) - settings - NOT_SETTINGS == set()


def test_secrets_are_marked_as_secrets_and_nothing_else_is() -> None:
    marked = {name for name, cells in _table_rows().items() if cells[0].startswith("**yes**")}

    assert marked == SECRET_FIELDS


def test_the_documented_defaults_match_the_code() -> None:
    rows = _table_rows()
    defaults = {
        "DATABASE_POOL_SIZE": "10",
        "DATABASE_MAX_OVERFLOW": "5",
        "ACCESS_TOKEN_EXPIRE_MINUTES": "15",
        "REFRESH_TOKEN_EXPIRE_DAYS": "30",
        "SENTRY_TRACES_SAMPLE_RATE": "0.1",
        "SMTP_PORT": "1025",
    }
    fields = {name.upper(): f for name, f in Settings.model_fields.items()}

    for name, shown in defaults.items():
        assert str(fields[name].default) == shown, name
        assert f"`{shown}`" in rows[name][2], name


def test_the_commands_the_doc_tells_you_to_run_exist_in_the_image() -> None:
    text = _doc()

    for command in (
        "alembic upgrade head",
        "arq app.worker.WorkerSettings",
        "python -m app.cli create-super-admin",
        "docker build --target production",
    ):
        assert command in text, command
