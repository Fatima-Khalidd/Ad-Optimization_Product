"""Analysis runs: create one, execute it in the background, and read the report back.

Money crossing from pandas floats into NUMERIC(14,2) goes through `to_money()` and
nowhere else (docs/PLAN.md section 1 #6).
"""

import math
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import InvalidUploadError, NotFoundError
from app.models import AnalysisRun, Client
from app.pipeline.config import PipelineConfig
from app.services.upload import get_upload

TWO_PLACES = Decimal("0.01")


def to_money(value: float) -> Decimal:
    """pandas float -> PKR NUMERIC(14,2).

    Goes through `Decimal(str(value))` (never `Decimal(float)`, which would drag in the
    float's binary artefacts) and quantizes with ROUND_HALF_UP, not Python's banker's-
    rounding `round()`. Non-finite input (`inf`/`nan`) has no sane money value, so it
    raises rather than silently producing garbage - the same stance Stage 1's
    `calculate_fee` takes.
    """
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(f"cannot convert non-finite value {value!r} to money")
    return Decimal(str(value)).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def to_money_or_none(value: float | None) -> Decimal | None:
    return None if value is None else to_money(value)


def create_run(session: Session, client: Client, upload_id: int) -> AnalysisRun:
    upload = get_upload(session, client.id, upload_id)  # 404 for another tenant
    if upload.status != "validated":
        raise InvalidUploadError(
            {
                "message": "this upload did not pass validation and cannot be analysed",
                "upload_id": upload.id,
            }
        )
    # An invalid override dict (e.g. a non-numeric waste_multiplier) makes
    # PipelineConfig.from_overrides raise ValueError, which propagates uncaught: the
    # caller (the router) sees a plain 500 unless it wraps this, since a bad override is a
    # server-side data problem, not something the request itself got wrong.
    config = PipelineConfig.from_overrides(client.config_overrides or {})
    run = AnalysisRun(
        client_id=client.id,
        upload_id=upload.id,
        config_snapshot=config.to_dict(),
        status="queued",
        review_status="pending",
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    return run


def get_run(session: Session, client_id: int, run_id: int) -> AnalysisRun:
    run = session.scalars(
        select(AnalysisRun).where(AnalysisRun.id == run_id, AnalysisRun.client_id == client_id)
    ).first()
    if run is None:
        raise NotFoundError("run not found")
    return run
