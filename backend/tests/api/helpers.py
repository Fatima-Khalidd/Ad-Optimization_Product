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
from app.models import AdDataUpload, AnalysisRun, Client, SegmentMetric, User, WasteReport

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
