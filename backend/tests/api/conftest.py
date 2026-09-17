"""Test wiring for API tests (INTERFACES.md section "Test-fixture contract").

Two rules for every test in this package:

1. Commit before issuing an HTTP request. The request handler runs on a second Session over
   the *same* connection, and closing a Session rolls back whatever is still open on that
   connection. The `make_*` helpers in `tests/api/helpers.py` all commit for you.
2. Call `db.expire_all()` before reading back a row that a request has just changed - `db`
   still holds the pre-request copy in its identity map.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.models import Client, User
from tests.api.helpers import TEST_PASSWORD, login_as, make_admin


@pytest.fixture(autouse=True)
def api_env(tmp_path: Path, monkeypatch, bound_engine: Engine) -> Engine:
    """Fresh settings plus the shared in-memory DB, for every test in tests/api/.

    Autouse, so no API test can accidentally run against an unbound engine.
    From Stage 3 on it also points LocalStorage at this test's own tmp_path, so uploads
    never touch the developer's ./storage directory.
    """
    from app.core.settings import get_settings

    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path / "storage"))
    get_settings.cache_clear()
    yield bound_engine
    get_settings.cache_clear()


@pytest.fixture
def db(api_env: Engine):
    """Direct DB access, for arranging state and for assertions."""
    with Session(api_env) as s:
        yield s


def _new_client() -> TestClient:
    """A TestClient over a fresh app on the bound engine, with the limiter disabled.

    No context manager on purpose: the app has no lifespan, and TestClient still runs
    BackgroundTasks synchronously before returning from .post()/.get(). Each call gets its
    own cookie jar, which is what lets two tenants be logged in at the same time.

    The Limiter is a module-level singleton with in-process storage; leaving it on would
    make unrelated tests fail depending on collection order. `rate_limited_client` (used
    only by tests/api/test_rate_limit.py) is the one place that turns it back on.
    """
    from app.core.rate_limit import limiter
    from app.main import create_app

    limiter.enabled = False
    return TestClient(create_app())


@pytest.fixture
def api(api_env: Engine) -> TestClient:
    """An anonymous TestClient on the bound engine. Log it in with `login_as`."""
    return _new_client()


@pytest.fixture
def rate_limited_client(api_env: Engine):
    from app.core.rate_limit import limiter

    http = _new_client()
    limiter.reset()
    limiter.enabled = True
    yield http
    limiter.enabled = False
    limiter.reset()


def _signup(email: str, business_name: str) -> TestClient:
    """A brand-new TestClient that has just signed up - so its cookie jar is logged in."""
    http = _new_client()
    response = http.post(
        "/api/auth/signup",
        json={"email": email, "password": TEST_PASSWORD, "business_name": business_name},
    )
    assert response.status_code == 201, response.text
    return http


@pytest.fixture
def client_a() -> TestClient:
    """A logged-in client (cookies set by signup). Its own cookie jar."""
    return _signup("a@example.com", "Alpha Traders")


@pytest.fixture
def client_b() -> TestClient:
    """A second, unrelated tenant - used by every isolation test."""
    return _signup("b@example.com", "Beta Traders")


@pytest.fixture
def admin_row(db: Session) -> User:
    """The admin User row. Requesting it alongside `admin_client` gives you both."""
    return make_admin(db, "admin@example.com")


@pytest.fixture
def admin_client(admin_row: User) -> TestClient:
    """A logged-in admin. Stage 6 mounts /api/admin/*; here it proves runs stay invisible."""
    http = _new_client()
    login_as(http, admin_row)
    return http


def _client_row(db: Session, email: str) -> Client:
    user = db.scalars(select(User).where(User.email == email)).one()
    return db.scalars(select(Client).where(Client.user_id == user.id)).one()


@pytest.fixture
def client_a_row(db: Session, client_a: TestClient) -> Client:
    return _client_row(db, "a@example.com")


@pytest.fixture
def client_b_row(db: Session, client_b: TestClient) -> Client:
    return _client_row(db, "b@example.com")
