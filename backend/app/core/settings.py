from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

_DEV_SECRET = "dev-only-insecure-secret"
_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    """All runtime configuration. Values come from environment variables or backend/.env."""

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE), env_file_encoding="utf-8", extra="ignore"
    )

    env: Literal["dev", "test", "prod"] = "dev"
    database_url: str = "sqlite:///./dev.db"
    secret_key: str = _DEV_SECRET

    # --- payments (docs/PLAN.md section 6, Stage 7) ---
    payment_provider: str = "manual"
    max_proof_mb: int = 5

    # --- file storage (docs/PLAN.md section 1 #9) ---
    storage_backend: str = "local"  # "supabase" arrives in Stage 8
    storage_root: str = "./storage"
    max_upload_mb: int = 20

    # Auth (docs/PLAN.md section 5 "Auth details").
    access_token_minutes: int = 15
    refresh_token_days: int = 7
    # Off by default so http://127.0.0.1 development works; never off in production.
    cookie_secure: bool = False

    @model_validator(mode="after")
    def _reject_insecure_prod_defaults(self) -> "Settings":
        if self.env == "prod" and (
            self.secret_key == _DEV_SECRET or self.database_url.startswith("sqlite")
        ):
            raise ValueError("prod requires a non-default SECRET_KEY and a non-sqlite DATABASE_URL")
        if self.env == "prod" and len(self.secret_key) < 32:
            raise ValueError("prod requires a SECRET_KEY of at least 32 characters")
        return self

    @model_validator(mode="after")
    def _force_secure_cookies_in_prod(self) -> "Settings":
        if self.env == "prod":
            self.cookie_secure = True
        return self

    # --- Stage 8: hardening & deploy -------------------------------------
    sentry_dsn: str | None = None
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:3000"]
    max_request_mb: int = 25
    supabase_url: str | None = None
    supabase_service_key: str | None = None
    storage_bucket: str = "ad-optimizer"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_cors_origins(cls, value: object) -> object:
        """CORS_ORIGINS is a comma-separated list, not JSON. Trailing slashes are dropped
        because browsers send `Origin` without one and Starlette compares exact strings."""
        if isinstance(value, str):
            return [part.strip().rstrip("/") for part in value.split(",") if part.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
