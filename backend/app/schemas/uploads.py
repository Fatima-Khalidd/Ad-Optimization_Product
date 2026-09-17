from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class UploadOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    uploaded_at: datetime
    original_filename: str
    row_count: int | None
    date_range_start: date | None
    date_range_end: date | None
    status: str
    validation_report: dict


class UploadRejected(BaseModel):
    """Body of the 422 returned when a CSV fails validation (docs/PLAN.md section 6)."""

    upload_id: int
    status: str
    errors: list[dict]
    warnings: list[dict]
