"""Request and response models for /api/admin. Decimals serialize as JSON strings."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ClientPatch(BaseModel):
    """A partial client update. Only the fields actually sent are applied."""

    model_config = ConfigDict(extra="forbid")

    base_fee: Decimal | None = Field(default=None, ge=0)
    performance_fee_pct: Decimal | None = Field(default=None, ge=0, le=100)
    config_overrides: dict[str, Any] | None = None


class AdminClientOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    business_name: str
    contact_info: str | None = None
    pricing_model: str
    base_fee: Decimal
    performance_fee_pct: Decimal
    config_overrides: dict[str, Any]
    created_at: datetime


class RunDimensionOut(BaseModel):
    dimension: str
    total_spend: Decimal
    total_wasted_spend: Decimal
    benchmark_cpa: Decimal | None = None


class FlaggedSegmentOut(BaseModel):
    dimension: str
    segment_value: str
    spend: Decimal
    conversions: int
    cpa: Decimal | None = None
    wasted_spend: Decimal


class RunAdminOut(BaseModel):
    id: int
    client_id: int
    business_name: str
    upload_id: int
    status: str
    review_status: str
    headline_waste: Decimal | None = None
    review_note: str | None = None
    reviewed_by: int | None = None
    reviewed_at: datetime | None = None
    created_at: datetime
    dimensions: list[RunDimensionOut]
    flagged_segments: list[FlaggedSegmentOut]
    config_snapshot: dict[str, Any]


class ReviewIn(BaseModel):
    note: str | None = Field(default=None, max_length=2000)


class InvoiceDraftIn(BaseModel):
    client_id: int
    period_start: date
    period_end: date


class ConfirmInvoiceIn(BaseModel):
    confirmed_recovered_waste: Decimal = Field(ge=0)


class IssueInvoiceIn(BaseModel):
    due_date: date


class VoidInvoiceIn(BaseModel):
    note: str | None = Field(default=None, max_length=2000)


class AdminInvoiceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    invoice_number: str
    client_id: int
    period_start: date
    period_end: date
    due_date: date
    base_fee: Decimal
    suggested_recovered_waste: Decimal
    confirmed_recovered_waste: Decimal
    performance_fee: Decimal
    total: Decimal
    amount_paid: Decimal
    status: str
    confirmed_by: int | None = None
    issued_at: datetime | None = None
    created_at: datetime


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    actor_user_id: int | None = None
    action: str
    entity_type: str
    entity_id: int
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    created_at: datetime
