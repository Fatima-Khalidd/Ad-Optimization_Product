from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import select

from app.core.errors import ConflictError, FileTooLargeError, NotFoundError, UnsupportedMediaError
from app.models import AuditLog, Invoice, Payment
from app.payments.manual import ManualProvider
from app.schemas.billing import PaymentMethodIn, PaymentMethodPatch, PaymentSubmission
from app.services import payments as payments_service
from tests.api.helpers import (
    JPEG_BYTES,
    PDF_BYTES,
    PNG_BYTES,
    make_admin,
    make_client,
    make_invoice,
    make_method,
)


def _submit(db, client, invoice, ref="JC-90001", amount="10000.00", method="jazzcash"):
    submission = PaymentSubmission(
        method_type=method, transaction_ref=ref, amount=Decimal(amount), paid_at=date(2026, 10, 2)
    )
    return ManualProvider().submit(db, client, invoice, submission, None, None)


def test_the_invoice_total_is_the_base_fee_plus_the_performance_fee(db):
    client = make_client(db, "owner-a@example.com", "Karachi Kicks")
    invoice = make_invoice(db, client)
    # 20% of 23,000 recovered waste = 4,600; 15,000 + 4,600 = 19,600.
    assert invoice.base_fee == Decimal("15000.00")
    assert invoice.confirmed_recovered_waste == Decimal("23000.00")
    assert invoice.performance_fee == Decimal("4600.00")
    assert invoice.total == Decimal("19600.00")


def test_a_partial_confirmation_records_the_money_but_leaves_the_invoice_unpaid(db):
    admin = make_admin(db)
    client = make_client(db, "owner-a@example.com", "Karachi Kicks")
    invoice = make_invoice(db, client)
    payment = _submit(db, client, invoice, "JC-90001", "10000.00")

    confirmed = payments_service.confirm_payment(db, admin, payment.id, "seen in JazzCash app")

    assert confirmed.status == "confirmed"
    assert confirmed.reviewed_by == admin.id
    assert confirmed.reviewed_at is not None
    assert confirmed.review_note == "seen in JazzCash app"
    reloaded = db.get(Invoice, invoice.id)
    assert reloaded.amount_paid == Decimal("10000.00")
    assert reloaded.status == "issued"  # 10,000 < 19,600 -> still owed


def test_confirming_the_remaining_9600_marks_the_invoice_paid(db):
    admin = make_admin(db)
    client = make_client(db, "owner-a@example.com", "Karachi Kicks")
    invoice = make_invoice(db, client)
    first = _submit(db, client, invoice, "JC-90001", "10000.00")
    payments_service.confirm_payment(db, admin, first.id, None)
    second = _submit(db, client, invoice, "JC-90002", "9600.00")

    payments_service.confirm_payment(db, admin, second.id, None)

    reloaded = db.get(Invoice, invoice.id)
    assert reloaded.amount_paid == Decimal("19600.00")
    assert reloaded.status == "paid"


def test_rejecting_the_only_pending_payment_puts_the_invoice_back_to_issued(db):
    admin = make_admin(db)
    client = make_client(db, "owner-a@example.com", "Karachi Kicks")
    invoice = make_invoice(db, client)
    payment = _submit(db, client, invoice)
    assert db.get(Invoice, invoice.id).status == "payment_submitted"

    rejected = payments_service.reject_payment(db, admin, payment.id, "no such TID in my app")

    assert rejected.status == "rejected"
    assert rejected.review_note == "no such TID in my app"
    reloaded = db.get(Invoice, invoice.id)
    assert reloaded.status == "issued"
    assert reloaded.amount_paid == Decimal("0.00")


def test_rejecting_one_of_two_pending_payments_keeps_the_invoice_awaiting_review(db):
    admin = make_admin(db)
    client = make_client(db, "owner-a@example.com", "Karachi Kicks")
    invoice = make_invoice(db, client)
    first = _submit(db, client, invoice, "JC-90001")
    _submit(db, client, invoice, "JC-90002")

    payments_service.reject_payment(db, admin, first.id, "wrong amount")

    assert db.get(Invoice, invoice.id).status == "payment_submitted"


def test_confirm_and_reject_each_write_one_audit_entry(db):
    admin = make_admin(db)
    client = make_client(db, "owner-a@example.com", "Karachi Kicks")
    invoice = make_invoice(db, client)
    good = _submit(db, client, invoice, "JC-90001")
    bad = _submit(db, client, invoice, "JC-90002")

    payments_service.confirm_payment(db, admin, good.id, None)
    payments_service.reject_payment(db, admin, bad.id, "duplicate screenshot")

    actions = [row.action for row in db.scalars(select(AuditLog).order_by(AuditLog.id))]
    assert actions == ["payment.confirm", "payment.reject"]
    entry = db.scalars(select(AuditLog).where(AuditLog.action == "payment.confirm")).one()
    assert entry.actor_user_id == admin.id
    assert entry.entity_type == "payment"
    assert entry.entity_id == good.id
    assert entry.before["invoice_amount_paid"] == "0.00"
    assert entry.after["invoice_amount_paid"] == "10000.00"


def test_confirming_one_of_two_pending_payments_keeps_the_invoice_awaiting_review(db):
    admin = make_admin(db)
    client = make_client(db, "owner-a@example.com", "Karachi Kicks")
    invoice = make_invoice(db, client)
    first = _submit(db, client, invoice, "JC-90001", "10000.00")
    _submit(db, client, invoice, "JC-90002", "5000.00")

    payments_service.confirm_payment(db, admin, first.id, None)

    reloaded = db.get(Invoice, invoice.id)
    assert reloaded.amount_paid == Decimal("10000.00")
    assert reloaded.status == "payment_submitted"  # a second claim is still under review


def test_confirming_the_only_pending_payment_reports_issued_when_still_unpaid(db):
    admin = make_admin(db)
    client = make_client(db, "owner-a@example.com", "Karachi Kicks")
    invoice = make_invoice(db, client)
    payment = _submit(db, client, invoice, "JC-90001", "10000.00")

    payments_service.confirm_payment(db, admin, payment.id, None)

    reloaded = db.get(Invoice, invoice.id)
    assert reloaded.amount_paid == Decimal("10000.00")
    assert reloaded.status == "issued"  # nothing else is pending


def test_confirming_the_last_pending_payment_marks_the_invoice_paid_even_if_others_were_pending(db):
    admin = make_admin(db)
    client = make_client(db, "owner-a@example.com", "Karachi Kicks")
    invoice = make_invoice(db, client)
    first = _submit(db, client, invoice, "JC-90001", "10000.00")
    second = _submit(db, client, invoice, "JC-90002", "9600.00")
    payments_service.confirm_payment(db, admin, first.id, None)

    payments_service.confirm_payment(db, admin, second.id, None)

    reloaded = db.get(Invoice, invoice.id)
    assert reloaded.amount_paid == Decimal("19600.00")
    assert reloaded.status == "paid"  # fully paid overrides any other pending payments


def test_confirming_a_payment_against_a_void_invoice_is_refused(db):
    admin = make_admin(db)
    client = make_client(db, "owner-a@example.com", "Karachi Kicks")
    invoice = make_invoice(db, client)
    payment = _submit(db, client, invoice)
    invoice.status = "void"
    db.commit()

    with pytest.raises(ConflictError) as exc:
        payments_service.confirm_payment(db, admin, payment.id, None)
    assert exc.value.status_code == 409

    db.refresh(payment)
    assert payment.status == "pending"


def test_confirming_a_payment_against_a_draft_invoice_is_refused(db):
    admin = make_admin(db)
    client = make_client(db, "owner-a@example.com", "Karachi Kicks")
    invoice = make_invoice(db, client)
    payment = _submit(db, client, invoice)
    invoice.status = "draft"
    db.commit()

    with pytest.raises(ConflictError) as exc:
        payments_service.confirm_payment(db, admin, payment.id, None)
    assert exc.value.status_code == 409

    db.refresh(payment)
    assert payment.status == "pending"


def test_a_payment_can_only_be_reviewed_once(db):
    admin = make_admin(db)
    client = make_client(db, "owner-a@example.com", "Karachi Kicks")
    invoice = make_invoice(db, client)
    payment = _submit(db, client, invoice)
    payments_service.confirm_payment(db, admin, payment.id, None)

    with pytest.raises(ConflictError) as exc:
        payments_service.confirm_payment(db, admin, payment.id, None)
    assert exc.value.status_code == 409

    with pytest.raises(ConflictError) as exc:
        payments_service.reject_payment(db, admin, payment.id, "changed my mind")
    assert exc.value.status_code == 409


def test_reviewing_a_payment_that_does_not_exist_is_404(db):
    admin = make_admin(db)
    with pytest.raises(NotFoundError) as exc:
        payments_service.confirm_payment(db, admin, 4242, None)
    assert exc.value.status_code == 404


def test_clients_never_see_drafts_and_never_see_another_clients_invoice(db):
    client_a = make_client(db, "a@example.com", "Karachi Kicks")
    client_b = make_client(db, "b@example.com", "Lahore Leather")
    issued = make_invoice(db, client_a, number="INV-2026-0001", status="issued")
    draft = make_invoice(db, client_a, number="INV-2026-0002", status="draft")

    assert [i.id for i in payments_service.list_invoices(db, client_a.id)] == [issued.id]
    assert payments_service.list_invoices(db, client_b.id) == []
    assert payments_service.get_invoice(db, client_a.id, issued.id).id == issued.id

    for client_id, invoice_id in ((client_b.id, issued.id), (client_a.id, draft.id)):
        with pytest.raises(NotFoundError) as exc:
            payments_service.get_invoice(db, client_id, invoice_id)
        assert exc.value.status_code == 404


def test_the_payment_queue_carries_the_invoice_and_the_business_name(db):
    admin = make_admin(db)
    client = make_client(db, "owner-a@example.com", "Karachi Kicks")
    invoice = make_invoice(db, client)
    payment = _submit(db, client, invoice)

    rows = payments_service.list_pending_payments(db)

    assert len(rows) == 1
    assert rows[0].payment.id == payment.id
    assert rows[0].invoice.invoice_number == "INV-2026-0001"
    assert rows[0].client.business_name == "Karachi Kicks"

    payments_service.confirm_payment(db, admin, payment.id, None)
    assert payments_service.list_pending_payments(db) == []
    assert len(payments_service.list_pending_payments(db, status_filter=None)) == 1


@pytest.mark.parametrize(
    ("content_type", "data", "expected"),
    [
        ("image/png", PNG_BYTES, "png"),
        ("image/jpeg", JPEG_BYTES, "jpg"),
        ("application/pdf", PDF_BYTES, "pdf"),
        ("image/png; charset=binary", PNG_BYTES, "png"),
    ],
)
def test_validate_proof_accepts_png_jpeg_and_pdf(content_type, data, expected):
    assert payments_service.validate_proof(content_type, data, 5) == expected


def test_validate_proof_rejects_other_types_and_lying_content_types():
    with pytest.raises(UnsupportedMediaError) as exc:
        payments_service.validate_proof("image/svg+xml", b"<svg/>", 5)
    assert exc.value.status_code == 415

    with pytest.raises(UnsupportedMediaError) as exc:  # says PNG, is really a zip
        payments_service.validate_proof("image/png", b"PK\x03\x04payload", 5)
    assert exc.value.status_code == 415

    with pytest.raises(UnsupportedMediaError) as exc:
        payments_service.validate_proof(None, PNG_BYTES, 5)
    assert exc.value.status_code == 415


def test_validate_proof_enforces_the_five_megabyte_cap():
    too_big = b"\x89PNG\r\n\x1a\n" + b"0" * (5 * 1024 * 1024)
    with pytest.raises(FileTooLargeError) as exc:
        payments_service.validate_proof("image/png", too_big, 5)
    assert exc.value.status_code == 413
    assert "5 MB" in exc.value.detail


def test_payment_method_crud_is_audited_and_patches_only_what_is_sent(db):
    admin = make_admin(db)
    created = payments_service.create_payment_method(
        db,
        admin,
        PaymentMethodIn(
            type="easypaisa",
            account_title="Ali Raza",
            account_identifier="0345-7654321",
            instructions="Easypaisa app -> Send Money.",
            sort_order=3,
        ),
    )
    assert created.is_active is True

    patched = payments_service.update_payment_method(
        db, admin, created.id, PaymentMethodPatch(is_active=False)
    )
    assert patched.is_active is False
    assert patched.account_title == "Ali Raza"  # untouched
    assert patched.sort_order == 3

    make_method(db, "jazzcash", sort_order=1)
    assert [m.type for m in payments_service.list_payment_methods(db)] == ["jazzcash"]
    assert len(payments_service.list_payment_methods(db, active_only=False)) == 2

    actions = [row.action for row in db.scalars(select(AuditLog).order_by(AuditLog.id))]
    assert actions == ["payment_method.create", "payment_method.update"]


def test_updating_a_missing_payment_method_is_404(db):
    admin = make_admin(db)
    with pytest.raises(NotFoundError) as exc:
        payments_service.update_payment_method(db, admin, 999, PaymentMethodPatch(sort_order=1))
    assert exc.value.status_code == 404


def test_list_payments_returns_the_history_oldest_first(db):
    client = make_client(db, "owner-a@example.com", "Karachi Kicks")
    invoice = make_invoice(db, client)
    first = _submit(db, client, invoice, "JC-90001")
    second = _submit(db, client, invoice, "JC-90002")
    assert [p.id for p in payments_service.list_payments(db, invoice.id)] == [first.id, second.id]
    assert len(db.scalars(select(Payment)).all()) == 2


def test_the_service_layer_never_imports_fastapi():
    """app/services/payments.py and app/payments/manual.py raise AppError subclasses, which
    create_app() maps centrally (app/core/errors.py) -- so this layer stays usable outside a
    request (background tasks, scripts/) and there is exactly one error convention in the
    codebase, not two. A plain source-text check is cheap and catches a reintroduced import
    immediately, which is all this needs to guard against.
    """
    backend = Path(__file__).resolve().parents[2]
    for relative in ("app/services/payments.py", "app/payments/manual.py"):
        source = (backend / relative).read_text(encoding="utf-8")
        assert "fastapi" not in source.lower(), f"{relative} must not import fastapi"
