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
    marker = "FROM python:3.12-slim AS production"
    stage = text.split(marker, 1)[1]
    # The development stage follows and is not published.
    return stage.split("\nFROM ", 1)[0]


def test_there_is_a_production_target() -> None:
    assert "FROM python:3.12-slim AS production" in DOCKERFILE


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
    stage = _final_stage(DOCKERFILE)

    assert "HEALTHCHECK" in stage
    assert "/health/live" in stage
    assert "curl" not in stage


def test_the_production_image_ships_only_the_runtime() -> None:
    stage = _final_stage(DOCKERFILE)

    assert "COPY --from=deps" in stage
    assert "/app/.venv" in stage
    assert "app ./app" in stage
    assert "migrations ./migrations" in stage
    assert "alembic.ini ./alembic.ini" in stage
    assert "COPY . ." not in stage
    assert "/uv" not in stage
    assert "uv sync" not in stage


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


# ------------------------------------------------------------- publishing the image

CI_WORKFLOW = Path(os.environ.get("CI_WORKFLOW", REPO / ".github" / "workflows" / "ci.yml"))


def _publish_job() -> str:
    if not CI_WORKFLOW.is_file():
        if os.environ.get("CI"):
            pytest.fail(f"{CI_WORKFLOW} must exist in CI")
        pytest.skip(f"{CI_WORKFLOW} is not visible from here (set CI_WORKFLOW)")
    text = CI_WORKFLOW.read_text(encoding="utf-8")
    assert "\n  publish-image:" in text
    return text.split("\n  publish-image:", 1)[1]


def test_main_publishes_the_production_image_with_the_commit_as_its_tag() -> None:
    job = _publish_job()
    assert "github.ref == 'refs/heads/main'" in job
    assert "github.event_name == 'push'" in job
    assert "needs: lint-and-test" in job  # never publish an image that failed the tests
    assert "target: production" in job
    assert "push: true" in job
    assert "ghcr.io" in job
    assert "type=sha" in job
    assert "latest=false" in job


def test_publishing_uses_the_workflow_token_and_nothing_wider_than_it_needs() -> None:
    job = _publish_job()
    assert "secrets.GITHUB_TOKEN" in job
    assert "packages: write" in job
    assert "contents: read" in job
    # no personal tokens or other stored credentials
    assert job.count("secrets.") == 1


def test_pull_requests_never_push_an_image() -> None:
    text = CI_WORKFLOW.read_text(encoding="utf-8") if CI_WORKFLOW.is_file() else ""
    if not text:
        pytest.skip("workflow not visible")
    build_job = text.split("\n  docker-build:", 1)[1].split("\n  publish-image:", 1)[0]
    assert "pull_request" in build_job
    assert "push: false" in build_job
