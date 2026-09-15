from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models._types import JSONVariant, Money, utcnow

RUN_STATUS = Enum(
    "queued", "running", "done", "failed", name="run_status", native_enum=False, length=10
)
REVIEW_STATUS = Enum(
    "pending", "approved", "rejected", name="review_status", native_enum=False, length=10
)


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"
    __table_args__ = (Index("ix_analysis_runs_client_created", "client_id", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(
        ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True
    )
    upload_id: Mapped[int] = mapped_column(
        ForeignKey("ad_data_uploads.id", ondelete="CASCADE"), nullable=False
    )
    config_snapshot: Mapped[dict] = mapped_column(JSONVariant, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(RUN_STATUS, nullable=False, default="queued")
    review_status: Mapped[str] = mapped_column(REVIEW_STATUS, nullable=False, default="pending")
    headline_waste: Mapped[Decimal | None] = mapped_column(Money)
    error_message: Mapped[str | None] = mapped_column(Text)
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class WasteReport(Base):
    __tablename__ = "waste_reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    client_id: Mapped[int] = mapped_column(
        ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True
    )
    upload_id: Mapped[int] = mapped_column(
        ForeignKey("ad_data_uploads.id", ondelete="CASCADE"), nullable=False
    )
    dimension: Mapped[str] = mapped_column(String(30), nullable=False)
    total_spend: Mapped[Decimal] = mapped_column(Money, nullable=False)
    total_wasted_spend: Mapped[Decimal] = mapped_column(Money, nullable=False)
    benchmark_cpa: Mapped[Decimal | None] = mapped_column(Money)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SegmentMetric(Base):
    __tablename__ = "segment_metrics"

    id: Mapped[int] = mapped_column(primary_key=True)
    report_id: Mapped[int] = mapped_column(
        ForeignKey("waste_reports.id", ondelete="CASCADE"), nullable=False, index=True
    )
    segment_value: Mapped[str] = mapped_column(String(100), nullable=False)
    spend: Mapped[Decimal] = mapped_column(Money, nullable=False)
    impressions: Mapped[int] = mapped_column(Integer, nullable=False)
    clicks: Mapped[int] = mapped_column(Integer, nullable=False)
    conversions: Mapped[int] = mapped_column(Integer, nullable=False)
    revenue: Mapped[Decimal] = mapped_column(Money, nullable=False)
    cpa: Mapped[Decimal | None] = mapped_column(Money)
    is_significant: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_flagged: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    wasted_spend: Mapped[Decimal] = mapped_column(Money, nullable=False, default=0)


class Recommendation(Base):
    __tablename__ = "recommendations"

    id: Mapped[int] = mapped_column(primary_key=True)
    report_id: Mapped[int] = mapped_column(
        ForeignKey("waste_reports.id", ondelete="CASCADE"), nullable=False, index=True
    )
    dimension: Mapped[str] = mapped_column(String(30), nullable=False)
    segment_name: Mapped[str] = mapped_column(String(100), nullable=False)
    current_spend: Mapped[Decimal] = mapped_column(Money, nullable=False)
    recommended_cut: Mapped[Decimal] = mapped_column(Money, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
