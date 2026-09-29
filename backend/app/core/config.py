from functools import lru_cache
from typing import Literal

from pydantic import PostgresDsn, RedisDsn, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Central configuration. Every value comes from the environment —
    never hardcode secrets or environment-specific values here.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = False

    # App
    app_name: str = "Alumni Challenge API"
    api_v1_prefix: str = "/api/v1"

    # Security
    secret_key: SecretStr
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30
    jwt_algorithm: str = "HS256"

    # Database
    database_url: PostgresDsn
    database_pool_size: int = 10
    database_max_overflow: int = 5

    # Redis
    redis_url: RedisDsn

    # CORS
    cors_allowed_origins: list[str] = ["http://localhost:3000"]

    # Used only to build links inside emails (verification, password reset).
    # Never used for redirects or trust decisions — those never depend on this value.
    frontend_url: str = "http://localhost:3000"

    # Observability
    sentry_dsn: str | None = None

    # Object storage (Cloudflare R2, S3-compatible)
    storage_endpoint_url: str | None = None
    storage_access_key: str | None = None
    storage_secret_key: SecretStr | None = None
    storage_bucket_name: str | None = None

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    """Cached so settings are parsed once per process, not per request."""
    return Settings()
