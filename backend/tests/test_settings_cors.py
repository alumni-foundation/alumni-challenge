from typing import Any

import pytest
from pydantic import ValidationError

from app.core.config import Settings

STRONG_KEY = "k9Zr2vQp7LmX4wTb8NcY1hGfJdS6aUeV0oIxRtMq3Bn"


def _settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "environment": "development",
        "secret_key": STRONG_KEY,
        "database_url": "postgresql+asyncpg://u:p@localhost:5432/x",
        "redis_url": "redis://localhost:6379/0",
        **overrides,
    }
    return Settings(_env_file=None, **values)


def test_an_unset_value_allows_every_origin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CORS_ALLOWED_ORIGINS", raising=False)

    assert _settings().cors_allowed_origins == ["*"]


@pytest.mark.parametrize("raw", ["", "   ", "*"])
def test_a_blank_or_star_value_allows_every_origin(
    monkeypatch: pytest.MonkeyPatch, raw: str
) -> None:
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", raw)

    assert _settings().cors_allowed_origins == ["*"]


def test_a_json_list_limits_the_origins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", '["https://staging.appalumni.africa"]')

    assert _settings().cors_allowed_origins == ["https://staging.appalumni.africa"]


def test_a_value_that_is_not_json_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "https://staging.appalumni.africa")

    with pytest.raises(ValidationError, match="CORS_ALLOWED_ORIGINS"):
        _settings()
