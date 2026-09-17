"""Every auth-related database write. The only place a User.role is ever chosen."""

from decimal import Decimal
from functools import lru_cache

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models import Client, User
from app.pipeline.config import PipelineConfig

# NUMERIC(14,2) - quantise on the way in so Decimals match what the DB gives back.
MONEY_SCALE = Decimal("0.01")


class EmailTakenError(Exception):
    """The email already belongs to a user."""


def _normalize(email: str) -> str:
    return email.strip().lower()


def _by_email(session: Session, email: str) -> User | None:
    return session.scalar(select(User).where(User.email == _normalize(email)))


@lru_cache(maxsize=1)
def _dummy_hash() -> str:
    """A real hash to verify against when the email is unknown, so a missing account and a
    wrong password take the same amount of time."""
    return hash_password("no-such-user-placeholder")


def _create_user(session: Session, email: str, password: str, role: str) -> User:
    """Insert the User row. Raises EmailTakenError from BOTH the pre-check select and the
    unique index on users.email - the pre-check is only an optimisation, the flush is the
    real guarantee (docs/PLAN.md tenant-isolation notes: no email race can slip through)."""
    normalized = _normalize(email)
    if _by_email(session, normalized) is not None:
        raise EmailTakenError(normalized)
    user = User(email=normalized, password_hash=hash_password(password), role=role, is_active=True)
    session.add(user)
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise EmailTakenError(normalized) from exc
    return user


def signup_client(session: Session, email: str, password: str, business_name: str) -> User:
    """Create a client User plus its Client row. There is deliberately no role parameter."""
    user = _create_user(session, email, password, "client")
    defaults = PipelineConfig()
    session.add(
        Client(
            user_id=user.id,
            business_name=business_name.strip(),
            base_fee=defaults.base_fee.quantize(MONEY_SCALE),
            performance_fee_pct=defaults.performance_fee_pct.quantize(MONEY_SCALE),
        )
    )
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        # Only translate to EmailTakenError when the email row actually landed - i.e. the
        # failure really was the users.email race this guards against (docs/PLAN.md
        # tenant-isolation notes). Any other constraint failure (e.g. on `clients`) must
        # surface as itself, not a misleading 409 "email already registered".
        if _by_email(session, email) is not None:
            raise EmailTakenError(_normalize(email)) from exc
        raise
    session.refresh(user)
    return user


def create_admin(session: Session, email: str, password: str) -> User:
    """Used only by scripts/create_admin.py. Signup can never reach this (docs/PLAN.md s5)."""
    user = _create_user(session, email, password, "admin")
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise EmailTakenError(_normalize(email)) from exc
    session.refresh(user)
    return user


def authenticate(session: Session, email: str, password: str) -> User | None:
    """None for an unknown email, a wrong password, or an inactive user. verify_password
    always runs - even against a dummy hash when the email is unknown - so a missing
    account and a wrong password take about the same amount of time."""
    user = _by_email(session, email)
    if user is None:
        verify_password(password, _dummy_hash())
        return None
    if not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def client_for(session: Session, user: User) -> Client | None:
    return session.scalar(select(Client).where(Client.user_id == user.id))
