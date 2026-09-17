"""The only module that turns the limiter on. Everywhere else `_new_client()` in
tests/api/conftest.py disables it, because the Limiter is a process-wide singleton with
in-memory storage and would otherwise leak across tests depending on collection order."""

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
