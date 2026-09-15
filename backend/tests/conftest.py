import os

import pytest
from fastapi.testclient import TestClient

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
