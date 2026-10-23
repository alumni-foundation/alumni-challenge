import pytest
from pydantic import ValidationError

from app.core.config import Settings

DATABASE_URL = "postgresql+asyncpg://u:p@localhost:5432/x"
REDIS_URL = "redis://localhost:6379/0"
STRONG_KEY = "k9Zr2vQp7LmX4wTb8NcY1hGfJdS6aUeV0oIxRtMq3Bn"
PLACEHOLDER = "change-me-dev-only-not-a-real-secret"


def _settings(environment: str, secret_key: str) -> Settings:
    return Settings(
        _env_file=None,  # type: ignore[call-arg]
        environment=environment,  # type: ignore[arg-type]
        secret_key=secret_key,  # type: ignore[arg-type]
        database_url=DATABASE_URL,  # type: ignore[arg-type]
        redis_url=REDIS_URL,  # type: ignore[arg-type]
    )


@pytest.mark.parametrize("environment", ["staging", "production"])
@pytest.mark.parametrize(
    "bad_key", [PLACEHOLDER, "Change-Me", "my-secret key", "short", "x" * 31, ""]
)
def test_a_deployed_environment_refuses_a_placeholder_or_short_secret(
    environment: str, bad_key: str
) -> None:
    with pytest.raises(ValidationError, match="SECRET_KEY"):
        _settings(environment, bad_key)


@pytest.mark.parametrize("environment", ["staging", "production"])
def test_a_deployed_environment_accepts_a_real_secret(environment: str) -> None:
    assert _settings(environment, STRONG_KEY).environment == environment


def test_development_may_use_the_placeholder() -> None:
    assert _settings("development", PLACEHOLDER).environment == "development"
