import pytest
from fastapi.testclient import TestClient

from app.core.settings import get_settings
from app.main import CorsMisconfiguredError, create_app

ALLOWED = "https://app.example.com"


@pytest.fixture
def cors_client(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", f"{ALLOWED},https://staging.example.com")
    get_settings.cache_clear()
    with TestClient(create_app()) as c:
        yield c
    get_settings.cache_clear()


def test_allowed_origin_gets_the_cors_header(cors_client):
    response = cors_client.get("/api/health", headers={"Origin": ALLOWED})
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == ALLOWED
    assert response.headers["access-control-allow-credentials"] == "true"


def test_second_allowed_origin_also_works(cors_client):
    response = cors_client.get("/api/health", headers={"Origin": "https://staging.example.com"})
    assert response.headers["access-control-allow-origin"] == "https://staging.example.com"


def test_disallowed_origin_gets_no_cors_header(cors_client):
    response = cors_client.get("/api/health", headers={"Origin": "https://evil.example.com"})
    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers


def test_preflight_from_a_disallowed_origin_is_not_approved(cors_client):
    response = cors_client.options(
        "/api/health",
        headers={
            "Origin": "https://evil.example.com",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert "access-control-allow-origin" not in response.headers


def test_request_id_header_is_exposed_to_the_browser(cors_client):
    response = cors_client.get("/api/health", headers={"Origin": ALLOWED})
    assert "X-Request-ID" in response.headers["access-control-expose-headers"]


def test_wildcard_cors_is_refused_in_prod(monkeypatch):
    monkeypatch.setenv("ENV", "prod")
    monkeypatch.setenv("SECRET_KEY", "p" * 32)
    # Stage 0's prod validator already rejects sqlite DATABASE_URLs in prod (see
    # test_settings.py); use a postgres URL here so this test exercises only the CORS check.
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pw@host/db")
    monkeypatch.setenv("CORS_ORIGINS", "*")
    get_settings.cache_clear()
    with pytest.raises(CorsMisconfiguredError):
        create_app()
    get_settings.cache_clear()


def test_empty_cors_list_is_refused_in_prod(monkeypatch):
    monkeypatch.setenv("ENV", "prod")
    monkeypatch.setenv("SECRET_KEY", "p" * 32)
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pw@host/db")
    monkeypatch.setenv("CORS_ORIGINS", " , ")
    get_settings.cache_clear()
    with pytest.raises(CorsMisconfiguredError):
        create_app()
    get_settings.cache_clear()
