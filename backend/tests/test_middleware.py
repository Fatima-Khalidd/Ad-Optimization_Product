import json
import logging

import pytest
from fastapi.testclient import TestClient

from app.core.middleware import REQUEST_ID_HEADER, JsonFormatter, request_id_var
from app.core.settings import get_settings
from app.main import create_app


@pytest.fixture
def build_app(monkeypatch):
    """Build a fresh app with specific env vars, then restore the settings cache."""

    def build(**env: str):
        for key, value in env.items():
            monkeypatch.setenv(key, value)
        get_settings.cache_clear()
        return create_app()

    yield build
    get_settings.cache_clear()


def test_security_headers_are_on_every_response(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    policy = response.headers["Permissions-Policy"]
    assert "camera=()" in policy
    assert "microphone=()" in policy
    assert "geolocation=()" in policy


def test_hsts_is_absent_outside_prod(client):
    assert "Strict-Transport-Security" not in client.get("/api/health").headers


def test_hsts_is_present_in_prod(build_app):
    # Stage 0's prod validator rejects sqlite DATABASE_URLs in prod, so this must supply a
    # postgres URL to exercise only the HSTS behaviour under test.
    app = build_app(
        ENV="prod",
        SECRET_KEY="p" * 32,
        CORS_ORIGINS="https://app.example.com",
        DATABASE_URL="postgresql+psycopg://user:pw@host/db",
    )
    with TestClient(app) as prod_client:
        header = prod_client.get("/api/health").headers["Strict-Transport-Security"]
    assert header == "max-age=31536000; includeSubDomains"


def test_request_id_is_generated_when_the_client_sends_none(client):
    value = client.get("/api/health").headers[REQUEST_ID_HEADER]
    assert len(value) == 32
    int(value, 16)  # raises ValueError if it is not hex


def test_request_id_is_echoed_when_the_client_sends_one(client):
    response = client.get("/api/health", headers={REQUEST_ID_HEADER: "abc-123_XYZ"})
    assert response.headers[REQUEST_ID_HEADER] == "abc-123_XYZ"


def test_a_hostile_request_id_is_replaced_not_echoed(client):
    hostile = "not a valid id " + "x" * 200
    response = client.get("/api/health", headers={REQUEST_ID_HEADER: hostile})
    assert response.headers[REQUEST_ID_HEADER] != hostile
    assert len(response.headers[REQUEST_ID_HEADER]) == 32


def test_every_request_gets_its_own_id(client):
    first = client.get("/api/health").headers[REQUEST_ID_HEADER]
    second = client.get("/api/health").headers[REQUEST_ID_HEADER]
    assert first != second


def test_json_formatter_emits_one_parseable_object():
    record = logging.LogRecord(
        name="app.access",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="request",
        args=(),
        exc_info=None,
    )
    record.method = "GET"
    record.path = "/api/health"
    record.status = 200
    record.duration_ms = 1.25
    record.request_id = "deadbeef"

    payload = json.loads(JsonFormatter().format(record))

    assert payload["level"] == "INFO"
    assert payload["logger"] == "app.access"
    assert payload["msg"] == "request"
    assert payload["method"] == "GET"
    assert payload["path"] == "/api/health"
    assert payload["status"] == 200
    assert payload["duration_ms"] == 1.25
    assert payload["request_id"] == "deadbeef"
    assert payload["ts"].endswith("Z")


def test_json_formatter_never_emits_a_newline_inside_a_record():
    record = logging.LogRecord(
        name="app",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg="line one\nline two",
        args=(),
        exc_info=None,
    )
    assert "\n" not in JsonFormatter().format(record)


def test_request_id_var_defaults_outside_a_request():
    assert request_id_var.get() == "-"


def test_access_line_is_logged_with_the_request_id(client, caplog):
    with caplog.at_level(logging.INFO, logger="app.access"):
        response = client.get("/api/health")
    record = next(r for r in caplog.records if r.name == "app.access")
    assert record.request_id == response.headers[REQUEST_ID_HEADER]
    assert record.status == 200
    assert record.path == "/api/health"


def test_body_within_the_cap_is_accepted(build_app):
    app = build_app(MAX_REQUEST_MB="1")
    with TestClient(app) as sized_client:
        response = sized_client.post("/api/health", content=b"0" * 1024)
    # /api/health has no POST handler, so anything other than 413 proves we got through.
    assert response.status_code == 405


def test_body_over_the_cap_is_rejected_with_413(build_app):
    app = build_app(MAX_REQUEST_MB="1")
    with TestClient(app) as sized_client:
        response = sized_client.post("/api/health", content=b"0" * (2 * 1024 * 1024))
    assert response.status_code == 413
    assert response.json() == {"detail": "request body too large"}


def test_413_still_carries_the_security_headers_and_a_request_id(build_app):
    app = build_app(MAX_REQUEST_MB="1")
    with TestClient(app) as sized_client:
        response = sized_client.post("/api/health", content=b"0" * (2 * 1024 * 1024))
    assert response.status_code == 413
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert len(response.headers[REQUEST_ID_HEADER]) == 32


def test_a_non_numeric_content_length_is_rejected_with_400(build_app):
    app = build_app(MAX_REQUEST_MB="1")
    with TestClient(app) as sized_client:
        response = sized_client.post(
            "/api/health", content=b"hi", headers={"Content-Length": "not-a-number"}
        )
    assert response.status_code == 400
    assert response.json() == {"detail": "invalid Content-Length"}
