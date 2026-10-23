from typing import Any

import pytest
from pydantic import ValidationError

from app.core.config import Settings

STRONG_KEY = "k9Zr2vQp7LmX4wTb8NcY1hGfJdS6aUeV0oIxRtMq3Bn"

R2 = {
    "storage_endpoint_url": "https://example-account.r2.cloudflarestorage.com",
    "storage_access_key": "access",
    "storage_secret_key": "secret",
    "storage_bucket_name": "alumni",
}


def _settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "environment": "development",
        "secret_key": STRONG_KEY,
        "database_url": "postgresql+asyncpg://u:p@localhost:5432/x",
        "redis_url": "redis://localhost:6379/0",
        **overrides,
    }
    return Settings(_env_file=None, **values)


def test_local_disk_is_fine_in_development() -> None:
    assert _settings().storage_backend == "local"


def test_production_refuses_local_disk() -> None:
    with pytest.raises(ValidationError, match="STORAGE_BACKEND=r2"):
        _settings(environment="production")


def test_production_accepts_object_storage() -> None:
    assert _settings(environment="production", storage_backend="r2", **R2).storage_backend == "r2"


@pytest.mark.parametrize("missing", list(R2))
def test_object_storage_needs_every_setting(missing: str) -> None:
    settings = {k: v for k, v in R2.items() if k != missing}

    with pytest.raises(ValidationError, match=missing.upper()):
        _settings(storage_backend="r2", **settings)


def test_staging_may_use_local_disk_for_a_trial_run() -> None:
    assert _settings(environment="staging").storage_backend == "local"
