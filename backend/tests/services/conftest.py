from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app.core.settings import get_settings
from app.models import Client, User


@pytest.fixture(autouse=True)
def storage_root(tmp_path: Path, monkeypatch):
    """Every service test writes its files into its own tmp_path."""
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path / "storage"))
    get_settings.cache_clear()
    yield tmp_path / "storage"
    get_settings.cache_clear()


def _make_client(session: Session, email: str, name: str) -> Client:
    user = User(email=email, password_hash="x", role="client", is_active=True)
    session.add(user)
    session.flush()
    client = Client(
        user_id=user.id,
        business_name=name,
        pricing_model="hybrid",
        base_fee=Decimal("15000"),
        performance_fee_pct=Decimal("20"),
        config_overrides={},
    )
    session.add(client)
    session.commit()
    session.refresh(client)
    return client


@pytest.fixture
def client_row(session: Session) -> Client:
    return _make_client(session, "a@example.com", "Alpha Traders")


@pytest.fixture
def other_client_row(session: Session) -> Client:
    return _make_client(session, "b@example.com", "Beta Traders")
