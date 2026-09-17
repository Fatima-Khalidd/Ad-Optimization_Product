"""Proves `get_session()`'s no-implicit-commit contract (Task 4 fix round 1).

A route built on `Depends(get_session)` must commit its own writes. If it forgets, the
change is silently discarded when the request ends - the client still gets whatever status
code the route returned, so this must be caught by a test, not just by reading the code.

The throwaway route lives only in this test module (never registered on the real
`app/main.py` app), built fresh from `create_app()` plus one extra route so it still goes
through the real middleware/exception-handling stack.
"""

from typing import Annotated

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.core.db import get_session
from app.models import Client, User
from tests.api.helpers import TEST_PASSWORD


@pytest.fixture
def app_with_commitless_route(api_env: Engine) -> FastAPI:
    from app.main import create_app

    app = create_app()

    @app.post("/__test__/commitless-insert")
    def commitless_insert(session: Annotated[Session, Depends(get_session)]):
        user = User(
            email="never-committed@example.com",
            password_hash="x",
            role="client",
            is_active=True,
        )
        session.add(user)
        session.flush()  # gets an id, proves the row exists in THIS transaction
        # deliberately no session.commit()
        return {"ok": True}

    return app


def test_get_session_does_not_commit_a_forgotten_write(
    app_with_commitless_route: FastAPI, api_env: Engine
):
    http = TestClient(app_with_commitless_route)

    response = http.post("/__test__/commitless-insert")

    assert response.status_code == 200
    assert response.json() == {"ok": True}

    with Session(api_env) as verify:
        assert (
            verify.scalars(select(User).where(User.email == "never-committed@example.com")).first()
            is None
        )


def test_a_route_that_commits_explicitly_still_persists(api: TestClient, api_env: Engine):
    """Existing behaviour, unchanged: signup commits its own writes."""
    response = api.post(
        "/api/auth/signup",
        json={"email": "commits@example.com", "password": TEST_PASSWORD, "business_name": "Co"},
    )
    assert response.status_code == 201, response.text

    with Session(api_env) as verify:
        user = verify.scalars(select(User).where(User.email == "commits@example.com")).first()
        assert user is not None
        client = verify.scalars(select(Client).where(Client.user_id == user.id)).first()
        assert client is not None
