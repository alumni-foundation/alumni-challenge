"""scripts/load_bookings.py writes thousands of rows: it must refuse anything but test targets."""

import asyncio
import importlib.util
import os
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "load_bookings.py"
TEST_DB = "postgresql+asyncpg://u:p@db:5432/alumni_challenge_test"
DEV_DB = "postgresql+asyncpg://u:p@db:5432/alumni_challenge"


def _load() -> ModuleType:
    if not SCRIPT.is_file():
        if os.environ.get("CI"):
            pytest.fail("scripts/ must exist in CI")
        pytest.skip("scripts/ is not visible from here")
    spec = importlib.util.spec_from_file_location("load_bookings", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_it_refuses_a_non_test_database_and_the_development_redis_index() -> None:
    refusal = _load().refusal
    assert refusal(TEST_DB, "redis://r:6379/15") is None
    assert "_test" in refusal(DEV_DB, "redis://r:6379/15")
    assert "Redis index 0" in refusal(TEST_DB, "redis://r:6379/0")
    assert "Redis index 0" in refusal(TEST_DB, "redis://r:6379")  # no index means 0


@pytest.mark.parametrize(
    ("database", "redis"), [(DEV_DB, "redis://r:6379/15"), (TEST_DB, "redis://r:6379/0")]
)
def test_main_exits_before_touching_anything_when_the_targets_are_not_test_targets(
    monkeypatch: pytest.MonkeyPatch, database: str, redis: str
) -> None:
    module = _load()
    monkeypatch.setattr(
        module, "get_settings", lambda: SimpleNamespace(database_url=database, redis_url=redis)
    )
    monkeypatch.setattr(sys, "argv", ["load_bookings.py"])
    assert asyncio.run(module.main()) == 2
