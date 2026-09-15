from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models._types import JSONVariant, utcnow

UPLOAD_STATUS = Enum(
    "uploaded", "validated", "failed", name="upload_status", native_enum=False, length=10
)


class AdDataUpload(Base):
    __tablename__ = "ad_data_uploads"

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(
        ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True
    )
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    row_count: Mapped[int | None] = mapped_column(Integer)
    date_range_start: Mapped[date | None] = mapped_column(Date)
    date_range_end: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(UPLOAD_STATUS, nullable=False, default="uploaded")
    validation_report: Mapped[dict] = mapped_column(JSONVariant, nullable=False, default=dict)
