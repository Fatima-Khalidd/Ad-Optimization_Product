import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

# Make every test run with test settings regardless of the developer's .env.
os.environ["ENV"] = "test"
os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["SECRET_KEY"] = "test-secret"


@pytest.fixture
def client():
    from app.core.settings import get_settings
    from app.main import create_app

    get_settings.cache_clear()
    with TestClient(create_app()) as c:
        yield c


@pytest.fixture
def session():
    import app.models  # noqa: F401  (registers every table on Base.metadata)
    from app.core.db import Base

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s
    Base.metadata.drop_all(engine)
