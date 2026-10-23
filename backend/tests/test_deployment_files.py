"""
Guards on the files a deployment depends on. They cannot prove the image works (that was run
by hand and is in docs/DEPLOYMENT.md), but they stop the easy, quiet regressions.
"""

import os
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parent
DOCKERFILE = (BACKEND / "Dockerfile").read_text()
DOCKERIGNORE = (BACKEND / ".dockerignore").read_text().splitlines()


def _final_stage(text: str) -> str:
    return text.split("FROM deps AS production", 1)[1]


def test_there_is_a_production_target() -> None:
    assert "FROM deps AS production" in DOCKERFILE


def test_the_production_image_does_not_run_as_root() -> None:
    stage = _final_stage(DOCKERFILE)

    assert "USER appuser" in stage
    assert stage.index("USER appuser") < stage.index("CMD")


def test_the_production_command_is_not_a_development_server() -> None:
    stage = _final_stage(DOCKERFILE)
    command = stage[stage.index("CMD") :]

    assert "--reload" not in command
    assert "uvicorn app.main:app" in command


def test_uvicorn_does_not_print_query_strings_because_they_can_hold_signed_link_tokens() -> None:
    assert "--no-access-log" in _final_stage(DOCKERFILE)


def test_the_image_checks_its_own_health() -> None:
    assert "HEALTHCHECK" in _final_stage(DOCKERFILE)
    assert "/health/live" in _final_stage(DOCKERFILE)


def test_secrets_data_and_tests_stay_out_of_the_image() -> None:
    for pattern in (".env", ".env.*", "var", "tests", ".venv", "*.dump"):
        assert pattern in DOCKERIGNORE, f"{pattern} should be in .dockerignore"
    assert "!.env.example" in DOCKERIGNORE


def test_the_backup_scripts_exist_and_do_not_leave_the_dump_readable_by_everyone() -> None:
    if not (REPO / "scripts").is_dir():
        # Inside the dev container only backend/ is mounted. CI has the whole repository.
        if os.environ.get("CI"):
            pytest.fail("scripts/ must exist in CI")
        pytest.skip("scripts/ is not visible from here")
    backup = (REPO / "scripts" / "backup-db.sh").read_text()
    restore = (REPO / "scripts" / "restore-db.sh").read_text()

    assert "umask 077" in backup
    assert "set -euo pipefail" in backup and "set -euo pipefail" in restore
    assert "--yes-overwrite" in restore  # a restore never overwrites by accident
