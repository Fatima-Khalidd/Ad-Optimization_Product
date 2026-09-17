"""Admin operations on clients and analysis runs. Every mutation is audited."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, InvalidConfigError, NotFoundError
from app.models import AnalysisRun, Client, SegmentMetric, User, WasteReport
from app.pipeline.config import PipelineConfig
from app.schemas.admin import ClientPatch, FlaggedSegmentOut, RunAdminOut, RunDimensionOut
from app.services import audit

CLIENT_AUDIT_FIELDS = ("base_fee", "performance_fee_pct", "config_overrides")
RUN_AUDIT_FIELDS = ("status", "review_status", "reviewed_by", "reviewed_at", "review_note")


def list_clients(session: Session) -> list[Client]:
    return list(session.scalars(select(Client).order_by(Client.business_name)))


def get_client(session: Session, client_id: int) -> Client:
    client = session.get(Client, client_id)
    if client is None:
        raise NotFoundError(f"client {client_id} not found")
    return client


def update_client(session: Session, actor: User, client_id: int, patch: ClientPatch) -> Client:
    client = get_client(session, client_id)
    # `exclude_unset` keeps a PATCH partial; an explicit null is dropped because every
    # one of these columns is NOT NULL (docs/PLAN.md section 4).
    data = {k: v for k, v in patch.model_dump(exclude_unset=True).items() if v is not None}

    if "config_overrides" in data:
        try:
            PipelineConfig.from_overrides(data["config_overrides"])
        except (ValueError, TypeError, ArithmeticError) as exc:
            raise InvalidConfigError(str(exc)) from exc

    before = audit.snapshot(client, CLIENT_AUDIT_FIELDS)
    for field, value in data.items():
        setattr(client, field, value)
    session.flush()
    # NUMERIC(14,2) columns quantize on the DB round-trip, not on assignment — refresh so
    # both the returned row and the audit "after" snapshot show "25000.00", not "25000".
    session.refresh(client)
    audit.record(
        session,
        actor.id,
        "client.update",
        "client",
        client.id,
        before,
        audit.snapshot(client, CLIENT_AUDIT_FIELDS),
    )
    session.commit()
    return client


def list_runs(session: Session, review_status: str | None = None) -> list[AnalysisRun]:
    """Every run across every client (admins are not tenant-scoped), newest first."""
    stmt = select(AnalysisRun)
    if review_status is not None:
        stmt = stmt.where(AnalysisRun.review_status == review_status)
    stmt = stmt.order_by(AnalysisRun.created_at.desc(), AnalysisRun.id.desc())
    return list(session.scalars(stmt))


def get_run(session: Session, run_id: int) -> AnalysisRun:
    run = session.get(AnalysisRun, run_id)
    if run is None:
        raise NotFoundError(f"run {run_id} not found")
    return run


def _review_run(
    session: Session, actor: User, run_id: int, new_status: str, note: str | None
) -> AnalysisRun:
    run = get_run(session, run_id)
    if run.review_status != "pending":
        raise ConflictError(f"run {run_id} is already {run.review_status}")
    if new_status == "approved" and run.status != "done":
        # Approving unlocks the report for the client; there is nothing to unlock yet.
        raise ConflictError(f"run {run_id} status is {run.status}, not done")

    before = audit.snapshot(run, RUN_AUDIT_FIELDS)
    run.review_status = new_status
    run.reviewed_by = actor.id
    run.reviewed_at = datetime.now(UTC)
    run.review_note = note
    session.flush()
    action = "run.approve" if new_status == "approved" else "run.reject"
    audit.record(
        session,
        actor.id,
        action,
        "analysis_run",
        run.id,
        before,
        audit.snapshot(run, RUN_AUDIT_FIELDS),
    )
    session.commit()
    return run


def approve_run(session: Session, actor: User, run_id: int, note: str | None = None) -> AnalysisRun:
    return _review_run(session, actor, run_id, "approved", note)


def reject_run(session: Session, actor: User, run_id: int, note: str | None = None) -> AnalysisRun:
    return _review_run(session, actor, run_id, "rejected", note)


def serialize_run(session: Session, run: AnalysisRun, client: Client | None = None) -> RunAdminOut:
    """One run with everything the approval queue shows: per-dimension totals, the flagged
    segments behind them and the config snapshot it was produced with.

    Dimension totals are listed side by side and never summed — the headline figure is the
    largest single dimension and is already stored on the run (docs/PLAN.md section 1 #1).

    `client` lets a caller serializing many runs (the queue endpoint) pass in a row it
    already fetched in bulk, so this never issues its own per-run client query. A caller
    with just one run (approve/reject) can omit it and pay one extra query.
    """
    reports = list(
        session.scalars(
            select(WasteReport).where(WasteReport.run_id == run.id).order_by(WasteReport.dimension)
        )
    )
    dimensions = [
        RunDimensionOut(
            dimension=r.dimension,
            total_spend=r.total_spend,
            total_wasted_spend=r.total_wasted_spend,
            benchmark_cpa=r.benchmark_cpa,
        )
        for r in reports
    ]

    flagged: list[FlaggedSegmentOut] = []
    if reports:
        by_id = {r.id: r.dimension for r in reports}
        rows = session.scalars(
            select(SegmentMetric)
            .where(SegmentMetric.report_id.in_(by_id), SegmentMetric.is_flagged.is_(True))
            .order_by(SegmentMetric.wasted_spend.desc())
        )
        flagged = [
            FlaggedSegmentOut(
                dimension=by_id[s.report_id],
                segment_value=s.segment_value,
                spend=s.spend,
                conversions=s.conversions,
                cpa=s.cpa,
                wasted_spend=s.wasted_spend,
            )
            for s in rows
        ]

    if client is None:
        client = session.get(Client, run.client_id)
    return RunAdminOut(
        id=run.id,
        client_id=run.client_id,
        business_name=client.business_name if client else "",
        upload_id=run.upload_id,
        status=run.status,
        review_status=run.review_status,
        headline_waste=run.headline_waste,
        review_note=run.review_note,
        reviewed_by=run.reviewed_by,
        reviewed_at=run.reviewed_at,
        created_at=run.created_at,
        dimensions=dimensions,
        flagged_segments=flagged,
        config_snapshot=run.config_snapshot or {},
    )
