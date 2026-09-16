"""Row builders and login helpers shared by every test under tests/api/.

Columns are exactly docs/PLAN.md section 4. Every builder COMMITS, because the request
handler runs on its own Session over the shared connection and only sees committed rows.
Import them as `from tests.api.helpers import make_client, login_as` - that resolves because
pytest is always run as `.venv/Scripts/python -m pytest` from `backend/`.
"""

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import Client, User

TEST_PASSWORD = "correct horse battery staple"


def login_as(api: TestClient, user: User) -> None:
    """Log this TestClient in as `user`, through the real login route.

    Works for any user built by `make_client` / `make_admin`, because both hash
    TEST_PASSWORD. Cookies land in the client's jar, so every later call is authenticated.
    """
    response = api.post("/api/auth/login", json={"email": user.email, "password": TEST_PASSWORD})
    assert response.status_code == 200, response.text


def user_for(db: Session, client: Client) -> User:
    """The login row behind a Client (the models declare no relationships)."""
    user = db.get(User, client.user_id)
    assert user is not None
    return user


def make_client(
    db: Session,
    email: str = "client@example.com",
    business_name: str = "Biz",
    *,
    is_active: bool = True,
    base_fee: Decimal = Decimal("15000.00"),
    performance_fee_pct: Decimal = Decimal("20.00"),
    config_overrides: dict | None = None,
) -> Client:
    """A committed User(role="client") + its Client row. Returns the Client."""
    user = User(
        email=email.lower(),
        password_hash=hash_password(TEST_PASSWORD),
        role="client",
        is_active=is_active,
    )
    db.add(user)
    db.flush()
    client = Client(
        user_id=user.id,
        business_name=business_name,
        base_fee=base_fee,
        performance_fee_pct=performance_fee_pct,
        config_overrides=config_overrides or {},
    )
    db.add(client)
    db.commit()
    db.refresh(client)
    return client


def make_admin(db: Session, email: str = "admin@example.com", *, is_active: bool = True) -> User:
    """A committed User(role="admin"). Admins have no Client row (docs/PLAN.md section 5)."""
    user = User(
        email=email.lower(),
        password_hash=hash_password(TEST_PASSWORD),
        role="admin",
        is_active=is_active,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
