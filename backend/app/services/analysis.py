"""Analysis runs: create one, execute it in the background, and read the report back.

Money crossing from pandas floats into NUMERIC(14,2) goes through `to_money()` and
nowhere else (docs/PLAN.md section 1 #6).
"""

import io
import math
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import session_scope
from app.core.errors import InvalidUploadError, NotFoundError
from app.models import AdDataUpload, AnalysisRun, Client, SegmentMetric, WasteReport
from app.models import Recommendation as RecommendationRow
from app.pipeline.analyzer import analyze_all_dimensions
from app.pipeline.config import DIMENSIONS, PipelineConfig
from app.pipeline.loader import load_csv
from app.pipeline.optimizer import build_recommendations, headline_waste
from app.services.storage import get_storage
from app.services.upload import get_upload

TWO_PLACES = Decimal("0.01")


def to_money(value: float | Decimal) -> Decimal:
    """pandas float (or an already-Decimal amount) -> PKR NUMERIC(14,2).

    A `Decimal` argument is quantized directly - no float round-trip, so a value a float
    cannot represent exactly (e.g. Decimal("123456789012.345")) keeps its exact digits.
    Anything else goes through `Decimal(str(value))` (never `Decimal(float)`, which would
    drag in the float's binary artefacts), then both paths quantize with ROUND_HALF_UP, not
    Python's banker's-rounding `round()`. Non-finite input (`inf`/`nan`) has no sane money
    value, so it raises rather than silently producing garbage - the same stance Stage 1's
    `calculate_fee` takes.
    """
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError(f"cannot convert non-finite value {value!r} to money")
        return value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(f"cannot convert non-finite value {value!r} to money")
    return Decimal(str(value)).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def to_money_or_none(value: float | Decimal | None) -> Decimal | None:
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


def execute_run(run_id: int) -> None:
    """FastAPI BackgroundTask. Runs after the response, so it opens its own session.

    Idempotency: only a `queued` run is executed. A run that is already `running`,
    `done` or `failed` is left untouched - re-dispatching the same run_id (a retried
    background task, a double-click on "analyse") is a silent no-op rather than a
    duplicate set of WasteReport/SegmentMetric/Recommendation rows.
    """
    with session_scope() as session:
        run = session.get(AnalysisRun, run_id)
        if run is None or run.status != "queued":
            return
        run.status = "running"
        session.commit()
        try:
            _persist_analysis(session, run)
        except Exception as exc:  # noqa: BLE001 - every failure must land on the run row
            session.rollback()
            failed = session.get(AnalysisRun, run_id)
            if failed is not None:
                failed.status = "failed"
                failed.error_message = f"{type(exc).__name__}: {exc}"[:1000]
                session.commit()


def _persist_analysis(session: Session, run: AnalysisRun) -> None:
    upload = session.get(AdDataUpload, run.upload_id)
    if upload is None:
        raise RuntimeError(f"upload {run.upload_id} no longer exists")

    data = get_storage().read(upload.file_path)
    config = PipelineConfig.from_overrides(run.config_snapshot)  # the snapshot, never the client
    result = load_csv(io.BytesIO(data), config)
    if not result.ok:
        raise RuntimeError(f"stored file failed validation: {result.errors[0].message}")

    results = analyze_all_dimensions(result.df, config)
    by_dimension: dict[str, list] = {dimension: [] for dimension in DIMENSIONS}
    for rec in build_recommendations(results, config):
        by_dimension[rec.dimension].append(rec)

    for dimension in DIMENSIONS:
        dim = results[dimension]
        report = WasteReport(
            run_id=run.id,
            client_id=run.client_id,
            upload_id=run.upload_id,
            dimension=dimension,
            total_spend=to_money(dim.total_spend),
            total_wasted_spend=to_money(dim.total_wasted_spend),
            benchmark_cpa=to_money_or_none(dim.benchmark_cpa),
        )
        session.add(report)
        session.flush()  # we need report.id for the children

        for seg in dim.segments:
            session.add(
                SegmentMetric(
                    report_id=report.id,
                    segment_value=seg.segment,
                    spend=to_money(seg.spend),
                    impressions=seg.impressions,
                    clicks=seg.clicks,
                    conversions=seg.conversions,
                    revenue=to_money(seg.revenue),
                    cpa=to_money_or_none(seg.cpa),
                    is_significant=seg.is_significant,
                    is_flagged=seg.is_flagged,
                    wasted_spend=to_money(seg.wasted_spend),
                )
            )

        for rec in by_dimension[dimension]:
            session.add(
                RecommendationRow(
                    report_id=report.id,
                    dimension=dimension,
                    segment_name=rec.segment_name,
                    current_spend=to_money(rec.current_spend),
                    recommended_cut=to_money(rec.recommended_cut),
                    reason=rec.reason,
                )
            )

    run.headline_waste = to_money(headline_waste(results))
    run.status = "done"
    session.commit()
