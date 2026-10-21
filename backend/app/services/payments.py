"""Invoice reads and the payment lifecycle.

Only two paths change invoices.amount_paid or move an invoice to "paid" (docs/PLAN.md
section 6, Stage 7, Rules): an admin's confirm_payment for a manual transfer, and
record_gateway_payment for a card payment whose webhook signature has already been verified.
Both settle the invoice through `_settle`.
"""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal
from io import BytesIO
from typing import NamedTuple

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, FileTooLargeError, NotFoundError, UnsupportedMediaError
from app.models import Client, Invoice, Payment, PaymentMethod, User
from app.models._types import utcnow
from app.payments import lemonsqueezy
from app.payments.base import PaymentInstruction
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
    "build_invoice_pdf",
    "confirm_payment",
    "create_payment_method",
    "ensure_payable",
    "get_invoice",
    "list_invoices",
    "list_payment_methods",
    "list_payments",
    "list_pending_payments",
    "record_gateway_payment",
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
    lemonsqueezy.METHOD_TYPE: "Card",
}

logger = logging.getLogger(__name__)

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
        raise NotFoundError("invoice not found")
    return invoice


def ensure_payable(invoice: Invoice) -> None:
    """Raise 409 unless a client may still report a payment against this invoice."""
    if invoice.status not in PAYABLE_STATUSES:
        raise ConflictError(
            f"invoice {invoice.invoice_number} is {invoice.status} and cannot take payments"
        )


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
        raise NotFoundError("payment not found")
    if payment.status != "pending":
        raise ConflictError(f"payment was already {payment.status}")
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
    if invoice.status in ("void", "draft"):
        raise ConflictError(
            f"invoice {invoice.invoice_number} is {invoice.status} and cannot take payments"
        )
    before = _snapshot(payment, invoice)

    payment.status = "confirmed"
    payment.reviewed_by = actor.id
    payment.reviewed_at = utcnow()
    payment.review_note = note
    _settle(session, payment, invoice)

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


def _settle(session: Session, payment: Payment, invoice: Invoice) -> None:
    """Credit a just-confirmed payment to its invoice and move the invoice's status on."""
    invoice.amount_paid = Decimal(invoice.amount_paid) + Decimal(payment.amount)
    session.flush()

    if invoice.amount_paid >= invoice.total:
        invoice.status = "paid"
    else:
        # Another payment may still be awaiting review — don't report "issued" (unpaid,
        # nothing pending) while a claim against this same balance is still under review.
        still_pending = session.scalar(
            select(func.count())
            .select_from(Payment)
            .where(Payment.invoice_id == invoice.id, Payment.status == "pending")
        )
        invoice.status = "payment_submitted" if still_pending else "issued"


def record_gateway_payment(session: Session, order: lemonsqueezy.PaidOrder) -> Payment | None:
    """Record a card payment the gateway has already taken, as confirmed. Idempotent.

    Gateways retry webhooks, so a second delivery of the same order returns the payment the
    first one recorded. An order for an invoice that no longer takes payments returns None
    and is logged: the money has moved, so an admin has to refund it by hand.
    """
    existing = _gateway_payment(session, order.order_id)
    if existing is not None:
        return existing
    invoice = session.get(Invoice, order.invoice_id)
    if invoice is None or invoice.status in ("void", "draft"):
        logger.error(
            "card payment %s for invoice %s that cannot take payments; refund it",
            order.order_id,
            order.invoice_id,
        )
        return None

    before = {"invoice_status": invoice.status, "invoice_amount_paid": str(invoice.amount_paid)}
    payment = Payment(
        invoice_id=invoice.id,
        client_id=invoice.client_id,
        method_type=lemonsqueezy.METHOD_TYPE,
        transaction_ref=order.order_id,
        amount=order.amount,
        paid_at=order.paid_at,
        status="confirmed",
        provider=lemonsqueezy.PROVIDER,
        reviewed_at=utcnow(),
        review_note="Paid by card; confirmed automatically by the payment gateway.",
    )
    session.add(payment)
    try:
        # uq_payments_method_ref: two concurrent deliveries of one order cannot both insert.
        session.flush()
    except IntegrityError:
        session.rollback()
        return _gateway_payment(session, order.order_id)
    _settle(session, payment, invoice)
    audit.record(
        session,
        None,  # no human actor: the gateway confirmed it
        "payment.gateway_confirm",
        "payment",
        payment.id,
        before,
        _snapshot(payment, invoice),
    )
    session.commit()
    session.refresh(payment)
    return payment


def _gateway_payment(session: Session, order_id: str) -> Payment | None:
    return session.scalars(
        select(Payment).where(
            Payment.method_type == lemonsqueezy.METHOD_TYPE, Payment.transaction_ref == order_id
        )
    ).first()


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
        raise FileTooLargeError(f"proof file must be {max_mb} MB or smaller")
    entry = PROOF_TYPES.get((content_type or "").split(";")[0].strip().lower())
    if entry is None:
        raise UnsupportedMediaError("proof must be a PNG, JPEG or PDF file")
    extension, magic = entry
    if not data.startswith(magic):
        raise UnsupportedMediaError("proof file contents do not match its file type")
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
        raise NotFoundError("payment method not found")
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


# --------------------------------------------------------------------------- invoice PDF

INK = colors.HexColor("#0b1220")
SLATE = colors.HexColor("#8891a5")
HAIRLINE = colors.HexColor("#d8dde5")

_TABLE_STYLE = TableStyle(
    [
        ("LINEBELOW", (0, 0), (-1, 0), 0.7, INK),
        ("LINEBELOW", (0, 1), (-1, -2), 0.3, HAIRLINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
)


CURRENCY_SYMBOLS = {"USD": "$", "PKR": "Rs. "}


def _money(value: Decimal, currency: str) -> str:
    """$71.01 / Rs. 19,600.00 — always two decimals, always from a Decimal.

    Invoice amounts already carry exact cents (docs/PLAN.md section 1 #6), unlike the waste
    report's format_pkr (app/services/pdf.py), which rounds to whole rupees for the dashboard's
    headline numbers. There is nothing to round here — this just renders the Decimal as-is.
    """
    amount = Decimal(value)
    sign = "-" if amount < 0 else ""
    return f"{sign}{CURRENCY_SYMBOLS[currency]}{abs(amount):,.2f}"


def _day(value: date) -> str:
    return f"{value.day:02d} {value:%b %Y}"


def build_invoice_pdf(
    invoice: Invoice, client: Client, instructions: list[PaymentInstruction]
) -> bytes:
    """One page: what is owed, why, and exactly where to send it."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=f"Invoice {invoice.invoice_number}",
        author="Ad Spend Optimization",
    )
    sheet = getSampleStyleSheet()
    title = ParagraphStyle(
        "InvoiceTitle", parent=sheet["Title"], fontSize=20, alignment=TA_LEFT, spaceAfter=2
    )
    heading = ParagraphStyle(
        "InvoiceHeading", parent=sheet["Heading2"], fontSize=12, spaceBefore=6, spaceAfter=4
    )
    body = ParagraphStyle("InvoiceBody", parent=sheet["BodyText"], fontSize=9.5, leading=13)
    muted = ParagraphStyle("InvoiceMuted", parent=body, textColor=SLATE)

    flow = [
        Paragraph(f"Invoice {invoice.invoice_number}", title),
        Paragraph(client.business_name, body),
        Paragraph(
            f"Billing period: {_day(invoice.period_start)} to {_day(invoice.period_end)}", body
        ),
        Paragraph(f"Due date: {_day(invoice.due_date)}", body),
        Spacer(1, 7 * mm),
    ]

    def money(value: Decimal) -> str:
        return _money(value, invoice.currency)

    # Recovered waste is measured in the client's rupee ad spend; say how it became dollars.
    rate_note = (
        f" at Rs. {Decimal(invoice.pkr_per_usd):,.2f} per USD"
        if invoice.pkr_per_usd is not None
        else ""
    )
    rows = [
        [Paragraph("<b>Item</b>", body), Paragraph("<b>Amount</b>", body)],
        [Paragraph("Monthly fee", body), Paragraph(money(invoice.base_fee), body)],
    ]
    # Flat-price invoices carry no performance fee; a "$0.00" line would only raise questions.
    if Decimal(invoice.performance_fee) > 0:
        rows.append(
            [
                Paragraph(
                    "Performance fee on confirmed recovered waste of "
                    f"{_money(invoice.confirmed_recovered_waste, 'PKR')}{rate_note}",
                    body,
                ),
                Paragraph(money(invoice.performance_fee), body),
            ]
        )
    rows.append(
        [Paragraph("<b>Total due</b>", body), Paragraph(f"<b>{money(invoice.total)}</b>", body)]
    )
    if Decimal(invoice.amount_paid) > 0:
        balance = Decimal(invoice.total) - Decimal(invoice.amount_paid)
        rows.append([Paragraph("Already paid", body), Paragraph(money(invoice.amount_paid), body)])
        rows.append(
            [Paragraph("<b>Balance</b>", body), Paragraph(f"<b>{money(balance)}</b>", body)]
        )

    amounts = Table(rows, colWidths=[115 * mm, 45 * mm], hAlign="LEFT")
    amounts.setStyle(_TABLE_STYLE)
    flow += [amounts, Spacer(1, 8 * mm), Paragraph("How to pay", heading)]

    if instructions:
        account_rows = [
            [
                Paragraph("<b>Method</b>", body),
                Paragraph("<b>Account title</b>", body),
                Paragraph("<b>Account number / IBAN</b>", body),
            ]
        ]
        for instruction in instructions:
            account_rows.append(
                [
                    Paragraph(
                        METHOD_LABELS.get(instruction.method_type, instruction.method_type), body
                    ),
                    Paragraph(instruction.account_title, body),
                    Paragraph(instruction.account_identifier, body),
                ]
            )
        accounts = Table(account_rows, colWidths=[40 * mm, 50 * mm, 70 * mm], hAlign="LEFT")
        accounts.setStyle(_TABLE_STYLE)
        flow.append(accounts)
        for instruction in instructions:
            if instruction.instructions:
                label = METHOD_LABELS.get(instruction.method_type, instruction.method_type)
                flow.append(Paragraph(f"{label}: {instruction.instructions}", muted))
    else:
        flow.append(
            Paragraph("No payment accounts are set up yet — contact us before paying.", muted)
        )

    flow += [
        Spacer(1, 6 * mm),
        Paragraph(
            "Pay from your own wallet or bank app, then reply with your transaction ID on the "
            "billing page. We confirm every payment by hand, so the invoice stays open until we "
            "have checked it.",
            body,
        ),
    ]

    doc.build(flow)
    return buffer.getvalue()
