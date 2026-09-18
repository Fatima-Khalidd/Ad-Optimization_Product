import subprocess
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from app.core.errors import ConflictError
from app.core.settings import get_settings
from app.models import Invoice, Payment
from app.payments import get_payment_provider
from app.payments.base import PaymentInstruction, PaymentProvider
from app.payments.manual import ManualProvider
from app.schemas.billing import PaymentSubmission
from app.services.storage import get_storage
from tests.api.helpers import PNG_BYTES, make_client, make_invoice, make_method


def test_payment_provider_defaults_to_manual():
    assert get_settings().payment_provider == "manual"
    assert get_settings().max_proof_mb == 5


def test_payment_instruction_carries_the_account_a_client_pays_into():
    inst = PaymentInstruction(
        method_type="jazzcash",
        account_title="Ali Raza",
        account_identifier="0300-1234567",
        instructions="Send from your JazzCash app.",
    )
    assert inst.model_dump() == {
        "method_type": "jazzcash",
        "account_title": "Ali Raza",
        "account_identifier": "0300-1234567",
        "instructions": "Send from your JazzCash app.",
    }


def test_protocol_accepts_any_class_with_the_two_methods():
    class FakeGateway:
        name = "fake"

        def instructions_for(self, session, invoice):
            return []

        def submit(self, session, client, invoice, submission, proof, proof_ext):
            raise NotImplementedError

    assert isinstance(FakeGateway(), PaymentProvider)
    assert not isinstance(object(), PaymentProvider)


def test_submission_requires_a_positive_decimal_amount_and_a_known_method():
    ok = PaymentSubmission(
        method_type="easypaisa",
        transaction_ref="EP-77001",
        amount=Decimal("10000.00"),
        paid_at=date(2026, 10, 2),
    )
    assert ok.amount == Decimal("10000.00")
    for bad in (
        {
            "method_type": "easypaisa",
            "transaction_ref": "x",
            "amount": Decimal("0"),
            "paid_at": date(2026, 10, 2),
        },
        {
            "method_type": "easypaisa",
            "transaction_ref": "",
            "amount": Decimal("1"),
            "paid_at": date(2026, 10, 2),
        },
        {
            "method_type": "paypal",
            "transaction_ref": "x",
            "amount": Decimal("1"),
            "paid_at": date(2026, 10, 2),
        },
    ):
        with pytest.raises(ValidationError):
            PaymentSubmission(**bad)


def test_schemas_can_be_imported_before_the_payments_package():
    """app.schemas.billing imports app.payments.base, whose package imports app.schemas.billing back.

    Both sides use `from __future__ import annotations` + TYPE_CHECKING, so the cycle never runs at
    import time. This test fails loudly if someone converts either import into a runtime one.
    """
    backend = Path(__file__).resolve().parents[2]
    for first in ("app.schemas.billing", "app.payments"):
        result = subprocess.run(
            [sys.executable, "-c", f"import {first}"], cwd=backend, capture_output=True, text=True
        )
        assert result.returncode == 0, result.stderr


def _submission(ref="JC-90001", amount="10000.00", method="jazzcash"):
    return PaymentSubmission(
        method_type=method, transaction_ref=ref, amount=Decimal(amount), paid_at=date(2026, 10, 2)
    )


def test_manual_provider_satisfies_the_protocol():
    assert isinstance(ManualProvider(), PaymentProvider)
    assert ManualProvider().name == "manual"


def test_get_payment_provider_returns_the_manual_one_by_default():
    assert isinstance(get_payment_provider(), ManualProvider)


def test_get_payment_provider_rejects_an_unknown_name(monkeypatch):
    monkeypatch.setenv("PAYMENT_PROVIDER", "stripe")
    get_settings.cache_clear()
    with pytest.raises(ValueError, match="unknown payment provider: stripe"):
        get_payment_provider()


def test_instructions_are_the_active_methods_in_sort_order(db):
    client = make_client(db, "owner-a@example.com", "Karachi Kicks")
    invoice = make_invoice(db, client)
    make_method(db, "jazzcash", "0300-1234567", sort_order=2)
    make_method(db, "raast", "PK36SCBL0000001123456702", sort_order=1)
    make_method(db, "nayapay", "0333-9999999", sort_order=0, is_active=False)

    instructions = ManualProvider().instructions_for(db, invoice)

    assert [i.method_type for i in instructions] == ["raast", "jazzcash"]
    assert instructions[0].account_identifier == "PK36SCBL0000001123456702"


def test_submit_records_a_pending_payment_and_moves_the_invoice_to_payment_submitted(db):
    client = make_client(db, "owner-a@example.com", "Karachi Kicks")
    invoice = make_invoice(db, client)

    payment = ManualProvider().submit(db, client, invoice, _submission(), None, None)

    assert payment.status == "pending"
    assert payment.provider == "manual"
    assert payment.amount == Decimal("10000.00")
    assert payment.client_id == client.id
    assert payment.proof_file_path is None
    reloaded = db.get(Invoice, invoice.id)
    assert reloaded.status == "payment_submitted"
    # The rule that matters: a client submission never marks an invoice paid.
    assert reloaded.amount_paid == Decimal("0.00")


def test_the_same_transaction_ref_cannot_be_used_twice_for_one_method(db):
    client = make_client(db, "owner-a@example.com", "Karachi Kicks")
    invoice = make_invoice(db, client)
    provider = ManualProvider()
    provider.submit(db, client, invoice, _submission("JC-90001"), None, None)

    with pytest.raises(ConflictError) as exc:
        provider.submit(db, client, invoice, _submission("JC-90001"), None, None)

    assert exc.value.status_code == 409
    assert "transaction id" in exc.value.detail.lower()
    assert len(db.scalars(select(Payment)).all()) == 1


def test_the_same_ref_on_a_different_method_is_allowed(db):
    client = make_client(db, "owner-a@example.com", "Karachi Kicks")
    invoice = make_invoice(db, client)
    provider = ManualProvider()
    provider.submit(db, client, invoice, _submission("REF-1", method="jazzcash"), None, None)
    second = provider.submit(
        db, client, invoice, _submission("REF-1", method="easypaisa"), None, None
    )
    assert second.id is not None
    assert len(db.scalars(select(Payment)).all()) == 2


def test_proof_bytes_land_in_private_storage_under_the_client_id(db):
    # api_env already points STORAGE_ROOT at this test's own tmp_path.
    client = make_client(db, "owner-a@example.com", "Karachi Kicks")
    invoice = make_invoice(db, client)

    payment = ManualProvider().submit(db, client, invoice, _submission(), PNG_BYTES, "png")

    key = f"proofs/{client.id}/{payment.id}.png"
    assert payment.proof_file_path is not None
    assert key in payment.proof_file_path.replace("\\", "/")
    assert get_storage().read(key) == PNG_BYTES
