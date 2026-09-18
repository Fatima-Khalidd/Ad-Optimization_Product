"""Invoice reads and the payment lifecycle.

Only an admin calls confirm_payment/reject_payment — they are the only functions that change
invoices.amount_paid or move an invoice to "paid" (docs/PLAN.md section 6, Stage 7, Rules).
"""

from __future__ import annotations

from decimal import Decimal
from typing import NamedTuple

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Client, Invoice, Payment, PaymentMethod, User
from app.models._types import utcnow
from app.schemas.billing import (
    CLIENT_VISIBLE_STATUSES,
    PAYABLE_STATUSES,
    PaymentMethodIn,
    PaymentMethodPatch,
)
from app.services import audit

__all__ = [
    "CLIENT_VISIBLE_STATUSES",
    "METHOD_LABELS",
    "PAYABLE_STATUSES",
    "PROOF_TYPES",
    "PaymentQueueRow",
    "confirm_payment",
    "create_payment_method",
    "get_invoice",
    "list_invoices",
    "list_payment_methods",
    "list_payments",
    "list_pending_payments",
    "reject_payment",
    "update_payment_method",
    "validate_proof",
]

# Human labels for the five methods in docs/PLAN.md section 4.
METHOD_LABELS: dict[str, str] = {
    "jazzcash": "JazzCash",
    "easypaisa": "Easypaisa",
    "nayapay": "NayaPay",
    "raast": "Raast",
    "bank_iban": "Bank transfer (IBAN)",
}

# content-type -> (file extension, magic bytes the file must actually start with).
PROOF_TYPES: dict[str, tuple[str, bytes]] = {
    "image/png": ("png", b"\x89PNG\r\n\x1a\n"),
    "image/jpeg": ("jpg", b"\xff\xd8\xff"),
    "application/pdf": ("pdf", b"%PDF-"),
}


class PaymentQueueRow(NamedTuple):
    payment: Payment
    invoice: Invoice
    client: Client


# --------------------------------------------------------------------------- client reads


def list_invoices(session: Session, client_id: int) -> list[Invoice]:
    return list(
        session.scalars(
            select(Invoice)
            .where(Invoice.client_id == client_id, Invoice.status.in_(CLIENT_VISIBLE_STATUSES))
            .order_by(Invoice.period_start.desc(), Invoice.id.desc())
        )
    )


def get_invoice(session: Session, client_id: int, invoice_id: int) -> Invoice:
    """404 — not 403 — for another tenant's invoice, so ids can't be probed (docs/PLAN.md §4)."""
    invoice = session.scalars(
        select(Invoice).where(
            Invoice.id == invoice_id,
            Invoice.client_id == client_id,
            Invoice.status.in_(CLIENT_VISIBLE_STATUSES),
        )
    ).first()
    if invoice is None:
        raise HTTPException(status_code=404, detail="invoice not found")
    return invoice


def list_payments(session: Session, invoice_id: int) -> list[Payment]:
    return list(
        session.scalars(
            select(Payment).where(Payment.invoice_id == invoice_id).order_by(Payment.id)
        )
    )


# --------------------------------------------------------------------------- admin queue


def list_pending_payments(
    session: Session, status_filter: str | None = "pending"
) -> list[PaymentQueueRow]:
    stmt = (
        select(Payment, Invoice, Client)
        .join(Invoice, Payment.invoice_id == Invoice.id)
        .join(Client, Payment.client_id == Client.id)
        .order_by(Payment.created_at.desc(), Payment.id.desc())
    )
    if status_filter is not None:
        stmt = stmt.where(Payment.status == status_filter)
    return [
        PaymentQueueRow(payment, invoice, client)
        for payment, invoice, client in session.execute(stmt).all()
    ]


# --------------------------------------------------------------------------- admin decisions


def _get_payment(session: Session, payment_id: int) -> Payment:
    payment = session.get(Payment, payment_id)
    if payment is None:
        raise HTTPException(status_code=404, detail="payment not found")
    if payment.status != "pending":
        raise HTTPException(status_code=409, detail=f"payment was already {payment.status}")
    return payment


def _snapshot(payment: Payment, invoice: Invoice) -> dict[str, str]:
    """JSON-safe before/after for audit_log. Decimals become strings, never floats."""
    return {
        "payment_status": payment.status,
        "payment_amount": str(payment.amount),
        "invoice_status": invoice.status,
        "invoice_amount_paid": str(invoice.amount_paid),
    }


def confirm_payment(
    session: Session, actor: User, payment_id: int, note: str | None = None
) -> Payment:
    payment = _get_payment(session, payment_id)
    invoice = session.get(Invoice, payment.invoice_id)
    before = _snapshot(payment, invoice)

    payment.status = "confirmed"
    payment.reviewed_by = actor.id
    payment.reviewed_at = utcnow()
    payment.review_note = note
    invoice.amount_paid = Decimal(invoice.amount_paid) + Decimal(payment.amount)
    invoice.status = "paid" if invoice.amount_paid >= invoice.total else "issued"

    audit.record(
        session,
        actor.id,
        "payment.confirm",
        "payment",
        payment.id,
        before,
        _snapshot(payment, invoice),
    )
    session.commit()
    session.refresh(payment)
    return payment


def reject_payment(session: Session, actor: User, payment_id: int, note: str) -> Payment:
    payment = _get_payment(session, payment_id)
    invoice = session.get(Invoice, payment.invoice_id)
    before = _snapshot(payment, invoice)

    payment.status = "rejected"
    payment.reviewed_by = actor.id
    payment.reviewed_at = utcnow()
    payment.review_note = note
    session.flush()

    still_pending = session.scalar(
        select(func.count())
        .select_from(Payment)
        .where(Payment.invoice_id == invoice.id, Payment.status == "pending")
    )
    if invoice.status == "payment_submitted" and not still_pending:
        invoice.status = "issued"

    audit.record(
        session,
        actor.id,
        "payment.reject",
        "payment",
        payment.id,
        before,
        _snapshot(payment, invoice),
    )
    session.commit()
    session.refresh(payment)
    return payment


# --------------------------------------------------------------------------- proof files


def validate_proof(content_type: str | None, data: bytes, max_mb: int) -> str:
    """Return the file extension for a proof upload, or raise 413 (too big) / 415 (wrong kind)."""
    if len(data) > max_mb * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"proof file must be {max_mb} MB or smaller")
    entry = PROOF_TYPES.get((content_type or "").split(";")[0].strip().lower())
    if entry is None:
        raise HTTPException(status_code=415, detail="proof must be a PNG, JPEG or PDF file")
    extension, magic = entry
    if not data.startswith(magic):
        raise HTTPException(
            status_code=415, detail="proof file contents do not match its file type"
        )
    return extension


# --------------------------------------------------------------------------- payment methods


def list_payment_methods(session: Session, active_only: bool = True) -> list[PaymentMethod]:
    stmt = select(PaymentMethod).order_by(PaymentMethod.sort_order, PaymentMethod.id)
    if active_only:
        stmt = stmt.where(PaymentMethod.is_active.is_(True))
    return list(session.scalars(stmt))


def _method_snapshot(method: PaymentMethod) -> dict[str, str | bool | int]:
    return {
        "type": method.type,
        "account_title": method.account_title,
        "account_identifier": method.account_identifier,
        "is_active": method.is_active,
        "sort_order": method.sort_order,
    }


def create_payment_method(session: Session, actor: User, data: PaymentMethodIn) -> PaymentMethod:
    method = PaymentMethod(**data.model_dump())
    session.add(method)
    session.flush()
    audit.record(
        session,
        actor.id,
        "payment_method.create",
        "payment_method",
        method.id,
        None,
        _method_snapshot(method),
    )
    session.commit()
    session.refresh(method)
    return method


def update_payment_method(
    session: Session, actor: User, method_id: int, patch: PaymentMethodPatch
) -> PaymentMethod:
    method = session.get(PaymentMethod, method_id)
    if method is None:
        raise HTTPException(status_code=404, detail="payment method not found")
    before = _method_snapshot(method)
    for field, value in patch.model_dump(exclude_unset=True).items():
        setattr(method, field, value)
    audit.record(
        session,
        actor.id,
        "payment_method.update",
        "payment_method",
        method.id,
        before,
        _method_snapshot(method),
    )
    session.commit()
    session.refresh(method)
    return method
