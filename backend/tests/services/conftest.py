from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app.core.settings import get_settings
from app.models import Client, User
from app.schemas.reports import DimensionOut, RecommendationOut, ReportOut, SegmentOut


@pytest.fixture(autouse=True)
def storage_root(tmp_path: Path, monkeypatch):
    """Every service test writes its files into its own tmp_path."""
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path / "storage"))
    get_settings.cache_clear()
    yield tmp_path / "storage"
    get_settings.cache_clear()


def _make_client(session: Session, email: str, name: str) -> Client:
    user = User(email=email, password_hash="x", role="client", is_active=True)
    session.add(user)
    session.flush()
    client = Client(
        user_id=user.id,
        business_name=name,
        pricing_model="hybrid",
        base_fee=Decimal("15000"),
        performance_fee_pct=Decimal("20"),
        config_overrides={},
    )
    session.add(client)
    session.commit()
    session.refresh(client)
    return client


@pytest.fixture
def client_row(session: Session) -> Client:
    return _make_client(session, "a@example.com", "Alpha Traders")


@pytest.fixture
def other_client_row(session: Session) -> Client:
    return _make_client(session, "b@example.com", "Beta Traders")


# --- PDF report fixtures ---------------------------------------------------------------------
#
# Hand-built ReportOut fixtures with known numbers (see the table in the Stage 5 plan).
#
# The renderer must never recompute anything, so these objects are written out literally rather
# than produced by the pipeline: if pdf.py and the dashboard disagree, these numbers say who is
# wrong.

TOTAL_SPEND = 100900.0
HEADLINE_WASTE = 53000.0
RECOVERY_PCT = HEADLINE_WASTE / TOTAL_SPEND * 100  # 52.527... -> "52.5%"

CONFIG_SNAPSHOT = {
    "benchmark_mode": "account_avg",
    "waste_multiplier": 1.5,
    "min_spend": 1000.0,
    "min_clicks": 100,
    "min_spend_zero_conv": 1000.0,
    "max_cut_pct": 0.6,
}

AUDIENCE_NETWORK_REASON = (
    "Audience Network spent Rs. 84,000 at Rs. 2,100 per conversion — "
    "2.6× your placement average of Rs. 800. Cut Rs. 50,400 (60%)."
)
AGE_55_64_REASON = (
    "55-64 spent Rs. 20,000 at Rs. 4,000 per conversion — "
    "5.0× your age group average of Rs. 800. Cut Rs. 12,000 (60%)."
)
REELS_REASON = "Reels spent Rs. 1,000 with no conversions at all. Cut Rs. 600 (60%)."


@pytest.fixture
def make_segment():
    def _make(segment: str, spend: float, conversions: float, **kw) -> SegmentOut:
        clicks = kw.pop("clicks", 1000)
        impressions = kw.pop("impressions", clicks * 50)
        data = dict(
            segment=segment,
            spend=spend,
            impressions=impressions,
            clicks=clicks,
            conversions=conversions,
            revenue=kw.pop("revenue", 0.0),
            cpa=kw.pop("cpa", spend / conversions if conversions else None),
            ctr=clicks / impressions * 100 if impressions else 0.0,
            cvr=conversions / clicks * 100 if clicks else 0.0,
            roas=None,
            is_significant=kw.pop("is_significant", True),
            is_flagged=kw.pop("is_flagged", False),
            wasted_spend=kw.pop("wasted_spend", 0.0),
            flag_reason=kw.pop("flag_reason", None),
        )
        data.update(kw)
        return SegmentOut(**data)

    return _make


@pytest.fixture
def make_dimension():
    def _make(dimension: str, segments: list[SegmentOut], **kw) -> DimensionOut:
        return DimensionOut(
            dimension=dimension,
            benchmark_cpa=kw.pop("benchmark_cpa", 800.0),
            total_spend=kw.pop("total_spend", sum(s.spend for s in segments)),
            total_wasted_spend=kw.pop("total_wasted_spend", sum(s.wasted_spend for s in segments)),
            segments=segments,
        )

    return _make


@pytest.fixture
def make_report(make_segment, make_dimension):
    def _make(**overrides) -> ReportOut:
        placement = make_dimension(
            "placement",
            [
                make_segment(
                    "audience_network",
                    84000.0,
                    40,
                    clicks=12000,
                    revenue=60000.0,
                    cpa=2100.0,
                    is_flagged=True,
                    wasted_spend=52000.0,
                    flag_reason="high_cpa",
                ),
                make_segment(
                    "reels",
                    1000.0,
                    0,
                    clicks=300,
                    is_flagged=True,
                    wasted_spend=1000.0,
                    flag_reason="zero_conversions",
                ),
                make_segment("facebook_feed", 15000.0, 30, clicks=4000, revenue=45000.0),
                make_segment("messenger_inbox", 900.0, 1, clicks=20, is_significant=False),
            ],
        )
        age_group = make_dimension(
            "age_group",
            [
                make_segment("25-34", 64900.0, 100, clicks=18000, revenue=150000.0),
                make_segment("35-44", 16000.0, 25, clicks=5000, revenue=40000.0),
                make_segment(
                    "55-64",
                    20000.0,
                    5,
                    clicks=2000,
                    cpa=4000.0,
                    is_flagged=True,
                    wasted_spend=16000.0,
                    flag_reason="high_cpa",
                ),
            ],
        )
        time_slot = make_dimension(
            "time_slot", [], benchmark_cpa=None, total_spend=0.0, total_wasted_spend=0.0
        )
        data = dict(
            run_id=7,
            upload_id=3,
            generated_at=datetime(2026, 9, 16, 9, 30, tzinfo=UTC),
            date_range_start=date(2026, 8, 1),
            date_range_end=date(2026, 8, 31),
            total_spend=TOTAL_SPEND,
            headline_waste=HEADLINE_WASTE,
            recovery_pct=RECOVERY_PCT,
            dimensions=[placement, age_group, time_slot],
            recommendations=[
                RecommendationOut(
                    id=11,
                    dimension="placement",
                    segment_name="audience_network",
                    current_spend=84000.0,
                    recommended_cut=50400.0,
                    reason=AUDIENCE_NETWORK_REASON,
                ),
                RecommendationOut(
                    id=12,
                    dimension="age_group",
                    segment_name="55-64",
                    current_spend=20000.0,
                    recommended_cut=12000.0,
                    reason=AGE_55_64_REASON,
                ),
                RecommendationOut(
                    id=13,
                    dimension="placement",
                    segment_name="reels",
                    current_spend=1000.0,
                    recommended_cut=600.0,
                    reason=REELS_REASON,
                ),
            ],
            config_snapshot=dict(CONFIG_SNAPSHOT),
        )
        data.update(overrides)
        return ReportOut(**data)

    return _make


@pytest.fixture
def sample_report(make_report):
    return make_report()
