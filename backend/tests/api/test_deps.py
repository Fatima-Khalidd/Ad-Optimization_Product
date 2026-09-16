from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token, create_refresh_token
from tests.api.helpers import make_admin, make_client, user_for


@pytest.fixture
def probe(api_env) -> TestClient:
    """A TestClient over an app with throwaway routes, so the dependencies have something
    to protect. Built exactly like the `api` fixture, plus three probe routes."""
    from app.core.deps import CurrentAdmin, CurrentClient, CurrentUser
    from app.core.rate_limit import limiter
    from app.main import create_app

    limiter.enabled = False
    application = create_app()

    @application.get("/probe/whoami")
    def whoami(user: CurrentUser):
        return {"id": user.id, "role": user.role}

    @application.get("/probe/admin-only")
    def admin_only(admin: CurrentAdmin):
        return {"admin_id": admin.id}

    @application.get("/probe/client-only")
    def client_only(current: CurrentClient):
        return {"client_id": current.id, "business_name": current.business_name}

    return TestClient(application)


def test_harness_shares_one_database_between_test_and_app(probe, db):
    user = user_for(db, make_client(db, "shared@example.com"))

    probe.cookies.set("access_token", create_access_token(user.id, "client"))
    response = probe.get("/probe/whoami")

    assert response.status_code == 200
    assert response.json() == {"id": user.id, "role": "client"}


def test_missing_cookie_is_401(probe):
    response = probe.get("/probe/whoami")

    assert response.status_code == 401
    assert response.json() == {"detail": "invalid credentials"}


def test_tampered_token_is_401(probe, db):
    user = user_for(db, make_client(db))
    token = create_access_token(user.id, "client")
    probe.cookies.set("access_token", token[:-1] + ("A" if token[-1] != "A" else "B"))

    assert probe.get("/probe/whoami").status_code == 401


def test_expired_token_is_401(probe, db):
    user = user_for(db, make_client(db))
    stale = datetime.now(UTC) - timedelta(minutes=30)
    probe.cookies.set("access_token", create_access_token(user.id, "client", now=stale))

    response = probe.get("/probe/whoami")

    assert response.status_code == 401
    assert response.json() == {"detail": "invalid credentials"}


def test_a_refresh_token_cannot_be_used_as_an_access_token(probe, db):
    user = user_for(db, make_client(db))
    probe.cookies.set("access_token", create_refresh_token(user.id))

    assert probe.get("/probe/whoami").status_code == 401


def test_deactivated_user_is_401(probe, db):
    user = user_for(db, make_client(db, "gone@example.com", is_active=False))
    probe.cookies.set("access_token", create_access_token(user.id, "client"))

    assert probe.get("/probe/whoami").status_code == 401


def test_token_for_a_deleted_user_is_401(probe):
    probe.cookies.set("access_token", create_access_token(999999, "client"))

    assert probe.get("/probe/whoami").status_code == 401


def test_client_calling_an_admin_route_is_403(probe, db):
    user = user_for(db, make_client(db, "client@example.com"))
    probe.cookies.set("access_token", create_access_token(user.id, "client"))

    response = probe.get("/probe/admin-only")

    assert response.status_code == 403
    assert response.json() == {"detail": "admin only"}


def test_admin_calling_an_admin_route_is_200(probe, db):
    admin = make_admin(db, "boss@example.com")
    probe.cookies.set("access_token", create_access_token(admin.id, "admin"))

    response = probe.get("/probe/admin-only")

    assert response.status_code == 200
    assert response.json() == {"admin_id": admin.id}


def test_admin_calling_a_client_route_is_403(probe, db):
    admin = make_admin(db, "boss2@example.com")
    probe.cookies.set("access_token", create_access_token(admin.id, "admin"))

    response = probe.get("/probe/client-only")

    assert response.status_code == 403
    assert response.json() == {"detail": "client only"}


def test_require_client_loads_that_users_own_client_row(probe, db):
    client_row = make_client(db, "a@example.com", "Lahore Leather")
    make_client(db, "b@example.com", "Other Business")
    user = user_for(db, client_row)
    probe.cookies.set("access_token", create_access_token(user.id, "client"))

    response = probe.get("/probe/client-only")

    assert response.status_code == 200
    assert response.json() == {"client_id": client_row.id, "business_name": "Lahore Leather"}


def test_role_in_the_token_does_not_override_the_database(probe, db):
    # A forged-looking token is still signed by us, so the role claim must never be trusted
    # for authorisation - only the stored User.role counts.
    user = user_for(db, make_client(db, "sneaky@example.com"))
    probe.cookies.set("access_token", create_access_token(user.id, "admin"))

    assert probe.get("/probe/admin-only").status_code == 403
