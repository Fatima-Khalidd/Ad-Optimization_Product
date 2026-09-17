"""Read models for the dashboard.

Decimal fields serialise as JSON strings (Pydantic v2's default), which keeps rupee values
exact across the wire; the Stage 4 client parses them with Number().
"""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.models import SegmentMetric


class SegmentOut(BaseModel):
    segment: str
    spend: Decimal
    impressions: int
    clicks: int
    conversions: int
    revenue: Decimal
    cpa: Decimal | None
    ctr: float
    cvr: float
    roas: float | None
    is_significant: bool
    is_flagged: bool
    wasted_spend: Decimal
    flag_reason: str | None

    @classmethod
    def from_row(cls, row: SegmentMetric) -> "SegmentOut":
        """ctr/cvr/roas/flag_reason are derived, not stored.

        `segment_metrics` (docs/PLAN.md section 4) has no columns for them, and all four
        follow exactly from what is stored: a flagged segment with zero conversions is a
        zero-conversions flag, and any other flagged segment is a high-CPA flag (the
        analyzer can only raise high_cpa when conversions > 0).
        """
        spend = float(row.spend)
        flag_reason: str | None = None
        if row.is_flagged:
            flag_reason = "zero_conversions" if row.conversions == 0 else "high_cpa"
        return cls(
            segment=row.segment_value,
            spend=row.spend,
            impressions=row.impressions,
            clicks=row.clicks,
            conversions=row.conversions,
            revenue=row.revenue,
            cpa=row.cpa,
            ctr=row.clicks / row.impressions if row.impressions else 0.0,
            cvr=row.conversions / row.clicks if row.clicks else 0.0,
            roas=float(row.revenue) / spend if spend else None,
            is_significant=row.is_significant,
            is_flagged=row.is_flagged,
            wasted_spend=row.wasted_spend,
            flag_reason=flag_reason,
        )


class DimensionOut(BaseModel):
    dimension: str
    benchmark_cpa: Decimal | None
    total_spend: Decimal
    total_wasted_spend: Decimal
    segments: list[SegmentOut]


class RecommendationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    dimension: str
    segment_name: str
    current_spend: Decimal
    recommended_cut: Decimal
    reason: str


class ReportOut(BaseModel):
    run_id: int
    upload_id: int
    generated_at: datetime
    date_range_start: date | None
    date_range_end: date | None
    total_spend: Decimal
    headline_waste: Decimal
    recovery_pct: Decimal
    dimensions: list[DimensionOut]
    recommendations: list[RecommendationOut]
    config_snapshot: dict


class RunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    upload_id: int
    status: str
    review_status: str
    headline_waste: Decimal | None
    error_message: str | None
    created_at: datetime
