import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

# Make every test run with test settings regardless of the developer's .env.
os.environ["ENV"] = "test"
os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["SECRET_KEY"] = "test-secret"


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    from app.core.settings import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def client():
    """Stage 0's TestClient. It has no database wiring, so only /api/health uses it."""
    from app.main import create_app

    with TestClient(create_app()) as c:
        yield c


@pytest.fixture
def bound_engine() -> Engine:
    """One in-memory DB reached by BOTH `get_session()` AND any session opened directly.

    A bare `sqlite+pysqlite:///:memory:` URL gives every *connection* its own database, so
    the app under test and the test itself would never see the same rows. StaticPool hands
    out one single connection for the whole engine, which makes the in-memory database
    shared. Registering it with `app.core.db.configure_engine()` (rather than overriding the
    FastAPI dependency) means non-request code reaches the same DB too - Stage 3's background
    task opens its own session through `app.core.db.session_scope()`.
    """
    import app.models  # noqa: F401  (registers every table on Base.metadata)
    from app.core.db import Base, configure_engine, reset_engine

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    configure_engine(engine)
    yield engine
    reset_engine()
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def session(bound_engine: Engine):
    with Session(bound_engine) as s:
        yield s
