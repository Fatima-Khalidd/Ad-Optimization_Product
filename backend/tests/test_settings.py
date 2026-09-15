import pytest
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
    get_settings.cache_clear()
    assert get_settings() is get_settings()
