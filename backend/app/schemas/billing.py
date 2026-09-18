"""Request/response shapes for billing. Money is Decimal everywhere (docs/PLAN.md section 1 #6)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.payments.base import PaymentInstruction

MethodType = Literal["jazzcash", "easypaisa", "nayapay", "raast", "bank_iban"]

# Clients never see drafts (docs/PLAN.md section 6, Stage 7, step 3).
CLIENT_VISIBLE_STATUSES: tuple[str, ...] = ("issued", "payment_submitted", "paid", "void")
# A client may only report a payment against these.
PAYABLE_STATUSES: tuple[str, ...] = ("issued", "payment_submitted")


def _overdue(status: str, due_date: date, today: date) -> bool:
    return status not in ("paid", "void") and due_date < today


class PaymentSubmission(BaseModel):
    """What the client types in after paying from their own app."""

    method_type: MethodType
    transaction_ref: str = Field(min_length=1, max_length=80)
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    paid_at: date


class PaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    method_type: str
    transaction_ref: str
    amount: Decimal
    paid_at: date
    status: str
    review_note: str | None = None
    reviewed_at: datetime | None = None
    created_at: datetime
    # Read from the model but never serialised: the proof path is private (docs/PLAN.md section 6).
    proof_file_path: str | None = Field(default=None, exclude=True)

    @computed_field
    @property
    def has_proof(self) -> bool:
        return self.proof_file_path is not None


class InvoiceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    invoice_number: str
    period_start: date
    period_end: date
    due_date: date
    base_fee: Decimal
    confirmed_recovered_waste: Decimal
    performance_fee: Decimal
    total: Decimal
    amount_paid: Decimal
    status: str
    issued_at: datetime | None = None
    created_at: datetime
    payments: list[PaymentOut] = []
    instructions: list[PaymentInstruction] = []

    @computed_field
    @property
    def amount_due(self) -> Decimal:
        return self.total - self.amount_paid

    @computed_field
    @property
    def is_overdue(self) -> bool:
        return _overdue(self.status, self.due_date, date.today())


class AdminPaymentOut(PaymentOut):
    client_id: int
    business_name: str
    invoice_id: int
    invoice_number: str
    invoice_total: Decimal
    invoice_due_date: date
    invoice_status: str
    invoice_is_overdue: bool


class PaymentMethodIn(BaseModel):
    type: MethodType
    account_title: str = Field(min_length=1, max_length=120)
    account_identifier: str = Field(min_length=1, max_length=60)
    instructions: str | None = Field(default=None, max_length=1000)
    is_active: bool = True
    sort_order: int = 0


class PaymentMethodPatch(BaseModel):
    """Only the fields actually sent are applied.

    See model_dump(exclude_unset=True) in the service.
    """

    account_title: str | None = Field(default=None, min_length=1, max_length=120)
    account_identifier: str | None = Field(default=None, min_length=1, max_length=60)
    instructions: str | None = Field(default=None, max_length=1000)
    is_active: bool | None = None
    sort_order: int | None = None


class PaymentMethodOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: str
    account_title: str
    account_identifier: str
    instructions: str | None = None
    is_active: bool
    sort_order: int


class ReviewRequest(BaseModel):
    note: str | None = Field(default=None, max_length=1000)


class RejectRequest(BaseModel):
    """A rejection must say why — the client reads this note and submits again."""

    note: str = Field(min_length=1, max_length=1000)


def invoice_out(invoice, payments=(), instructions=()) -> InvoiceOut:
    """Build an InvoiceOut. The Invoice model has no relationships, so both lists are passed in."""
    base = InvoiceOut.model_validate(invoice)
    return base.model_copy(
        update={
            "payments": [PaymentOut.model_validate(p) for p in payments],
            "instructions": list(instructions),
        }
    )


def admin_payment_out(payment, invoice, client, today: date | None = None) -> AdminPaymentOut:
    today = today or date.today()
    base = PaymentOut.model_validate(payment).model_dump(exclude={"has_proof"})
    return AdminPaymentOut(
        **base,
        proof_file_path=payment.proof_file_path,
        client_id=client.id,
        business_name=client.business_name,
        invoice_id=invoice.id,
        invoice_number=invoice.invoice_number,
        invoice_total=invoice.total,
        invoice_due_date=invoice.due_date,
        invoice_status=invoice.status,
        invoice_is_overdue=_overdue(invoice.status, invoice.due_date, today),
    )
