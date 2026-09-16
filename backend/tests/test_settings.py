from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.settings import Settings, get_settings


def test_settings_reads_database_url_from_environment(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./from-env.db")
    monkeypatch.setenv("SECRET_KEY", "test-secret")
    monkeypatch.setenv("ENV", "test")

    settings = Settings(_env_file=None)

    assert settings.database_url == "sqlite:///./from-env.db"
    assert settings.secret_key == "test-secret"
    assert settings.env == "test"


def test_settings_rejects_unknown_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./x.db")
    monkeypatch.setenv("SECRET_KEY", "s")
    monkeypatch.setenv("ENV", "staging")

    with pytest.raises(ValueError):
        Settings(_env_file=None)


def test_get_settings_is_cached(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./x.db")
    monkeypatch.setenv("SECRET_KEY", "s")
    assert get_settings() is get_settings()


def test_prod_rejects_default_secret_key(monkeypatch):
    monkeypatch.setenv("ENV", "prod")
    monkeypatch.setenv("SECRET_KEY", "dev-only-insecure-secret")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pw@host/db")

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_prod_rejects_sqlite_database_url(monkeypatch):
    monkeypatch.setenv("ENV", "prod")
    monkeypatch.setenv("SECRET_KEY", "a-real-production-secret")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./prod.db")

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_prod_accepts_real_secret_and_postgres_url(monkeypatch):
    monkeypatch.setenv("ENV", "prod")
    monkeypatch.setenv("SECRET_KEY", "a-real-production-secret")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pw@host/db")

    settings = Settings(_env_file=None)

    assert settings.env == "prod"
    assert settings.database_url == "postgresql+psycopg://user:pw@host/db"


def test_env_file_points_at_backend_dotenv():
    env_file = Path(Settings.model_config["env_file"])

    assert env_file.name == ".env"
    assert env_file.parent.name == "backend"
