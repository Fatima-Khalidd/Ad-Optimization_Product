from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models._types import Money, utcnow

INVOICE_STATUS = Enum(
    "draft",
    "issued",
    "payment_submitted",
    "paid",
    "void",
    name="invoice_status",
    native_enum=False,
    length=20,
)
METHOD_TYPE = Enum(
    "jazzcash",
    "easypaisa",
    "nayapay",
    "raast",
    "bank_iban",
    name="payment_method_type",
    native_enum=False,
    length=20,
)
PAYMENT_STATUS = Enum(
    "pending", "confirmed", "rejected", name="payment_status", native_enum=False, length=10
)


class Invoice(Base):
    __tablename__ = "invoices"
    __table_args__ = (Index("ix_invoices_client_period", "client_id", "period_start"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    client_id: Mapped[int] = mapped_column(
        ForeignKey("clients.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    base_fee: Mapped[Decimal] = mapped_column(Money, nullable=False)
    suggested_recovered_waste: Mapped[Decimal] = mapped_column(Money, nullable=False, default=0)
    confirmed_recovered_waste: Mapped[Decimal] = mapped_column(Money, nullable=False, default=0)
    performance_fee: Mapped[Decimal] = mapped_column(Money, nullable=False, default=0)
    total: Mapped[Decimal] = mapped_column(Money, nullable=False)
    amount_paid: Mapped[Decimal] = mapped_column(Money, nullable=False, default=0)
    status: Mapped[str] = mapped_column(INVOICE_STATUS, nullable=False, default="draft")
    confirmed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PaymentMethod(Base):
    __tablename__ = "payment_methods"

    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[str] = mapped_column(METHOD_TYPE, nullable=False)
    account_title: Mapped[str] = mapped_column(String(120), nullable=False)
    account_identifier: Mapped[str] = mapped_column(String(60), nullable=False)
    instructions: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = (
        UniqueConstraint("method_type", "transaction_ref", name="uq_payments_method_ref"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_id: Mapped[int] = mapped_column(
        ForeignKey("invoices.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    client_id: Mapped[int] = mapped_column(
        ForeignKey("clients.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    method_type: Mapped[str] = mapped_column(METHOD_TYPE, nullable=False)
    transaction_ref: Mapped[str] = mapped_column(String(80), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Money, nullable=False)
    paid_at: Mapped[date] = mapped_column(Date, nullable=False)
    proof_file_path: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(PAYMENT_STATUS, nullable=False, default="pending")
    provider: Mapped[str] = mapped_column(String(20), nullable=False, default="manual")
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
