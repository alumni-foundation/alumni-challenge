from functools import lru_cache
from typing import Literal

from pydantic import PostgresDsn, RedisDsn, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

MIN_DEPLOYED_SECRET_KEY_LENGTH = 32
# Values that have appeared in .env.example or in docs. Matched case-insensitively.
KNOWN_PLACEHOLDER_SECRET_KEYS = {"my-secret key"}
PLACEHOLDER_SECRET_KEY_PREFIX = "change-me"


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

    # File storage. "local" writes to disk (development and tests only). "r2" is any
    # S3-compatible object store: Cloudflare R2 in production, MinIO on a developer's machine.
    storage_backend: Literal["local", "r2"] = "local"
    storage_local_path: str = "var/uploads"

    # Object storage settings, required when storage_backend is "r2". The bucket must be private.
    storage_endpoint_url: str | None = None
    storage_access_key: str | None = None
    storage_secret_key: SecretStr | None = None
    storage_bucket_name: str | None = None

    @model_validator(mode="after")
    def _check_storage_settings(self) -> "Settings":
        if self.storage_backend == "r2":
            missing = [
                name
                for name, value in (
                    ("STORAGE_ENDPOINT_URL", self.storage_endpoint_url),
                    ("STORAGE_ACCESS_KEY", self.storage_access_key),
                    ("STORAGE_SECRET_KEY", self.storage_secret_key),
                    ("STORAGE_BUCKET_NAME", self.storage_bucket_name),
                )
                if not value
            ]
            if missing:
                raise ValueError(
                    f"STORAGE_BACKEND=r2 needs these settings too: {', '.join(missing)}."
                )
        if self.environment == "production" and self.storage_backend == "local":
            # A container's disk is wiped on every redeploy, so uploads would silently vanish.
            raise ValueError("Production must use STORAGE_BACKEND=r2, not local disk.")
        return self

    @model_validator(mode="after")
    def _refuse_placeholder_secret_outside_development(self) -> "Settings":
        """
        The repo is public and .env.example is copied to .env, so a staging or production
        deploy that forgot to set its own SECRET_KEY would sign tokens with a key anyone
        can read. Refuse to start rather than run that way.
        """
        if self.environment == "development":
            return self
        key = self.secret_key.get_secret_value()
        lowered = key.strip().lower()
        if (
            lowered.startswith(PLACEHOLDER_SECRET_KEY_PREFIX)
            or lowered in KNOWN_PLACEHOLDER_SECRET_KEYS
            or len(key) < MIN_DEPLOYED_SECRET_KEY_LENGTH
        ):
            raise ValueError(
                f"SECRET_KEY is a placeholder or shorter than {MIN_DEPLOYED_SECRET_KEY_LENGTH} "
                f"characters; set a real random secret before running in {self.environment}."
            )
        return self

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    """Cached so settings are parsed once per process, not per request."""
    return Settings()
