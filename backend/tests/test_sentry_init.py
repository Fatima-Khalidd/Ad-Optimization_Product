import pytest
import sentry_sdk
from fastapi.testclient import TestClient

from app.core.settings import get_settings
from app.main import create_app

FAKE_DSN = "https://publickey@o0.ingest.sentry.io/1"


@pytest.fixture
def captured_init(monkeypatch):
    """Record sentry_sdk.init kwargs instead of opening a real transport."""
    calls: list[dict] = []
    monkeypatch.setattr(sentry_sdk, "init", lambda **kwargs: calls.append(kwargs))
    yield calls
    get_settings.cache_clear()


def test_app_starts_and_serves_without_a_dsn(captured_init, monkeypatch):
    monkeypatch.delenv("SENTRY_DSN", raising=False)
    get_settings.cache_clear()
    with TestClient(create_app()) as c:
        assert c.get("/api/health").json()["status"] == "ok"
    assert captured_init == []


def test_app_starts_and_serves_with_a_dsn(captured_init, monkeypatch):
    monkeypatch.setenv("SENTRY_DSN", FAKE_DSN)
    get_settings.cache_clear()
    with TestClient(create_app()) as c:
        assert c.get("/api/health").json()["status"] == "ok"
    assert len(captured_init) == 1


def test_sentry_is_initialised_with_the_environment_and_no_pii(captured_init, monkeypatch):
    monkeypatch.setenv("SENTRY_DSN", FAKE_DSN)
    get_settings.cache_clear()
    create_app()
    kwargs = captured_init[0]
    assert kwargs["dsn"] == FAKE_DSN
    assert kwargs["environment"] == "test"
    assert kwargs["send_default_pii"] is False


def test_sentry_environment_follows_env(captured_init, monkeypatch):
    monkeypatch.setenv("SENTRY_DSN", FAKE_DSN)
    monkeypatch.setenv("ENV", "prod")
    monkeypatch.setenv("SECRET_KEY", "p" * 32)
    # Stage 0's prod validator also rejects sqlite DATABASE_URLs in prod (test_settings.py);
    # use a postgres URL so this test exercises only the Sentry environment wiring.
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pw@host/db")
    monkeypatch.setenv("CORS_ORIGINS", "https://app.example.com")
    get_settings.cache_clear()
    create_app()
    assert captured_init[0]["environment"] == "prod"


def test_an_empty_dsn_string_counts_as_off(captured_init, monkeypatch):
    monkeypatch.setenv("SENTRY_DSN", "")
    get_settings.cache_clear()
    create_app()
    assert captured_init == []
