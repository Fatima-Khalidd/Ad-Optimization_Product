"""Unit tests for app/services/auth.py - the only place a User.role is ever chosen.

Uses the `db` fixture (tests/api/conftest.py): a Session on the same bound in-memory
engine every other API test shares, so a row inserted directly via `db` is visible to a
service call that takes `db` as its own session argument.
"""

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import Client, User
from app.pipeline.config import PipelineConfig
from app.services.auth import (
    EmailTakenError,
    authenticate,
    client_for,
    create_admin,
    signup_client,
)


def test_signup_creates_a_client_user_and_a_client_row(db: Session):
    user = signup_client(db, "Owner@Example.COM", "longenough", "  Karachi Kicks  ")

    assert user.id is not None
    assert user.email == "owner@example.com"  # normalised
    assert user.role == "client"
    assert user.is_active is True
    assert user.password_hash.startswith("$argon2id$")

    client = db.scalar(select(Client).where(Client.user_id == user.id))
    assert client is not None
    assert client.business_name == "Karachi Kicks"  # trimmed


def test_signup_copies_the_pipeline_config_fee_defaults(db: Session):
    user = signup_client(db, "fees@example.com", "longenough", "Fee Co")
    client = db.scalar(select(Client).where(Client.user_id == user.id))

    defaults = PipelineConfig()
    assert client.base_fee == defaults.base_fee
    assert client.performance_fee_pct == defaults.performance_fee_pct
    # Quantised to the NUMERIC(14,2) scale so the API always renders "15000.00", not "15000".
    assert str(client.base_fee) == "15000.00"
    assert str(client.performance_fee_pct) == "20.00"


def test_signup_with_a_taken_email_raises_even_when_cased_differently(db: Session):
    signup_client(db, "dup@example.com", "longenough", "First")

    with pytest.raises(EmailTakenError):
        signup_client(db, "DUP@Example.com", "longenough", "Second")

    assert len(list(db.scalars(select(User)))) == 1


def test_signup_with_a_row_already_committed_by_someone_else_raises(db: Session):
    """The precheck is belt-and-braces; EmailTakenError must come from the DB itself.

    Insert a user directly through `db` (as another request/session would), then call
    signup_client with the same session: the precheck sees it via the shared connection,
    proving signup never gets past the unique index either way.
    """
    other = User(email="race@example.com", password_hash=hash_password("whatever"), role="client")
    db.add(other)
    db.commit()

    with pytest.raises(EmailTakenError):
        signup_client(db, "race@example.com", "longenough", "Racer Co")

    assert len(list(db.scalars(select(User)))) == 1


def test_authenticate_returns_the_user_for_the_right_password(db: Session):
    created = signup_client(db, "ok@example.com", "longenough", "OK Co")

    found = authenticate(db, "OK@example.com", "longenough")

    assert found is not None
    assert found.id == created.id


def test_authenticate_returns_none_for_a_wrong_password(db: Session):
    signup_client(db, "bad@example.com", "longenough", "Bad Co")

    assert authenticate(db, "bad@example.com", "wrongpassword") is None


def test_authenticate_returns_none_for_an_unknown_email(db: Session):
    assert authenticate(db, "nobody@example.com", "longenough") is None


def test_authenticate_returns_none_for_a_deactivated_user(db: Session):
    user = signup_client(db, "off@example.com", "longenough", "Off Co")
    user.is_active = False
    db.commit()

    assert authenticate(db, "off@example.com", "longenough") is None


def test_authenticate_runs_verify_password_for_an_unknown_email(db: Session, monkeypatch):
    """Timing side-channel guard: an unknown email must still pay for a hash verification,
    not short-circuit before touching the password hasher."""
    calls: list[tuple[str, str]] = []

    import app.services.auth as auth_module

    real_verify = auth_module.verify_password

    def spy(plain, hashed):
        calls.append((plain, hashed))
        return real_verify(plain, hashed)

    monkeypatch.setattr(auth_module, "verify_password", spy)

    assert authenticate(db, "ghost@example.com", "whatever") is None
    assert len(calls) == 1


def test_signup_reraises_a_non_email_integrity_error_unchanged(db: Session, monkeypatch):
    """A constraint failure unrelated to email uniqueness (e.g. on `clients`) must propagate
    as itself, not get mistranslated into a misleading EmailTakenError / 409 (F5)."""

    def failing_commit():
        raise IntegrityError("INSERT INTO clients ...", {}, Exception("some other constraint"))

    monkeypatch.setattr(db, "commit", failing_commit)

    with pytest.raises(IntegrityError):
        signup_client(db, "fresh@example.com", "longenough", "Fresh Co")


def test_create_admin_makes_an_admin_with_no_client_row(db: Session):
    admin = create_admin(db, "Boss@Example.com", "longenough")

    assert admin.role == "admin"
    assert admin.email == "boss@example.com"
    assert db.scalar(select(Client).where(Client.user_id == admin.id)) is None
    assert client_for(db, admin) is None


def test_create_admin_refuses_a_taken_email(db: Session):
    signup_client(db, "taken@example.com", "longenough", "Taken Co")

    with pytest.raises(EmailTakenError):
        create_admin(db, "taken@example.com", "longenough")


def test_client_for_returns_the_users_own_client(db: Session):
    a = signup_client(db, "a@example.com", "longenough", "A Co")
    signup_client(db, "b@example.com", "longenough", "B Co")

    assert client_for(db, a).business_name == "A Co"


def test_signup_never_accepts_a_role(db: Session):
    import inspect

    assert "role" not in inspect.signature(signup_client).parameters


def test_signup_is_case_insensitive_on_lookup_too(db: Session):
    """Foo@X.com and foo@x.com must collide, both at write time and at read time."""
    created = signup_client(db, "  Mixed@Case.com  ".strip(), "longenough", "Mixed Co")

    found = authenticate(db, "MIXED@case.COM", "longenough")

    assert found is not None
    assert found.id == created.id

    with pytest.raises(EmailTakenError):
        signup_client(db, "mixed@case.com", "longenough", "Other Co")
