from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, RedisDsn, SecretStr, model_validator
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
    # Password hashes running at once. Each uses 64 MiB, so this caps the memory they can take.
    password_hash_concurrency: int = Field(default=2, ge=1, le=16)

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

    # Which header carries the real visitor address when the API sits behind a proxy. Behind
    # Cloudflare use "cf-connecting-ip". Leave as "none" anywhere visitors reach the API
    # directly: those headers can be forged, and trusting them would let anyone dodge rate limits.
    trusted_client_ip_header: Literal[
        "none", "cf-connecting-ip", "x-forwarded-for", "x-visitor-ip"
    ] = "none"

    # Observability
    sentry_dsn: str | None = None
    sentry_traces_sample_rate: float = 0.1
    sentry_release: str | None = None

    # File storage. "local" writes to disk (development and tests only). "r2" is any
    # S3-compatible object store: Cloudflare R2 in production, MinIO on a developer's machine.
    storage_backend: Literal["local", "r2"] = "local"
    storage_local_path: str = "var/uploads"

    # Object storage settings, required when storage_backend is "r2". The bucket must be private.
    storage_endpoint_url: str | None = None
    storage_access_key: str | None = None
    storage_secret_key: SecretStr | None = None
    storage_bucket_name: str | None = None

    # Email. "logging" sends nothing (the default, and what tests use); "smtp" is for Mailpit in
    # development or a real relay; "resend" is the production provider.
    mail_backend: Literal["logging", "smtp", "resend"] = "logging"
    mail_from: str = "Alumni Challenge <no-reply@localhost>"
    smtp_host: str | None = None
    smtp_port: int = 1025
    smtp_username: str | None = None
    smtp_password: SecretStr | None = None
    smtp_starttls: bool = False
    resend_api_key: SecretStr | None = None

    # Signs the QR codes on event tickets. Optional in development and tests (a key is derived
    # from SECRET_KEY); production must set its own, different from SECRET_KEY.
    ticket_signing_key: SecretStr | None = None

    @model_validator(mode="after")
    def _check_mail_settings(self) -> "Settings":
        if self.mail_backend == "resend" and not self.resend_api_key:
            raise ValueError("MAIL_BACKEND=resend needs RESEND_API_KEY.")
        if self.mail_backend == "smtp" and not self.smtp_host:
            raise ValueError("MAIL_BACKEND=smtp needs SMTP_HOST.")
        if self.environment == "production":
            if self.mail_backend == "logging":
                # Nobody would ever receive a verification or reset email.
                raise ValueError("Production must send real email: set MAIL_BACKEND=resend.")
            if not self.frontend_url.startswith("https://"):
                # Links in emails are built from this. A reset link must never be plain HTTP.
                raise ValueError("Production FRONTEND_URL must start with https://.")
        return self

    @model_validator(mode="after")
    def _check_ticket_signing_key(self) -> "Settings":
        if self.environment == "production":
            key = self.ticket_signing_key.get_secret_value() if self.ticket_signing_key else ""
            if (
                len(key) < MIN_DEPLOYED_SECRET_KEY_LENGTH
                or key == self.secret_key.get_secret_value()
            ):
                raise ValueError(
                    "Production needs TICKET_SIGNING_KEY: at least "
                    f"{MIN_DEPLOYED_SECRET_KEY_LENGTH} random characters, "
                    "different from SECRET_KEY."
                )
        return self

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
