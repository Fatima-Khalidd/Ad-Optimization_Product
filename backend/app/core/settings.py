import os
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator
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
    new_client_base_fee: Decimal = Field(default=Decimal("0"), ge=0)
    new_client_performance_fee_pct: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    # Invoices are in USD; recovered waste is measured in the client's PKR ad spend. The
    # performance fee is converted at this rate, frozen onto each invoice when it is drafted.
    pkr_per_usd: Decimal = Field(default=Decimal("276"), gt=0)

    # --- card payments in USD (Lemon Squeezy, app/payments/lemonsqueezy.py) ---
    # Off until all four are set; the bank-transfer route keeps working either way.
    lemonsqueezy_api_key: str | None = None
    lemonsqueezy_store_id: str | None = None
    # A product variant whose price is overridden per checkout with the invoice's amount.
    lemonsqueezy_variant_id: str | None = None
    lemonsqueezy_webhook_secret: str | None = None
    # The frontend's public origin, where the checkout sends the client back afterwards.
    public_app_url: str | None = None

    @property
    def card_payments_enabled(self) -> bool:
        return all(
            (
                self.lemonsqueezy_api_key,
                self.lemonsqueezy_store_id,
                self.lemonsqueezy_variant_id,
                self.lemonsqueezy_webhook_secret,
            )
        )

    # --- file storage (docs/PLAN.md section 1 #9) ---
    storage_backend: str = "local"  # "supabase" arrives in Stage 8
    storage_root: str = "./storage"
    max_upload_mb: int = 20

    # Auth (docs/PLAN.md section 5 "Auth details").
    access_token_minutes: int = 15
    refresh_token_days: int = 7
    # Off by default so http://127.0.0.1 development works; never off in production.
    cookie_secure: bool = False
    auto_approve_analyses: bool = True

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

    # --- serverless hosting (Vercel) ---------------------------------------
    # Vercel sets VERCEL=1 in every build and function, so a Vercel deploy is detected with
    # no configuration; SERVERLESS=true/false overrides the detection either way.
    serverless: bool = Field(default_factory=lambda: bool(os.environ.get("VERCEL")))
    # How POST /api/analyze runs the pipeline (app.services.analysis.dispatch_run).
    # Unset means "inline" when serverless - a frozen function never finishes a post-response
    # task - and "background" otherwise.
    analysis_dispatch: Literal["background", "inline"] | None = None
    # Where the login rate limiter keeps its counters. "memory://" is per process, which
    # is only correct with a single long-lived process; serverless needs a shared store,
    # e.g. Upstash Redis: rediss://default:<password>@<host>:6379
    rate_limit_storage_uri: str = "memory://"

    @model_validator(mode="after")
    def _apply_serverless_defaults(self) -> "Settings":
        if self.analysis_dispatch is None:
            self.analysis_dispatch = "inline" if self.serverless else "background"
        if self.serverless and self.storage_backend == "local":
            raise ValueError(
                "serverless functions have no persistent disk: set STORAGE_BACKEND=supabase"
            )
        return self

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
