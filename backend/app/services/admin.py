"""Admin operations on clients and analysis runs. Every mutation is audited."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, InvalidConfigError, NotFoundError
from app.models import AnalysisRun, Client, User
from app.pipeline.config import PipelineConfig
from app.schemas.admin import ClientPatch
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
