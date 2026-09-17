"""Invoice drafting and the performance fee.

"Recovered waste" is the before/after comparison from docs/PLAN.md section 1 #5 and
section 7 #2: the system only ever *suggests* a number and the admin confirms it.
Every amount here is a Decimal quantized to 2 places; nothing is ever a float.
"""

from datetime import UTC, date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError
from app.models import AnalysisRun, Client, Invoice, SegmentMetric, User, WasteReport
from app.pipeline.config import PipelineConfig
from app.pipeline.optimizer import calculate_fee
from app.services import audit
from app.services.admin import get_client

TWO_PLACES = Decimal("0.01")

SegmentKey = tuple[str, str]  # (dimension, segment_value)


def _money(value: Decimal | int | float | str | None) -> Decimal:
    return Decimal(str(value or 0)).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def _midnight(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=UTC)


def _latest_approved_run(
    session: Session,
    client_id: int,
    *,
    before: datetime | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
) -> AnalysisRun | None:
    stmt = select(AnalysisRun).where(
        AnalysisRun.client_id == client_id,
        AnalysisRun.review_status == "approved",
        AnalysisRun.status == "done",
    )
    if before is not None:
        stmt = stmt.where(AnalysisRun.created_at < before)
    if start is not None:
        stmt = stmt.where(AnalysisRun.created_at >= start)
    if end is not None:
        stmt = stmt.where(AnalysisRun.created_at < end)
    stmt = stmt.order_by(AnalysisRun.created_at.desc(), AnalysisRun.id.desc()).limit(1)
    return session.scalars(stmt).first()


def _waste_by_segment(session: Session, run_id: int) -> dict[SegmentKey, tuple[bool, Decimal]]:
    """(dimension, segment_value) -> (is_flagged, wasted_spend) for one run."""
    rows = session.execute(
        select(
            WasteReport.dimension,
            SegmentMetric.segment_value,
            SegmentMetric.is_flagged,
            SegmentMetric.wasted_spend,
        )
        .join(SegmentMetric, SegmentMetric.report_id == WasteReport.id)
        .where(WasteReport.run_id == run_id)
    ).all()
    return {
        (dimension, segment): (bool(flagged), _money(waste))
        for dimension, segment, flagged, waste in rows
    }


def suggest_recovered_waste(
    session: Session, client_id: int, period_start: date, period_end: date
) -> Decimal:
    baseline = _latest_approved_run(session, client_id, before=_midnight(period_start))
    current = _latest_approved_run(
        session,
        client_id,
        start=_midnight(period_start),
        end=_midnight(period_end + timedelta(days=1)),  # period_end is inclusive
    )
    if baseline is None or current is None:
        return Decimal("0.00")

    waste_then = _waste_by_segment(session, baseline.id)
    waste_now = _waste_by_segment(session, current.id)

    total = Decimal("0")
    for key, (flagged, then) in waste_then.items():
        if not flagged:
            continue
        # A segment missing from the current run wastes nothing now. An unflagged segment
        # already carries wasted_spend = 0 (Stage 1 only assigns waste to flagged segments).
        now = waste_now.get(key, (False, Decimal("0")))[1]
        if then > now:
            total += then - now
    return total.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


DEFAULT_DUE_DAYS = 14

INVOICE_AUDIT_FIELDS = (
    "invoice_number",
    "status",
    "base_fee",
    "suggested_recovered_waste",
    "confirmed_recovered_waste",
    "performance_fee",
    "total",
    "due_date",
    "issued_at",
    "confirmed_by",
)


def get_invoice(session: Session, invoice_id: int) -> Invoice:
    invoice = session.get(Invoice, invoice_id)
    if invoice is None:
        raise NotFoundError(f"invoice {invoice_id} not found")
    return invoice


def list_invoices(
    session: Session, client_id: int | None = None, status: str | None = None
) -> list[Invoice]:
    stmt = select(Invoice)
    if client_id is not None:
        stmt = stmt.where(Invoice.client_id == client_id)
    if status is not None:
        stmt = stmt.where(Invoice.status == status)
    stmt = stmt.order_by(Invoice.created_at.desc(), Invoice.id.desc())
    return list(session.scalars(stmt))


def _fee_cap(client: Client) -> Decimal | None:
    return PipelineConfig.from_overrides(client.config_overrides or {}).performance_fee_cap


def _next_invoice_number(session: Session, year: int) -> str:
    """Highest existing number for the year, plus one.

    Suffixes are zero-padded to 4 digits, so MAX() on the text column is the numeric
    maximum. RACE: two admins drafting in the same instant can both read this MAX and
    build the same number. There is no SELECT ... FOR UPDATE on SQLite and the MVP has a
    single admin, so we lean on the UNIQUE constraint on invoices.invoice_number: the
    loser gets an IntegrityError and simply drafts again. Revisit if a second operator
    is ever hired (docs/PLAN.md section 4).
    """
    prefix = f"INV-{year}-"
    highest = session.scalar(
        select(func.max(Invoice.invoice_number)).where(Invoice.invoice_number.like(f"{prefix}%"))
    )
    nxt = 1 if highest is None else int(highest.rsplit("-", 1)[1]) + 1
    return f"{prefix}{nxt:04d}"


def draft_invoice(
    session: Session, actor: User, client_id: int, period_start: date, period_end: date
) -> Invoice:
    if period_end < period_start:
        raise ConflictError("period_end is before period_start")
    client = get_client(session, client_id)

    existing = session.scalars(
        select(Invoice).where(
            Invoice.client_id == client_id,
            Invoice.period_start == period_start,
            Invoice.period_end == period_end,
            Invoice.status != "void",
        )
    ).first()
    if existing is not None:
        raise ConflictError(
            f"invoice {existing.invoice_number} already covers {period_start} to {period_end}"
        )

    suggested = suggest_recovered_waste(session, client_id, period_start, period_end)
    # The draft shows what the bill would be if the admin accepts the suggestion; the
    # confirmed figure stays 0 until a human confirms it (docs/PLAN.md section 1 #5).
    fee = calculate_fee(
        _money(client.base_fee),
        Decimal(client.performance_fee_pct),
        suggested,
        cap=_fee_cap(client),
    )
    invoice = Invoice(
        invoice_number=_next_invoice_number(session, period_end.year),
        client_id=client.id,
        period_start=period_start,
        period_end=period_end,
        due_date=period_end + timedelta(days=DEFAULT_DUE_DAYS),  # issue_invoice() overwrites it
        base_fee=fee.base_fee,
        suggested_recovered_waste=suggested,
        confirmed_recovered_waste=Decimal("0.00"),
        performance_fee=fee.performance_fee,
        total=fee.total,
        amount_paid=Decimal("0.00"),
        status="draft",
    )
    session.add(invoice)
    session.flush()
    audit.record(
        session,
        actor.id,
        "invoice.draft",
        "invoice",
        invoice.id,
        None,
        audit.snapshot(invoice, INVOICE_AUDIT_FIELDS),
    )
    session.commit()
    return invoice


def confirm_invoice(
    session: Session, actor: User, invoice_id: int, confirmed_recovered_waste: Decimal
) -> Invoice:
    invoice = get_invoice(session, invoice_id)
    if invoice.status != "draft":
        raise ConflictError(f"invoice {invoice.invoice_number} is {invoice.status}, not draft")
    if confirmed_recovered_waste < 0:
        raise ConflictError("confirmed_recovered_waste must be >= 0")

    client = get_client(session, invoice.client_id)
    before = audit.snapshot(invoice, INVOICE_AUDIT_FIELDS)
    fee = calculate_fee(
        _money(client.base_fee),
        Decimal(client.performance_fee_pct),
        _money(confirmed_recovered_waste),
        cap=_fee_cap(client),
    )
    invoice.base_fee = fee.base_fee
    invoice.confirmed_recovered_waste = fee.recovered_waste
    invoice.performance_fee = fee.performance_fee
    invoice.total = fee.total
    invoice.confirmed_by = actor.id
    session.flush()
    audit.record(
        session,
        actor.id,
        "invoice.confirm",
        "invoice",
        invoice.id,
        before,
        audit.snapshot(invoice, INVOICE_AUDIT_FIELDS),
    )
    session.commit()
    return invoice


def issue_invoice(session: Session, actor: User, invoice_id: int, due_date: date) -> Invoice:
    invoice = get_invoice(session, invoice_id)
    if invoice.status != "draft":
        raise ConflictError(f"invoice {invoice.invoice_number} is {invoice.status}, not draft")
    if invoice.confirmed_by is None:
        raise ConflictError("confirm the performance fee before issuing")

    before = audit.snapshot(invoice, INVOICE_AUDIT_FIELDS)
    invoice.status = "issued"
    invoice.issued_at = datetime.now(UTC)
    invoice.due_date = due_date
    session.flush()
    audit.record(
        session,
        actor.id,
        "invoice.issue",
        "invoice",
        invoice.id,
        before,
        audit.snapshot(invoice, INVOICE_AUDIT_FIELDS),
    )
    session.commit()
    return invoice


def void_invoice(
    session: Session, actor: User, invoice_id: int, note: str | None = None
) -> Invoice:
    invoice = get_invoice(session, invoice_id)
    if invoice.status in ("paid", "void"):
        raise ConflictError(f"invoice {invoice.invoice_number} is {invoice.status}")

    before = audit.snapshot(invoice, INVOICE_AUDIT_FIELDS)
    invoice.status = "void"
    session.flush()
    after = audit.snapshot(invoice, INVOICE_AUDIT_FIELDS)
    after["note"] = note  # audit_log has no note column; the reason rides in `after`
    audit.record(session, actor.id, "invoice.void", "invoice", invoice.id, before, after)
    session.commit()
    return invoice
