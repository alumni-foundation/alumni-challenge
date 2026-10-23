import pytest

from app.core.config import get_settings
from tests import _env


def test_the_suite_runs_against_a_test_database_and_a_non_default_redis_index() -> None:
    settings = get_settings()
    assert _env.database_name(str(settings.database_url)).endswith("_test")
    assert _env.redis_db_index(str(settings.redis_url)) != 0


def test_the_test_database_name_is_derived_from_the_dev_one() -> None:
    assert (
        _env.derive_test_database_url("postgresql+asyncpg://u:p@db:5432/alumni_challenge")
        == "postgresql+asyncpg://u:p@db:5432/alumni_challenge_test"
    )


def test_a_name_that_is_already_a_test_database_is_kept() -> None:
    url = "postgresql+asyncpg://u:p@db:5432/alumni_challenge_test"
    assert _env.derive_test_database_url(url) == url


def test_the_test_redis_url_uses_the_test_index() -> None:
    assert _env.derive_test_redis_url("redis://redis:6379/0") == "redis://redis:6379/15"


def test_a_development_database_is_refused() -> None:
    with pytest.raises(RuntimeError, match="database"):
        _env.assert_safe_test_targets(
            "postgresql+asyncpg://u:p@db/alumni_challenge", "redis://r/15"
        )


def test_the_development_redis_index_is_refused() -> None:
    with pytest.raises(RuntimeError, match="Redis"):
        _env.assert_safe_test_targets("postgresql+asyncpg://u:p@db/x_test", "redis://r:6379/0")
