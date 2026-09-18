"""Invoice reads and the payment lifecycle.

Only an admin calls confirm_payment/reject_payment — they are the only functions that change
invoices.amount_paid or move an invoice to "paid" (docs/PLAN.md section 6, Stage 7, Rules).
"""

from __future__ import annotations

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
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, FileTooLargeError, NotFoundError, UnsupportedMediaError
from app.models import Client, Invoice, Payment, PaymentMethod, User
from app.models._types import utcnow
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


def _money(value: Decimal) -> str:
    """Rs. 19,600.00 — always two decimals, always from a Decimal.

    Invoice amounts already carry exact cents (docs/PLAN.md section 1 #6), unlike the waste
    report's format_pkr (app/services/pdf.py), which rounds to whole rupees for the dashboard's
    headline numbers. There is nothing to round here — this just renders the Decimal as-is.
    """
    return f"Rs. {Decimal(value):,.2f}"


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

    rows = [
        [Paragraph("<b>Item</b>", body), Paragraph("<b>Amount</b>", body)],
        [Paragraph("Monthly base fee", body), Paragraph(_money(invoice.base_fee), body)],
        [
            Paragraph(
                "Performance fee on confirmed recovered waste of "
                f"{_money(invoice.confirmed_recovered_waste)}",
                body,
            ),
            Paragraph(_money(invoice.performance_fee), body),
        ],
        [Paragraph("<b>Total due</b>", body), Paragraph(f"<b>{_money(invoice.total)}</b>", body)],
    ]
    if Decimal(invoice.amount_paid) > 0:
        balance = Decimal(invoice.total) - Decimal(invoice.amount_paid)
        rows.append([Paragraph("Already paid", body), Paragraph(_money(invoice.amount_paid), body)])
        rows.append(
            [Paragraph("<b>Balance</b>", body), Paragraph(f"<b>{_money(balance)}</b>", body)]
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
