from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

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

    @model_validator(mode="after")
    def _reject_insecure_prod_defaults(self) -> "Settings":
        if self.env == "prod" and (
            self.secret_key == _DEV_SECRET or self.database_url.startswith("sqlite")
        ):
            raise ValueError("prod requires a non-default SECRET_KEY and a non-sqlite DATABASE_URL")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
