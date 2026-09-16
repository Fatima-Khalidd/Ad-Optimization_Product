"""Test wiring for API tests (INTERFACES.md section "Test-fixture contract").

Two rules for every test in this package:

1. Commit before issuing an HTTP request. The request handler runs on a second Session over
   the *same* connection, and closing a Session rolls back whatever is still open on that
   connection. The `make_*` helpers in `tests/api/helpers.py` all commit for you.
2. Call `db.expire_all()` before reading back a row that a request has just changed - `db`
   still holds the pre-request copy in its identity map.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session


@pytest.fixture(autouse=True)
def api_env(bound_engine: Engine) -> Engine:
    """Fresh settings plus the shared in-memory DB, for every test in tests/api/.

    Autouse, so no API test can accidentally run against an unbound engine.
    """
    from app.core.settings import get_settings

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
