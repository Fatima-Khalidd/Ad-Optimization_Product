from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.models import AnalysisRun, Client
from app.pipeline.data_generator import write_sample_csv
from app.services.analysis import create_run, execute_run, get_report, latest_report
from app.services.upload import create_upload

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


def test_recovery_pct_is_headline_waste_over_total_spend(
    session: Session, client_row: Client, tmp_path: Path
):
    run = _done_run(session, client_row, tmp_path)
    _approve(session, run)

    report = get_report(session, client_row.id, run.id)

    expected = (report.headline_waste / report.total_spend * 100).quantize(Decimal("0.01"))
    assert report.recovery_pct == expected
    assert Decimal("0") < report.recovery_pct < Decimal("100")


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
