from datetime import date
from decimal import Decimal

import pytest
from app.models import Client, Invoice, Payment, User
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

EXPECTED_TABLES = {
    "users",
    "clients",
    "ad_data_uploads",
    "analysis_runs",
    "waste_reports",
    "segment_metrics",
    "recommendations",
    "invoices",
    "payment_methods",
    "payments",
    "audit_log",
}


def test_all_tables_from_design_doc_exist(session):
    names = set(inspect(session.get_bind()).get_table_names())
    assert EXPECTED_TABLES <= names, EXPECTED_TABLES - names


def _user_and_client(session, email="owner@example.com"):
    user = User(email=email, password_hash="x", role="client")
    session.add(user)
    session.flush()
    client = Client(
        user_id=user.id,
        business_name="Karachi Kicks",
        base_fee=Decimal("15000.00"),
        performance_fee_pct=Decimal("20.00"),
    )
    session.add(client)
    session.flush()
    return user, client


def test_user_client_roundtrip_keeps_money_as_decimal(session):
    _, client = _user_and_client(session)
    session.commit()

    loaded = session.get(Client, client.id)
    assert loaded.business_name == "Karachi Kicks"
    assert loaded.base_fee == Decimal("15000.00")
    assert isinstance(loaded.base_fee, Decimal)
    assert loaded.config_overrides == {}


def test_user_email_must_be_unique(session):
    _user_and_client(session, "dup@example.com")
    session.commit()
    session.add(User(email="dup@example.com", password_hash="y", role="client"))
    with pytest.raises(IntegrityError):
        session.commit()


def test_same_transaction_ref_cannot_be_used_twice_for_one_method(session):
    _, client = _user_and_client(session)
    invoice = Invoice(
        invoice_number="INV-2026-0001",
        client_id=client.id,
        period_start=date(2026, 9, 1),
        period_end=date(2026, 9, 30),
        due_date=date(2026, 10, 7),
        base_fee=Decimal("15000.00"),
        performance_fee=Decimal("0.00"),
        total=Decimal("15000.00"),
    )
    session.add(invoice)
    session.flush()

    def payment():
        return Payment(
            invoice_id=invoice.id,
            client_id=client.id,
            method_type="jazzcash",
            transaction_ref="TID123",
            amount=Decimal("15000.00"),
            paid_at=date(2026, 10, 2),
        )

    session.add(payment())
    session.commit()
    session.add(payment())
    with pytest.raises(IntegrityError):
        session.commit()
