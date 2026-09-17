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
    monkeypatch.setenv("SECRET_KEY", "a-real-production-secret-32chars+")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pw@host/db")

    settings = Settings(_env_file=None)

    assert settings.env == "prod"
    assert settings.database_url == "postgresql+psycopg://user:pw@host/db"


def test_prod_rejects_secret_key_shorter_than_32_chars(monkeypatch):
    monkeypatch.setenv("ENV", "prod")
    monkeypatch.setenv("SECRET_KEY", "a" * 31)
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pw@host/db")

    with pytest.raises(ValidationError, match="32"):
        Settings(_env_file=None)


def test_prod_accepts_secret_key_of_exactly_32_chars(monkeypatch):
    monkeypatch.setenv("ENV", "prod")
    monkeypatch.setenv("SECRET_KEY", "a" * 32)
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pw@host/db")

    settings = Settings(_env_file=None)

    assert settings.secret_key == "a" * 32


def test_dev_allows_a_short_secret_key(monkeypatch):
    monkeypatch.setenv("ENV", "dev")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./x.db")
    monkeypatch.setenv("SECRET_KEY", "s")

    settings = Settings(_env_file=None)

    assert settings.secret_key == "s"


def test_env_file_points_at_backend_dotenv():
    env_file = Path(Settings.model_config["env_file"])

    assert env_file.name == ".env"
    assert env_file.parent.name == "backend"


def test_auth_settings_have_spec_defaults(monkeypatch):
    monkeypatch.setenv("ENV", "dev")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./x.db")
    monkeypatch.setenv("SECRET_KEY", "s")

    settings = Settings(_env_file=None)

    assert settings.access_token_minutes == 15
    assert settings.refresh_token_days == 7
    assert settings.cookie_secure is False


def test_cookie_secure_is_forced_on_in_prod(monkeypatch):
    # Non-sqlite URL and non-default secret so this satisfies the existing
    # prod-safety validator (test_prod_rejects_* above) and isolates the
    # cookie_secure-forcing behavior under test.
    monkeypatch.setenv("ENV", "prod")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pw@host/db")
    monkeypatch.setenv("SECRET_KEY", "a-real-production-secret-32chars+")
    monkeypatch.setenv("COOKIE_SECURE", "false")  # must not be able to weaken prod

    assert Settings(_env_file=None).cookie_secure is True


def test_token_lifetimes_come_from_the_environment(monkeypatch):
    monkeypatch.setenv("ENV", "dev")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./x.db")
    monkeypatch.setenv("SECRET_KEY", "s")
    monkeypatch.setenv("ACCESS_TOKEN_MINUTES", "30")
    monkeypatch.setenv("REFRESH_TOKEN_DAYS", "14")
    monkeypatch.setenv("COOKIE_SECURE", "true")

    settings = Settings(_env_file=None)

    assert settings.access_token_minutes == 30
    assert settings.refresh_token_days == 14
    assert settings.cookie_secure is True
