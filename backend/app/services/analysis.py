"""Analysis runs: create one, execute it in the background, and read the report back.

Money crossing from pandas floats into NUMERIC(14,2) goes through `to_money()` and
nowhere else (docs/PLAN.md section 1 #6).
"""

import io
import logging
import math
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.db import session_scope
from app.core.errors import InvalidUploadError, NotFoundError
from app.models import AdDataUpload, AnalysisRun, Client, SegmentMetric, WasteReport
from app.models import Recommendation as RecommendationRow
from app.models._types import utcnow
from app.pipeline.analyzer import account_total_spend, analyze_all_dimensions
from app.pipeline.config import DIMENSIONS, PipelineConfig
from app.pipeline.loader import load_csv
from app.pipeline.optimizer import build_recommendations, headline_waste
from app.schemas.reports import DimensionOut, RecommendationOut, ReportOut, SegmentOut
from app.services.storage import get_storage
from app.services.upload import get_upload

logger = logging.getLogger(__name__)

TWO_PLACES = Decimal("0.01")

# A run is only reused (F4) while it is younger than this - past it, a `queued`/`running`
# row is treated as dead (a worker likely crashed mid-run) rather than blocking every later
# POST /api/analyze/{id} for that client+upload forever. Stage 8 backlog item: a real sweep
# that re-queues stale `running` rows (docs/superpowers/plans/INTERFACES.md close-out #7).
ANALYSIS_REUSE_WINDOW_MINUTES = 15


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
    """Idempotent for an in-flight run: a second call for the same client/upload while a

    prior run is still `queued` or `running` returns that SAME run unchanged, rather than
    queuing a duplicate - a double-click on the dashboard's Analyze button must not double
    the persisted WasteReport/SegmentMetric/Recommendation rows or give the Stage 6 admin
    two identical runs to approve. Once the prior run is `done` or `failed`, a fresh call
    starts a new run as before (re-analysis after a config change is legitimate).
    """
    upload = get_upload(session, client.id, upload_id)  # 404 for another tenant
    if upload.status != "validated":
        raise InvalidUploadError(
            {
                "message": "this upload did not pass validation and cannot be analysed",
                "upload_id": upload.id,
            }
        )
    reuse_cutoff = utcnow() - timedelta(minutes=ANALYSIS_REUSE_WINDOW_MINUTES)
    in_flight = session.scalars(
        select(AnalysisRun)
        .where(
            AnalysisRun.client_id == client.id,
            AnalysisRun.upload_id == upload.id,
            AnalysisRun.status.in_(("queued", "running")),
            AnalysisRun.created_at >= reuse_cutoff,
        )
        .order_by(AnalysisRun.id.desc())
    ).first()
    if in_flight is not None:
        return in_flight
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


_GENERIC_ERROR_MESSAGE = "the analysis could not be completed"

# A small allowlist of exception types whose default str() is known-safe (no storage key,
# server path, or file hash can appear in it) - everything else falls back to the generic
# message. `PermissionError` and a bare `ValueError` (e.g. "invalid storage key: '...'")
# are deliberately NOT here: both were shown to leak a full path/key when probed.
_SAFE_MESSAGES: dict[type[Exception], str] = {
    FileNotFoundError: "the uploaded file could not be read",
}


def _error_message(exc: Exception) -> str:
    """A short, client-facing reason - never a storage key, tenant path, or file hash.

    The full detail (including any key/path) always goes to `logger.exception` instead;
    this string is what ends up in a `Text` column a client can see (F3, Stage 3 close-out
    #6). Only exceptions on the allowlist above get a specific message - anything else,
    however descriptive, is reduced to a single generic sentence rather than risk leaking
    part of a path or key through `str(exc)`.
    """
    return _SAFE_MESSAGES.get(type(exc), _GENERIC_ERROR_MESSAGE)


def execute_run(run_id: int) -> None:
    """FastAPI BackgroundTask. Runs after the response, so it opens its own session.

    Idempotency: the claim below is a single conditional UPDATE
    (`WHERE id = :run_id AND status = 'queued'`), so a double dispatch of the same
    run_id can never have both calls proceed - whichever commits first flips the row to
    `running` and the loser's `rowcount` is 0. A run that is already `running`, `done` or
    `failed` (or an unknown id) is left untouched: silent no-op rather than a duplicate
    set of WasteReport/SegmentMetric/Recommendation rows.
    """
    with session_scope() as session:
        claim = session.execute(
            update(AnalysisRun)
            .where(AnalysisRun.id == run_id, AnalysisRun.status == "queued")
            .values(status="running")
        )
        session.commit()
        if claim.rowcount == 0:
            return  # unknown id, already running, or already done/failed
        run = session.get(AnalysisRun, run_id)
        try:
            _persist_analysis(session, run)
        except Exception as exc:  # noqa: BLE001 - every failure must land on the run row
            logger.exception("execute_run failed for run_id=%s", run_id)
            session.rollback()
            failed = session.get(AnalysisRun, run_id)
            if failed is not None:
                failed.status = "failed"
                failed.error_message = _error_message(exc)
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
    run.account_total_spend = to_money(account_total_spend(result.df))
    run.status = "done"
    session.commit()


ZERO = Decimal("0.00")


def get_report(session: Session, client_id: int, run_id: int) -> ReportOut:
    """Clients only ever see finished, admin-approved runs (docs/PLAN.md section 4)."""
    run = get_run(session, client_id, run_id)
    if run.status != "done" or run.review_status != "approved":
        raise NotFoundError("report not found")
    return _build_report(session, run)


def latest_report(session: Session, client_id: int) -> ReportOut | None:
    run = session.scalars(
        select(AnalysisRun)
        .where(
            AnalysisRun.client_id == client_id,
            AnalysisRun.status == "done",
            AnalysisRun.review_status == "approved",
        )
        .order_by(AnalysisRun.created_at.desc(), AnalysisRun.id.desc())
    ).first()
    return None if run is None else _build_report(session, run)


def _build_report(session: Session, run: AnalysisRun) -> ReportOut:
    upload = session.get(AdDataUpload, run.upload_id)
    reports = list(
        session.scalars(
            select(WasteReport).where(WasteReport.run_id == run.id).order_by(WasteReport.id)
        )
    )

    dimensions: list[DimensionOut] = []
    recommendations: list[RecommendationOut] = []
    for report in reports:
        segments = session.scalars(
            select(SegmentMetric)
            .where(SegmentMetric.report_id == report.id)
            .order_by(SegmentMetric.spend.desc(), SegmentMetric.id)
        )
        dimensions.append(
            DimensionOut(
                dimension=report.dimension,
                benchmark_cpa=report.benchmark_cpa,
                total_spend=report.total_spend,
                total_wasted_spend=report.total_wasted_spend,
                segments=[SegmentOut.from_row(s) for s in segments],
            )
        )
        rows = session.scalars(
            select(RecommendationRow)
            .where(RecommendationRow.report_id == report.id)
            .order_by(RecommendationRow.recommended_cut.desc(), RecommendationRow.id)
        )
        recommendations.extend(RecommendationOut.model_validate(row) for row in rows)

    recommendations.sort(key=lambda rec: rec.recommended_cut, reverse=True)

    # F1 (Stage 3 close-out #1): the true account total, persisted on the run from
    # analyzer.account_total_spend(df) at execute_run time - NOT max(per-dimension total),
    # which understates spend whenever the export is only partially populated (docs/PLAN.md
    # section 1 #3; measured 1500 vs the true 3500 on partial_dimensions.csv). The fallback
    # below only fires for a run persisted before this column existed (account_total_spend
    # is NULL): those legacy rows have no better figure available than the old largest-
    # dimension approximation.
    total_spend = (
        run.account_total_spend
        if run.account_total_spend is not None
        else max((d.total_spend for d in dimensions), default=ZERO)
    )
    headline = run.headline_waste if run.headline_waste is not None else ZERO
    recovery_pct = (
        ZERO
        if total_spend == 0
        else (headline / total_spend * 100).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    )

    return ReportOut(
        run_id=run.id,
        upload_id=run.upload_id,
        generated_at=reports[0].generated_at if reports else run.created_at,
        date_range_start=upload.date_range_start if upload else None,
        date_range_end=upload.date_range_end if upload else None,
        total_spend=total_spend,
        headline_waste=headline,
        recovery_pct=recovery_pct,
        dimensions=dimensions,
        recommendations=recommendations,
        config_snapshot=run.config_snapshot,
    )
