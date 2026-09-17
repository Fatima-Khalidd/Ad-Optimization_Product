import io
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.models import AdDataUpload, AnalysisRun, Client
from app.pipeline.analyzer import account_total_spend, analyze_all_dimensions
from app.pipeline.config import PipelineConfig
from app.pipeline.data_generator import write_sample_csv
from app.pipeline.loader import load_csv
from app.pipeline.optimizer import headline_waste as pipeline_headline_waste
from app.services.analysis import create_run, execute_run, get_report, latest_report, to_money
from app.services.storage import get_storage
from app.services.upload import create_upload

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def get_upload_bytes(session: Session, run: AnalysisRun) -> bytes:
    """The exact bytes the run was analysed from - read back through the same storage
    interface `_persist_analysis` uses, so the "expected" side of a test is computed from
    the source file, never from the report object under test."""
    upload = session.get(AdDataUpload, run.upload_id)
    return get_storage().read(upload.file_path)


WASTE = {"placement": {"audience_network": 3.0}}


def _done_run(
    session: Session, client: Client, tmp_path: Path, name: str = "s.csv", seed: int = 42
) -> AnalysisRun:
    # A different seed means different bytes, so a second sample is not a duplicate upload.
    path = write_sample_csv(tmp_path / name, days=30, seed=seed, waste=WASTE)
    upload = create_upload(session, client, name, path.read_bytes())
    run = create_run(session, client, upload.id)
    execute_run(run.id)
    session.expire_all()
    return session.get(AnalysisRun, run.id)


def _approve(session: Session, run: AnalysisRun) -> None:
    run.review_status = "approved"  # Stage 6 gives the admin a real endpoint for this
    session.commit()


def test_a_pending_run_has_no_report_for_the_client(
    session: Session, client_row: Client, tmp_path: Path
):
    run = _done_run(session, client_row, tmp_path)
    assert run.status == "done" and run.review_status == "pending"

    with pytest.raises(NotFoundError) as excinfo:
        get_report(session, client_row.id, run.id)

    assert excinfo.value.status_code == 404


def test_an_approved_run_returns_the_full_report(
    session: Session, client_row: Client, tmp_path: Path
):
    run = _done_run(session, client_row, tmp_path)
    _approve(session, run)

    report = get_report(session, client_row.id, run.id)

    assert report.run_id == run.id
    assert report.upload_id == run.upload_id
    assert [d.dimension for d in report.dimensions] == ["placement", "age_group", "time_slot"]
    assert report.headline_waste == run.headline_waste
    assert report.total_spend == max(d.total_spend for d in report.dimensions)
    assert report.config_snapshot == run.config_snapshot
    assert str(report.date_range_start) == "2026-08-01"
    assert report.recommendations, "the injected waste must produce at least one recommendation"
    assert report.recommendations == sorted(
        report.recommendations, key=lambda r: r.recommended_cut, reverse=True
    )


def test_report_total_spend_is_the_true_account_total_from_the_file(
    session: Session, client_row: Client, tmp_path: Path
):
    """F1: `total_spend` must be `analyzer.account_total_spend(df)`, computed independently
    here straight from the fixture file - NOT derived from the report object under test
    (that was the bug in the test this replaces: it re-derived its own expectation from
    `max(d.total_spend for d in report.dimensions)`, so it could never catch F1)."""
    run = _done_run(session, client_row, tmp_path)
    _approve(session, run)

    report = get_report(session, client_row.id, run.id)

    loaded = load_csv(io.BytesIO(get_upload_bytes(session, run)), PipelineConfig())
    assert loaded.ok, loaded.errors
    expected_total = to_money(account_total_spend(loaded.df))

    assert report.total_spend == expected_total


def test_recovery_pct_is_headline_waste_over_the_true_account_total(
    session: Session, client_row: Client, tmp_path: Path
):
    """F1: `recovery_pct` must be computed against the true account total, not the
    (possibly understated) largest per-dimension total - the expected value here is
    computed independently from the fixture file, not from the object under test."""
    run = _done_run(session, client_row, tmp_path)
    _approve(session, run)

    report = get_report(session, client_row.id, run.id)

    loaded = load_csv(io.BytesIO(get_upload_bytes(session, run)), PipelineConfig())
    assert loaded.ok, loaded.errors
    results = analyze_all_dimensions(loaded.df, PipelineConfig())
    expected_total = to_money(account_total_spend(loaded.df))
    expected_waste = to_money(pipeline_headline_waste(results))
    expected_pct = (expected_waste / expected_total * 100).quantize(Decimal("0.01"))

    assert report.recovery_pct == expected_pct
    assert Decimal("0") < report.recovery_pct < Decimal("100")


def test_report_total_spend_on_partially_populated_data_is_the_account_total_not_the_max_dimension(
    session: Session, client_row: Client
):
    """F1 (CRITICAL): on `partial_dimensions.csv`, no single dimension is fully populated -
    every dimension's own total_spend is 1500.00, but the true account total (every row's
    spend, summed once) is 3500.00. Getting this wrong understates spend by 2.33x and
    inflates recovery_pct by the same factor."""
    fixture = FIXTURES / "partial_dimensions.csv"
    upload = create_upload(session, client_row, "partial_dimensions.csv", fixture.read_bytes())
    run = create_run(session, client_row, upload.id)
    execute_run(run.id)
    session.expire_all()
    run = session.get(AnalysisRun, run.id)
    _approve(session, run)

    report = get_report(session, client_row.id, run.id)

    assert report.total_spend == Decimal("3500.00")
    assert all(d.total_spend == Decimal("1500.00") for d in report.dimensions)

    expected_pct = (report.headline_waste / Decimal("3500.00") * 100).quantize(Decimal("0.01"))
    assert report.recovery_pct == expected_pct


def test_segments_carry_derived_rates_and_a_flag_reason(
    session: Session, client_row: Client, tmp_path: Path
):
    run = _done_run(session, client_row, tmp_path)
    _approve(session, run)

    report = get_report(session, client_row.id, run.id)
    placement = next(d for d in report.dimensions if d.dimension == "placement")
    flagged = [s for s in placement.segments if s.is_flagged]

    assert [s.segment for s in flagged] == ["audience_network"]
    assert flagged[0].flag_reason == "high_cpa"
    assert flagged[0].is_significant
    assert flagged[0].ctr == pytest.approx(flagged[0].clicks / flagged[0].impressions)
    assert flagged[0].cvr == pytest.approx(flagged[0].conversions / flagged[0].clicks)
    assert flagged[0].roas == pytest.approx(float(flagged[0].revenue) / float(flagged[0].spend))
    assert all(s.flag_reason is None for s in placement.segments if not s.is_flagged)
    assert placement.segments == sorted(placement.segments, key=lambda s: s.spend, reverse=True)


def test_a_client_cannot_read_another_tenants_report(
    session: Session, client_row: Client, other_client_row: Client, tmp_path: Path
):
    run = _done_run(session, other_client_row, tmp_path)
    _approve(session, run)

    with pytest.raises(NotFoundError):
        get_report(session, client_row.id, run.id)


def test_latest_report_is_none_until_a_run_is_approved(
    session: Session, client_row: Client, tmp_path: Path
):
    run = _done_run(session, client_row, tmp_path)

    assert latest_report(session, client_row.id) is None

    _approve(session, run)
    assert latest_report(session, client_row.id).run_id == run.id


def test_latest_report_picks_the_newest_approved_run(
    session: Session, client_row: Client, tmp_path: Path
):
    older = _done_run(session, client_row, tmp_path, "older.csv", seed=42)
    _approve(session, older)
    newer = _done_run(session, client_row, tmp_path, "newer.csv", seed=43)
    _approve(session, newer)

    assert latest_report(session, client_row.id).run_id == newer.id


def test_latest_report_ignores_other_tenants(
    session: Session, client_row: Client, other_client_row: Client, tmp_path: Path
):
    theirs = _done_run(session, other_client_row, tmp_path, "theirs.csv")
    _approve(session, theirs)

    assert latest_report(session, client_row.id) is None
