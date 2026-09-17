from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.core.security import create_access_token, create_refresh_token
from app.models import Client, User
from tests.api.helpers import TEST_PASSWORD, login_as, make_admin, make_client, user_for

SIGNUP = {
    "email": "owner@example.com",
    "password": "longenough",
    "business_name": "Karachi Kicks",
}


def _set_cookie_headers(response):
    return response.headers.get_list("set-cookie")


def test_signup_returns_201_with_the_me_shape_and_both_cookies(api, db):
    response = api.post("/api/auth/signup", json=SIGNUP)

    assert response.status_code == 201
    body = response.json()
    assert set(body) == {"user", "client"}
    assert set(body["user"]) == {"id", "email", "role", "created_at"}
    assert body["user"]["email"] == "owner@example.com"
    assert body["user"]["role"] == "client"
    assert "password" not in str(body)
    assert set(body["client"]) == {"id", "business_name", "base_fee", "performance_fee_pct"}
    assert body["client"]["business_name"] == "Karachi Kicks"
    # pydantic v2 renders Decimal as a JSON string.
    assert body["client"]["base_fee"] == "15000.00"
    assert body["client"]["performance_fee_pct"] == "20.00"

    assert api.cookies.get("access_token")
    assert api.cookies.get("refresh_token")
    headers = _set_cookie_headers(response)
    assert any("access_token=" in h for h in headers)
    for header in headers:
        assert "HttpOnly" in header
        assert "samesite=lax" in header.lower()
        assert "Path=/" in header
        assert "; Secure" not in header  # cookie_secure is False when ENV=test


def test_signup_ignores_a_role_field_and_still_creates_a_client(api, db):
    response = api.post("/api/auth/signup", json={**SIGNUP, "role": "admin"})

    assert response.status_code == 201
    assert response.json()["user"]["role"] == "client"

    user = db.scalar(select(User).where(User.email == "owner@example.com"))
    assert user.role == "client"
    assert db.scalar(select(Client).where(Client.user_id == user.id)) is not None
    assert db.scalar(select(User).where(User.role == "admin")) is None


def test_signup_with_a_taken_email_returns_409(api, db):
    make_client(db, "owner@example.com")

    response = api.post("/api/auth/signup", json=SIGNUP)

    assert response.status_code == 409
    assert response.json() == {"detail": "email already registered"}


def test_signup_with_a_short_password_returns_422(api):
    response = api.post("/api/auth/signup", json={**SIGNUP, "password": "short12"})

    assert response.status_code == 422


def test_login_with_a_bad_password_returns_401_and_sets_no_cookie(api, db):
    make_client(db, "owner@example.com")

    response = api.post(
        "/api/auth/login", json={"email": "owner@example.com", "password": "wrong-password"}
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "invalid credentials"}
    assert api.cookies.get("access_token") is None


def test_login_with_an_unknown_email_returns_401(api):
    response = api.post(
        "/api/auth/login", json={"email": "nobody@example.com", "password": TEST_PASSWORD}
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "invalid credentials"}


def test_login_succeeds_and_me_returns_the_same_shape(api, db):
    client_row = make_client(db, "owner@example.com")
    user = user_for(db, client_row)

    login = api.post(
        "/api/auth/login", json={"email": "Owner@Example.com", "password": TEST_PASSWORD}
    )

    assert login.status_code == 200
    assert login.json()["user"]["id"] == user.id
    assert login.json()["client"]["id"] == client_row.id

    me = api.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json() == login.json()


def test_me_for_an_admin_has_a_null_client(api, db):
    login_as(api, make_admin(db, "boss@example.com"))

    body = api.get("/api/auth/me").json()

    assert body["user"]["role"] == "admin"
    assert body["client"] is None


def test_me_without_a_cookie_returns_401(api):
    response = api.get("/api/auth/me")

    assert response.status_code == 401
    assert response.json() == {"detail": "invalid credentials"}


def test_me_with_an_expired_token_returns_401(api, db):
    user = user_for(db, make_client(db, "owner@example.com"))
    stale = datetime.now(UTC) - timedelta(minutes=30)
    api.cookies.set("access_token", create_access_token(user.id, "client", now=stale))

    response = api.get("/api/auth/me")

    assert response.status_code == 401
    assert response.json() == {"detail": "invalid credentials"}


def test_refresh_rotates_both_cookies_and_keeps_the_session_alive(api, db):
    make_client(db, "owner@example.com")
    api.post("/api/auth/login", json={"email": "owner@example.com", "password": TEST_PASSWORD})
    old_access = api.cookies.get("access_token")
    old_refresh = api.cookies.get("refresh_token")

    response = api.post("/api/auth/refresh")

    assert response.status_code == 200
    assert response.json()["user"]["email"] == "owner@example.com"
    assert api.cookies.get("access_token") != old_access
    assert api.cookies.get("refresh_token") != old_refresh
    assert api.get("/api/auth/me").status_code == 200


def test_refresh_without_a_cookie_returns_401(api):
    response = api.post("/api/auth/refresh")

    assert response.status_code == 401
    assert response.json() == {"detail": "invalid credentials"}


def test_refresh_refuses_an_access_token(api, db):
    user = user_for(db, make_client(db, "owner@example.com"))
    api.cookies.set("refresh_token", create_access_token(user.id, "client"))

    assert api.post("/api/auth/refresh").status_code == 401


def test_refresh_refuses_an_expired_refresh_token(api, db):
    user = user_for(db, make_client(db, "owner@example.com"))
    stale = datetime.now(UTC) - timedelta(days=30)
    api.cookies.set("refresh_token", create_refresh_token(user.id, now=stale))

    assert api.post("/api/auth/refresh").status_code == 401


def test_refresh_for_a_deactivated_user_returns_401(api, db):
    client_row = make_client(db, "owner@example.com")
    user = user_for(db, client_row)
    api.post("/api/auth/login", json={"email": "owner@example.com", "password": TEST_PASSWORD})

    user.is_active = False
    db.commit()

    response = api.post("/api/auth/refresh")

    assert response.status_code == 401
    assert response.json() == {"detail": "invalid credentials"}


def test_logout_clears_both_cookies_and_me_then_fails(api, db):
    make_client(db, "owner@example.com")
    api.post("/api/auth/login", json={"email": "owner@example.com", "password": TEST_PASSWORD})
    assert api.get("/api/auth/me").status_code == 200

    response = api.post("/api/auth/logout")

    assert response.status_code == 204
    headers = _set_cookie_headers(response)
    assert any("access_token=" in h and "Max-Age=0" in h for h in headers)
    assert any("refresh_token=" in h and "Max-Age=0" in h for h in headers)
    assert api.cookies.get("access_token") is None
    assert api.cookies.get("refresh_token") is None
    assert api.get("/api/auth/me").status_code == 401


def test_health_still_works(api):
    assert api.get("/api/health").json() == {"status": "ok", "env": "test"}
