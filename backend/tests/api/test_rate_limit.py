"""The only module that turns the limiter on. Everywhere else `_new_client()` in
tests/api/conftest.py disables it, because the Limiter is a process-wide singleton with
in-memory storage and would otherwise leak across tests depending on collection order."""

from app.core.rate_limit import client_ip_key
from tests.api.helpers import TEST_PASSWORD, make_client


def test_the_sixth_login_in_a_minute_is_rejected_with_429(rate_limited_client, db):
    make_client(db, "rate@example.com")
    body = {"email": "rate@example.com", "password": "wrong-password"}

    first_five = [
        rate_limited_client.post("/api/auth/login", json=body).status_code for _ in range(5)
    ]
    sixth = rate_limited_client.post("/api/auth/login", json=body)

    assert first_five == [401, 401, 401, 401, 401]
    assert sixth.status_code == 429
    assert sixth.json() == {"detail": "too many requests"}


def test_a_correct_password_is_also_counted(rate_limited_client, db):
    make_client(db, "rate2@example.com")
    good = {"email": "rate2@example.com", "password": TEST_PASSWORD}

    codes = [rate_limited_client.post("/api/auth/login", json=good).status_code for _ in range(6)]

    assert codes == [200, 200, 200, 200, 200, 429]


def test_signup_and_me_are_not_rate_limited(rate_limited_client, db):
    make_client(db, "free@example.com")

    for index in range(8):
        response = rate_limited_client.post(
            "/api/auth/signup",
            json={
                "email": f"new{index}@example.com",
                "password": "longenough",
                "business_name": "New Co",
            },
        )
        assert response.status_code == 201
        assert rate_limited_client.get("/api/auth/me").status_code == 200


def test_the_limiter_is_off_for_ordinary_tests(api, db):
    make_client(db, "norate@example.com")
    body = {"email": "norate@example.com", "password": "wrong-password"}

    codes = [api.post("/api/auth/login", json=body).status_code for _ in range(8)]

    assert codes == [401] * 8


# --------------------------------------------------------------------------- F1: client_ip_key


def _request(headers: dict[str, str] | None = None, peer: str = "10.9.9.9"):
    """A minimal Starlette Request carrying only the headers client_ip_key reads, plus a
    fake direct-connection peer (what get_remote_address falls back to)."""
    from starlette.requests import Request

    raw_headers = [
        (k.lower().encode("latin-1"), v.encode("latin-1")) for k, v in (headers or {}).items()
    ]
    scope = {
        "type": "http",
        "headers": raw_headers,
        "client": (peer, 12345),
    }
    return Request(scope)


def test_client_ip_key_takes_the_first_hop_of_x_forwarded_for():
    request = _request({"X-Forwarded-For": "1.2.3.4, 10.0.0.1"})
    assert client_ip_key(request) == "1.2.3.4"


def test_client_ip_key_falls_back_to_the_peer_when_the_header_is_absent():
    request = _request(peer="203.0.113.5")
    assert client_ip_key(request) == "203.0.113.5"


def test_client_ip_key_falls_back_to_the_peer_when_the_header_is_garbage():
    request = _request({"X-Forwarded-For": "not-an-ip"}, peer="203.0.113.5")
    assert client_ip_key(request) == "203.0.113.5"


def test_two_forwarded_ips_get_independent_rate_limit_buckets(rate_limited_client, db):
    make_client(db, "bucket@example.com")
    body = {"email": "bucket@example.com", "password": "wrong-password"}

    first_five = [
        rate_limited_client.post(
            "/api/auth/login", json=body, headers={"X-Forwarded-For": "9.9.9.1"}
        ).status_code
        for _ in range(5)
    ]
    sixth_same_ip = rate_limited_client.post(
        "/api/auth/login", json=body, headers={"X-Forwarded-For": "9.9.9.1"}
    )
    still_ok_other_ip = rate_limited_client.post(
        "/api/auth/login", json=body, headers={"X-Forwarded-For": "9.9.9.2"}
    )

    assert first_five == [401, 401, 401, 401, 401]
    assert sixth_same_ip.status_code == 429
    assert still_ok_other_ip.status_code == 401
