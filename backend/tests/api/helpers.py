"""Row builders and login helpers shared by every test under tests/api/.

Columns are exactly docs/PLAN.md section 4. Every builder COMMITS, because the request
handler runs on its own Session over the shared connection and only sees committed rows.
Import them as `from tests.api.helpers import make_client, login_as` - that resolves because
pytest is always run as `.venv/Scripts/python -m pytest` from `backend/`.
"""

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import (
    AdDataUpload,
    AnalysisRun,
    Client,
    Invoice,
    PaymentMethod,
    Recommendation,
    SegmentMetric,
    User,
    WasteReport,
)
from app.models._types import utcnow

TEST_PASSWORD = "correct horse battery staple"


def login_as(api: TestClient, user: User) -> None:
    """Log this TestClient in as `user`, through the real login route.

    Works for any user built by `make_client` / `make_admin`, because both hash
    TEST_PASSWORD. Cookies land in the client's jar, so every later call is authenticated.
    """
    response = api.post("/api/auth/login", json={"email": user.email, "password": TEST_PASSWORD})
    assert response.status_code == 200, response.text


def user_for(db: Session, client: Client) -> User:
    """The login row behind a Client (the models declare no relationships)."""
    user = db.get(User, client.user_id)
    assert user is not None
    return user


def make_client(
    db: Session,
    email: str = "client@example.com",
    business_name: str = "Biz",
    *,
    is_active: bool = True,
    base_fee: Decimal = Decimal("15000.00"),
    performance_fee_pct: Decimal = Decimal("20.00"),
    config_overrides: dict | None = None,
) -> Client:
    """A committed User(role="client") + its Client row. Returns the Client."""
    user = User(
        email=email.lower(),
        password_hash=hash_password(TEST_PASSWORD),
        role="client",
        is_active=is_active,
    )
    db.add(user)
    db.flush()
    client = Client(
        user_id=user.id,
        business_name=business_name,
        base_fee=base_fee,
        performance_fee_pct=performance_fee_pct,
        config_overrides=config_overrides or {},
    )
    db.add(client)
    db.commit()
    db.refresh(client)
    return client


def make_admin(db: Session, email: str = "admin@example.com", *, is_active: bool = True) -> User:
    """A committed User(role="admin"). Admins have no Client row (docs/PLAN.md section 5)."""
    user = User(
        email=email.lower(),
        password_hash=hash_password(TEST_PASSWORD),
        role="admin",
        is_active=is_active,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


CONFIG_SNAPSHOT = {
    "benchmark_mode": "account_avg",
    "waste_multiplier": 1.5,
    "min_spend": 1000.0,
    "min_clicks": 100,
    "min_spend_zero_conv": 1000.0,
    "max_cut_pct": 0.6,
}


def make_upload(db: Session, client: Client, *, status: str = "validated") -> AdDataUpload:
    """A committed AdDataUpload row for `client`. No bytes are written to storage."""
    upload = AdDataUpload(
        client_id=client.id,
        original_filename="august.csv",
        file_path=f"uploads/{client.id}/{uuid4().hex}.csv",
        file_sha256=uuid4().hex,
        row_count=900,
        date_range_start=date(2026, 8, 1),
        date_range_end=date(2026, 8, 31),
        status=status,
        validation_report={"errors": [], "warnings": []},
    )
    db.add(upload)
    db.commit()
    db.refresh(upload)
    return upload


def make_run(
    db: Session,
    client: Client,
    upload: AdDataUpload | None = None,
    *,
    status: str = "done",
    review_status: str = "pending",
    created_at: datetime | None = None,
    headline_waste: Decimal | None = Decimal("52000.00"),
    segments: tuple[tuple[str, str, str, bool], ...] = (),
) -> AnalysisRun:
    """A committed AnalysisRun for `client`, optionally with its WasteReport rows.

    `segments` entries are (dimension, segment_value, wasted_spend, is_flagged); one
    WasteReport is created per distinct dimension and its total_wasted_spend is the sum of
    that dimension's segments. With the default empty tuple the run carries no reports,
    which is all a status-polling or review-queue test needs.
    """
    if upload is None:
        upload = make_upload(db, client)
    run = AnalysisRun(
        client_id=client.id,
        upload_id=upload.id,
        config_snapshot=dict(CONFIG_SNAPSHOT),
        status=status,
        review_status=review_status,
        headline_waste=headline_waste,
        created_at=created_at or datetime(2026, 9, 1, 12, 0, tzinfo=UTC),
    )
    db.add(run)
    db.flush()

    reports: dict[str, WasteReport] = {}
    for dimension, segment_value, wasted, flagged in segments:
        if dimension not in reports:
            report = WasteReport(
                run_id=run.id,
                client_id=client.id,
                upload_id=upload.id,
                dimension=dimension,
                total_spend=Decimal("100000.00"),
                total_wasted_spend=Decimal("0.00"),
                benchmark_cpa=Decimal("800.00"),
            )
            db.add(report)
            db.flush()
            reports[dimension] = report
        report = reports[dimension]
        report.total_wasted_spend = report.total_wasted_spend + Decimal(wasted)
        db.add(
            SegmentMetric(
                report_id=report.id,
                segment_value=segment_value,
                spend=Decimal("84000.00"),
                impressions=100000,
                clicks=2000,
                conversions=40,
                revenue=Decimal("60000.00"),
                cpa=Decimal("2100.00"),
                is_significant=True,
                is_flagged=flagged,
                wasted_spend=Decimal(wasted),
            )
        )
    db.commit()
    db.refresh(run)
    return run


AUDIENCE_NETWORK_REASON = (
    "Audience Network spent Rs. 84,000 at Rs. 2,100 per conversion — "
    "2.6× your placement average of Rs. 800. Cut Rs. 50,400 (60%)."
)


def make_approved_run(
    db: Session,
    client: Client,
    *,
    with_report: bool = True,
    status: str = "done",
    review_status: str = "approved",
) -> AnalysisRun:
    """One finished analysis for `client`, carrying the plan's known placement numbers.

    These are the Stage 1 optimizer test numbers: audience_network spends 84,000 at a CPA of
    2,100 against a placement benchmark of 800 and wastes 52,000; reels spends 1,000 with
    zero conversions and wastes all of it; headline waste is 53,000 of 100,900 total spend.

    `with_report=False` stops after the run row, for a caller that only needs an approved run
    to exist; every test in this stage wants the report, so they all take the default.

    ctr/cvr/roas and flag_reason are not columns on segment_metrics (docs/PLAN.md §4) —
    get_report() derives them, so nothing here sets them.
    """
    upload = make_upload(db, client)
    run = AnalysisRun(
        client_id=client.id,
        upload_id=upload.id,
        config_snapshot=dict(CONFIG_SNAPSHOT),
        status=status,
        review_status=review_status,
        headline_waste=Decimal("53000.00"),
    )
    db.add(run)
    db.flush()

    if not with_report:
        db.commit()
        db.refresh(run)
        return run

    report = WasteReport(
        run_id=run.id,
        client_id=client.id,
        upload_id=upload.id,
        dimension="placement",
        total_spend=Decimal("100900.00"),
        total_wasted_spend=Decimal("53000.00"),
        benchmark_cpa=Decimal("800.00"),
        generated_at=datetime(2026, 9, 16, 9, 30, tzinfo=UTC),
    )
    db.add(report)
    db.flush()

    db.add_all(
        [
            SegmentMetric(
                report_id=report.id,
                segment_value="audience_network",
                spend=Decimal("84000.00"),
                impressions=900000,
                clicks=12000,
                conversions=40,
                revenue=Decimal("60000.00"),
                cpa=Decimal("2100.00"),
                is_significant=True,
                is_flagged=True,
                wasted_spend=Decimal("52000.00"),
            ),
            SegmentMetric(
                report_id=report.id,
                segment_value="reels",
                spend=Decimal("1000.00"),
                impressions=20000,
                clicks=300,
                conversions=0,
                revenue=Decimal("0.00"),
                cpa=None,
                is_significant=True,
                is_flagged=True,
                wasted_spend=Decimal("1000.00"),
            ),
            SegmentMetric(
                report_id=report.id,
                segment_value="facebook_feed",
                spend=Decimal("15000.00"),
                impressions=200000,
                clicks=4000,
                conversions=30,
                revenue=Decimal("45000.00"),
                cpa=Decimal("500.00"),
                is_significant=True,
                is_flagged=False,
                wasted_spend=Decimal("0.00"),
            ),
            SegmentMetric(
                report_id=report.id,
                segment_value="messenger_inbox",
                spend=Decimal("900.00"),
                impressions=1000,
                clicks=20,
                conversions=1,
                revenue=Decimal("1200.00"),
                cpa=Decimal("900.00"),
                is_significant=False,
                is_flagged=False,
                wasted_spend=Decimal("0.00"),
            ),
        ]
    )
    db.add(
        Recommendation(
            report_id=report.id,
            dimension="placement",
            segment_name="audience_network",
            current_spend=Decimal("84000.00"),
            recommended_cut=Decimal("50400.00"),
            reason=AUDIENCE_NETWORK_REASON,
        )
    )
    db.commit()
    db.refresh(run)
    return run


# Smallest byte strings that still start with the real magic numbers.
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"0" * 64
JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"0" * 64
PDF_BYTES = b"%PDF-1.7\n" + b"0" * 64


def make_invoice(
    db: Session,
    client: Client,
    *,
    status: str = "issued",
    total: Decimal = Decimal("19600.00"),
    number: str = "INV-2026-0001",
    base_fee: Decimal = Decimal("15000.00"),
    recovered: Decimal = Decimal("23000.00"),
    pct: Decimal = Decimal("20.00"),
    due_date: date = date(2026, 10, 7),
    amount_paid: Decimal = Decimal("0.00"),
) -> Invoice:
    """A committed invoice for `client`, September 2026 by default.

    The defaults agree with each other: base 15,000 + 20% of 23,000 recovered waste = a 4,600
    performance fee, so `total` is 19,600. If you override `base_fee`, `recovered` or `pct`,
    pass a matching `total` so the row stays internally consistent.
    """
    performance_fee = (recovered * pct / Decimal("100")).quantize(Decimal("0.01"))
    invoice = Invoice(
        invoice_number=number,
        client_id=client.id,
        period_start=date(2026, 9, 1),
        period_end=date(2026, 9, 30),
        due_date=due_date,
        base_fee=base_fee,
        suggested_recovered_waste=recovered,
        confirmed_recovered_waste=recovered,
        performance_fee=performance_fee,
        total=total,
        amount_paid=amount_paid,
        status=status,
        issued_at=None if status == "draft" else utcnow(),
    )
    db.add(invoice)
    db.commit()
    db.refresh(invoice)
    return invoice


def make_method(
    db: Session,
    type: str = "jazzcash",
    identifier: str = "03001234567",
    *,
    account_title: str = "Ali Raza",
    instructions: str | None = "Send from your JazzCash app to this wallet.",
    is_active: bool = True,
    sort_order: int = 0,
) -> PaymentMethod:
    """A committed PaymentMethod row. `type` shadows the builtin only inside this function."""
    method = PaymentMethod(
        type=type,
        account_title=account_title,
        account_identifier=identifier,
        instructions=instructions,
        is_active=is_active,
        sort_order=sort_order,
    )
    db.add(method)
    db.commit()
    db.refresh(method)
    return method
