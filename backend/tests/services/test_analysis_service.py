import io
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import session_scope
from app.core.errors import InvalidUploadError, NotFoundError
from app.models import AdDataUpload, AnalysisRun, Client, SegmentMetric, WasteReport
from app.models import Recommendation as RecommendationRow
from app.pipeline.analyzer import analyze_all_dimensions
from app.pipeline.config import PipelineConfig
from app.pipeline.data_generator import write_sample_csv
from app.pipeline.loader import load_csv
from app.pipeline.optimizer import headline_waste
from app.services.analysis import create_run, execute_run, get_run, to_money, to_money_or_none
from app.services.storage import get_storage
from app.services.upload import create_upload

HEADER = (
    b"date,campaign_id,placement,age_group,gender,device,time_slot,"
    b"spend,impressions,clicks,conversions,revenue\n"
)
GOOD = HEADER + b"2026-08-01,C1,facebook_feed,25-34,male,mobile,morning,1200.50,10000,250,5,12500\n"
BAD = HEADER + b"2026-08-01,C1,facebook_feed,25-34,male,mobile,morning,abc,1000,20,1,500\n"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (1200.5, Decimal("1200.50")),
        (0.0, Decimal("0.00")),
        (5176.470588235294, Decimal("5176.47")),
        (0.125, Decimal("0.13")),  # ROUND_HALF_UP, not banker's rounding
        (2.5, Decimal("2.50")),
    ],
)
def test_to_money_quantises_to_two_places_half_up(raw: float, expected: Decimal):
    value = to_money(raw)

    assert value == expected
    assert value.as_tuple().exponent == -2


def test_session_scope_uses_the_same_database_as_get_session(session: Session, client_row: Client):
    upload = create_upload(session, client_row, "aug.csv", GOOD)

    with session_scope() as other:
        assert other.get(AdDataUpload, upload.id) is not None


def test_create_run_queues_a_run_with_a_config_snapshot(session: Session, client_row: Client):
    upload = create_upload(session, client_row, "aug.csv", GOOD)

    run = create_run(session, client_row, upload.id)

    assert run.client_id == client_row.id
    assert run.upload_id == upload.id
    assert run.status == "queued"
    assert run.review_status == "pending"
    assert run.headline_waste is None
    assert run.config_snapshot == PipelineConfig().to_dict()
    assert PipelineConfig.from_overrides(run.config_snapshot) == PipelineConfig()


def test_create_run_snapshots_the_clients_overrides(session: Session, client_row: Client):
    client_row.config_overrides = {"waste_multiplier": 2.0, "min_spend": 1000}
    session.commit()
    upload = create_upload(session, client_row, "aug.csv", GOOD)

    run = create_run(session, client_row, upload.id)

    assert run.config_snapshot["waste_multiplier"] == 2.0
    assert run.config_snapshot["min_spend"] == 1000
    assert run.config_snapshot["min_clicks"] == PipelineConfig().min_clicks


def test_create_run_rejects_an_upload_that_failed_validation(session: Session, client_row: Client):
    upload = create_upload(session, client_row, "broken.csv", BAD)
    assert upload.status == "failed"

    with pytest.raises(InvalidUploadError) as excinfo:
        create_run(session, client_row, upload.id)

    assert excinfo.value.status_code == 422
    assert excinfo.value.detail["upload_id"] == upload.id


def test_create_run_on_another_tenants_upload_is_not_found(
    session: Session, client_row: Client, other_client_row: Client
):
    theirs = create_upload(session, other_client_row, "theirs.csv", GOOD)

    with pytest.raises(NotFoundError):
        create_run(session, client_row, theirs.id)


def test_create_run_reuses_an_in_flight_run_for_the_same_upload(
    session: Session, client_row: Client
):
    upload = create_upload(session, client_row, "aug.csv", GOOD)

    first = create_run(session, client_row, upload.id)
    second = create_run(session, client_row, upload.id)

    assert second.id == first.id
    rows = session.scalars(select(AnalysisRun).where(AnalysisRun.upload_id == upload.id)).all()
    assert len(rows) == 1


def test_create_run_starts_a_fresh_run_once_the_previous_one_is_done(
    session: Session, client_row: Client
):
    upload = create_upload(session, client_row, "aug.csv", GOOD)

    first = create_run(session, client_row, upload.id)
    first.status = "done"
    session.commit()

    second = create_run(session, client_row, upload.id)

    assert second.id != first.id
    rows = session.scalars(select(AnalysisRun).where(AnalysisRun.upload_id == upload.id)).all()
    assert len(rows) == 2


def test_create_run_starts_a_fresh_run_once_the_previous_one_failed(
    session: Session, client_row: Client
):
    upload = create_upload(session, client_row, "aug.csv", GOOD)

    first = create_run(session, client_row, upload.id)
    first.status = "failed"
    session.commit()

    second = create_run(session, client_row, upload.id)

    assert second.id != first.id
    rows = session.scalars(select(AnalysisRun).where(AnalysisRun.upload_id == upload.id)).all()
    assert len(rows) == 2


def test_create_run_reuses_a_running_run_still_inside_the_reuse_window(
    session: Session, client_row: Client
):
    from datetime import timedelta

    from app.models._types import utcnow

    upload = create_upload(session, client_row, "aug.csv", GOOD)

    first = create_run(session, client_row, upload.id)
    first.status = "running"
    first.created_at = utcnow() - timedelta(minutes=5)
    session.commit()

    second = create_run(session, client_row, upload.id)

    assert second.id == first.id
    rows = session.scalars(select(AnalysisRun).where(AnalysisRun.upload_id == upload.id)).all()
    assert len(rows) == 1


def test_create_run_does_not_reuse_a_stale_running_run_past_the_reuse_window(
    session: Session, client_row: Client
):
    """F4: a worker that died mid-run leaves a `running` row forever otherwise, blocking
    every later POST /api/analyze/{id} for that client+upload. Past the reuse window a
    fresh run must be created instead."""
    from datetime import timedelta

    from app.models._types import utcnow
    from app.services.analysis import ANALYSIS_REUSE_WINDOW_MINUTES

    upload = create_upload(session, client_row, "aug.csv", GOOD)

    first = create_run(session, client_row, upload.id)
    first.status = "running"
    first.created_at = utcnow() - timedelta(minutes=ANALYSIS_REUSE_WINDOW_MINUTES + 15)
    session.commit()

    second = create_run(session, client_row, upload.id)

    assert second.id != first.id
    rows = session.scalars(select(AnalysisRun).where(AnalysisRun.upload_id == upload.id)).all()
    assert len(rows) == 2


def test_get_run_is_tenant_scoped(session: Session, client_row: Client, other_client_row: Client):
    theirs_upload = create_upload(session, other_client_row, "theirs.csv", GOOD)
    theirs_run = create_run(session, other_client_row, theirs_upload.id)

    assert get_run(session, other_client_row.id, theirs_run.id).id == theirs_run.id
    with pytest.raises(NotFoundError):
        get_run(session, client_row.id, theirs_run.id)


def test_get_run_missing_id_is_not_found(session: Session, client_row: Client):
    with pytest.raises(NotFoundError):
        get_run(session, client_row.id, 9999)
    assert session.get(AnalysisRun, 9999) is None


def test_to_money_rejects_non_finite_input():
    with pytest.raises(ValueError):
        to_money(float("nan"))
    with pytest.raises(ValueError):
        to_money(float("inf"))


def test_to_money_or_none_passes_through_none():
    from app.services.analysis import to_money_or_none

    assert to_money_or_none(None) is None
    assert to_money_or_none(1.005) == Decimal("1.01")


def test_to_money_hand_checked_values():
    assert to_money(210794.47925619833) == Decimal("210794.48")
    assert to_money(2.675) == Decimal("2.68")


def test_to_money_short_circuits_an_already_decimal_value():
    # Decimal("2.675") is exact; if this round-tripped through float it would become
    # 2.67499999999999982236431605997495353221893310546875 and round DOWN to 2.67.
    assert to_money(Decimal("2.675")) == Decimal("2.68")
    # A value no float can represent exactly - proves there is no float round-trip.
    assert to_money(Decimal("123456789012.345")) == Decimal("123456789012.35")


def test_to_money_rejects_a_non_finite_decimal():
    with pytest.raises(ValueError):
        to_money(Decimal("NaN"))


def test_create_run_invalid_override_propagates_value_error(session: Session, client_row: Client):
    upload = create_upload(session, client_row, "aug.csv", GOOD)
    client_row.config_overrides = {"waste_multiplier": "not-a-number"}
    session.commit()

    with pytest.raises(ValueError):
        create_run(session, client_row, upload.id)


def test_session_scope_commits_on_success(client_row: Client):
    with session_scope() as s:
        client = s.get(Client, client_row.id)
        client.business_name = "Renamed Traders"

    with session_scope() as s:
        assert s.get(Client, client_row.id).business_name == "Renamed Traders"


def test_session_scope_rolls_back_on_exception(client_row: Client):
    with pytest.raises(RuntimeError):
        with session_scope() as s:
            upload = AdDataUpload(
                client_id=client_row.id,
                original_filename="x.csv",
                file_path="uploads/x/x.csv",
                file_sha256="a" * 64,
                row_count=0,
                status="validated",
                validation_report={"errors": [], "warnings": []},
            )
            s.add(upload)
            s.flush()
            raise RuntimeError("boom")

    with session_scope() as s:
        from sqlalchemy import select

        rows = s.scalars(select(AdDataUpload).where(AdDataUpload.client_id == client_row.id)).all()
        assert list(rows) == []


WASTE = {"placement": {"audience_network": 3.0}}


def _upload_sample(session: Session, client: Client, tmp_path: Path) -> AdDataUpload:
    path = write_sample_csv(tmp_path / "sample.csv", days=30, seed=42, waste=WASTE)
    return create_upload(session, client, "sample.csv", path.read_bytes())


def _expected(raw: bytes):
    result = load_csv(io.BytesIO(raw), PipelineConfig())
    assert result.ok, result.errors
    return analyze_all_dimensions(result.df, PipelineConfig())


def test_execute_run_persists_every_dimension_segment_and_recommendation(
    session: Session, client_row: Client, tmp_path: Path
):
    upload = _upload_sample(session, client_row, tmp_path)
    run = create_run(session, client_row, upload.id)
    expected = _expected(get_storage().read(upload.file_path))

    execute_run(run.id)

    session.expire_all()
    run = session.get(AnalysisRun, run.id)
    assert run.status == "done"
    assert run.error_message is None
    assert run.review_status == "pending", "approval is a Stage 6 admin action"
    assert run.headline_waste == to_money(headline_waste(expected))

    reports = session.scalars(
        select(WasteReport).where(WasteReport.run_id == run.id).order_by(WasteReport.id)
    ).all()
    assert [r.dimension for r in reports] == ["placement", "age_group", "time_slot"]
    for report in reports:
        dim = expected[report.dimension]
        assert report.client_id == client_row.id
        assert report.upload_id == upload.id
        assert report.total_spend == to_money(dim.total_spend)
        assert report.total_wasted_spend == to_money(dim.total_wasted_spend)
        assert report.benchmark_cpa == to_money_or_none(dim.benchmark_cpa)
        segments = session.scalars(
            select(SegmentMetric).where(SegmentMetric.report_id == report.id)
        ).all()
        assert len(segments) == len(dim.segments)

    placement = next(r for r in reports if r.dimension == "placement")
    flagged = session.scalars(
        select(SegmentMetric).where(
            SegmentMetric.report_id == placement.id, SegmentMetric.is_flagged.is_(True)
        )
    ).all()
    assert [s.segment_value for s in flagged] == ["audience_network"]
    assert flagged[0].wasted_spend > 0
    assert flagged[0].is_significant

    recs = session.scalars(
        select(RecommendationRow).where(RecommendationRow.report_id == placement.id)
    ).all()
    assert [r.segment_name for r in recs] == ["audience_network"]
    assert recs[0].recommended_cut <= flagged[0].spend
    assert "audience network" in recs[0].reason.lower()


def test_execute_run_stores_money_as_two_place_decimals(
    session: Session, client_row: Client, tmp_path: Path
):
    upload = _upload_sample(session, client_row, tmp_path)
    run = create_run(session, client_row, upload.id)

    execute_run(run.id)

    session.expire_all()
    values = session.scalars(select(SegmentMetric.spend)).all()
    assert values
    for value in values:
        assert isinstance(value, Decimal)
        assert value.as_tuple().exponent == -2


def test_execute_run_uses_the_snapshot_not_the_live_client_config(
    session: Session, client_row: Client, tmp_path: Path
):
    upload = _upload_sample(session, client_row, tmp_path)
    run = create_run(session, client_row, upload.id)
    expected = _expected(get_storage().read(upload.file_path))

    # The admin changes the client's thresholds after the run was queued: with a 99x
    # multiplier nothing would ever be flagged, so a zero headline would prove the bug.
    client_row.config_overrides = {"waste_multiplier": 99.0}
    session.commit()

    execute_run(run.id)

    session.expire_all()
    run = session.get(AnalysisRun, run.id)
    assert run.headline_waste == to_money(headline_waste(expected))
    assert run.headline_waste > 0


def test_execute_run_marks_the_run_failed_when_the_file_is_gone(
    session: Session, client_row: Client, tmp_path: Path
):
    upload = _upload_sample(session, client_row, tmp_path)
    run = create_run(session, client_row, upload.id)
    get_storage().delete(upload.file_path)

    execute_run(run.id)

    session.expire_all()
    run = session.get(AnalysisRun, run.id)
    assert run.status == "failed"
    # The message is client-facing: no storage key (tenant id / content hash) may leak
    # into it. The full detail (including the key) goes to logger.exception instead.
    assert upload.file_sha256 not in run.error_message
    assert upload.file_path not in run.error_message
    assert session.scalars(select(WasteReport).where(WasteReport.run_id == run.id)).all() == []


def test_execute_run_on_an_unknown_id_is_a_no_op(session: Session):
    # `session` isn't used directly, but pulls in the `bound_engine` fixture so the
    # in-memory database (and its tables) exists for `execute_run`'s own session_scope()
    # to connect to - without it there is no database at all, not just no matching row.
    execute_run(987654)  # must not raise


def test_execute_run_leaves_no_partial_rows_when_analysis_blows_up(
    session: Session, client_row: Client, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """A forced failure mid-analysis must not leave any WasteReport/SegmentMetric/
    Recommendation rows behind - the whole persist is one atomic unit."""
    upload = _upload_sample(session, client_row, tmp_path)
    run = create_run(session, client_row, upload.id)

    def _boom(df, config):
        raise RuntimeError("forced failure for the atomicity test")

    monkeypatch.setattr("app.services.analysis.analyze_all_dimensions", _boom)

    execute_run(run.id)

    session.expire_all()
    run = session.get(AnalysisRun, run.id)
    assert run.status == "failed"
    assert run.error_message is not None
    assert "Traceback" not in run.error_message
    assert session.scalars(select(WasteReport).where(WasteReport.run_id == run.id)).all() == []
    assert session.scalars(select(SegmentMetric)).all() == []
    assert session.scalars(select(RecommendationRow)).all() == []


def test_execute_run_does_not_duplicate_rows_on_a_rerun(
    session: Session, client_row: Client, tmp_path: Path
):
    """The job refuses to re-run a non-queued run, so re-invoking it (e.g. a retried
    background task) never duplicates report rows."""
    upload = _upload_sample(session, client_row, tmp_path)
    run = create_run(session, client_row, upload.id)

    execute_run(run.id)
    execute_run(run.id)  # simulate a retry/duplicate dispatch of the same run

    session.expire_all()
    run = session.get(AnalysisRun, run.id)
    assert run.status == "done"
    reports = session.scalars(select(WasteReport).where(WasteReport.run_id == run.id)).all()
    assert [r.dimension for r in reports] == ["placement", "age_group", "time_slot"]
    assert len(reports) == 3


def test_execute_run_on_the_committed_sample_30d_fixture_matches_hand_checked_numbers(
    session: Session, client_row: Client
):
    """End-to-end against the fixture the CLI is hand-checked against (see
    `python -m app.pipeline.run tests/fixtures/sample_30d.csv`): placement's total waste
    of Rs. 210,794.48 and benchmark CPA of Rs. 356.78 are the same numbers a human
    reviewing the CLI output would see, just as two-place Decimals instead of rounded
    integers.
    """
    fixture = Path(__file__).resolve().parents[1] / "fixtures" / "sample_30d.csv"
    upload = create_upload(session, client_row, "sample_30d.csv", fixture.read_bytes())
    run = create_run(session, client_row, upload.id)

    execute_run(run.id)

    session.expire_all()
    run = session.get(AnalysisRun, run.id)
    assert run.status == "done"
    assert run.headline_waste == Decimal("210794.48")

    reports = session.scalars(
        select(WasteReport).where(WasteReport.run_id == run.id).order_by(WasteReport.id)
    ).all()
    assert len(reports) == 3

    placement = next(r for r in reports if r.dimension == "placement")
    assert placement.total_wasted_spend == Decimal("210794.48")
    assert placement.benchmark_cpa == Decimal("356.78")

    for report in reports:
        segments = session.scalars(
            select(SegmentMetric).where(SegmentMetric.report_id == report.id)
        ).all()
        assert segments  # every dimension in this fixture has data
        for value in (report.total_spend, report.total_wasted_spend):
            assert isinstance(value, Decimal)
            assert value.as_tuple().exponent == -2

    recs = session.scalars(
        select(RecommendationRow).where(RecommendationRow.report_id == placement.id)
    ).all()
    assert recs
    assert all(rec.reason for rec in recs)


def test_execute_run_does_not_touch_a_run_already_done(
    session: Session, client_row: Client, tmp_path: Path
):
    """The atomic claim (`UPDATE ... WHERE status = 'queued'`) means a run already in a
    terminal state is left completely alone on a re-dispatch: no new report rows, status
    unchanged."""
    upload = _upload_sample(session, client_row, tmp_path)
    run = create_run(session, client_row, upload.id)
    execute_run(run.id)

    session.expire_all()
    run = session.get(AnalysisRun, run.id)
    assert run.status == "done"
    before = session.scalars(select(WasteReport).where(WasteReport.run_id == run.id)).all()
    assert len(before) == 3

    execute_run(run.id)  # re-dispatch of an already-done run

    session.expire_all()
    run = session.get(AnalysisRun, run.id)
    assert run.status == "done"
    after = session.scalars(select(WasteReport).where(WasteReport.run_id == run.id)).all()
    assert len(after) == 3
    assert [r.id for r in after] == [r.id for r in before]


def test_execute_run_writes_a_zero_report_for_a_dimension_with_no_data(
    session: Session, client_row: Client
):
    """PLAN §1 #3: every dimension in DIMENSIONS gets a WasteReport row even when the
    upload has no data for it - here every row's time_slot is blank."""
    rows = [
        f"2026-08-{day:02d},C1,facebook_feed,25-34,male,mobile,,6000.00,10000,250,5,12500\n"
        for day in range(1, 6)
    ]
    csv_bytes = HEADER + b"".join(row.encode() for row in rows)
    upload = create_upload(session, client_row, "blank_time_slot.csv", csv_bytes)
    run = create_run(session, client_row, upload.id)

    execute_run(run.id)

    session.expire_all()
    run = session.get(AnalysisRun, run.id)
    assert run.status == "done"

    reports = session.scalars(
        select(WasteReport).where(WasteReport.run_id == run.id).order_by(WasteReport.id)
    ).all()
    assert len(reports) == 3

    blank = next(r for r in reports if r.dimension == "time_slot")
    assert blank.total_spend == Decimal("0.00")
    assert blank.total_wasted_spend == Decimal("0.00")
    assert blank.benchmark_cpa is None
    segments = session.scalars(
        select(SegmentMetric).where(SegmentMetric.report_id == blank.id)
    ).all()
    assert segments == []


def test_execute_run_truncates_a_very_long_error_message(
    session: Session, client_row: Client, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    upload = _upload_sample(session, client_row, tmp_path)
    run = create_run(session, client_row, upload.id)

    def _boom(df, config):
        raise RuntimeError("x" * 5000)

    monkeypatch.setattr("app.services.analysis.analyze_all_dimensions", _boom)

    execute_run(run.id)

    session.expire_all()
    run = session.get(AnalysisRun, run.id)
    assert run.status == "failed"
    assert len(run.error_message) <= 1000


# F3 (Stage 3 close-out #6): error_message is client-visible and must never leak a storage
# key, a server path, or the file's sha256 - `PermissionError` and a `ValueError` naming a
# storage key were both probed and found to leak. Only the small allowlist in
# app.services.analysis._SAFE_MESSAGES gets a specific message; everything else collapses
# to one generic sentence.
_LEAK_MARKERS = ("uploads/", "/", "\\", "sha256")


@pytest.mark.parametrize(
    "boom",
    [
        pytest.param(
            lambda: (_ for _ in ()).throw(
                PermissionError(r"[Errno 13] Permission denied: 'D:\storage\uploads\7\abc.csv'")
            ),
            id="permission_error_leaks_a_full_path",
        ),
        pytest.param(
            lambda: (_ for _ in ()).throw(
                ValueError("invalid storage key: 'uploads/1/deadbeef.csv'")
            ),
            id="value_error_leaks_a_storage_key",
        ),
        pytest.param(
            lambda: (_ for _ in ()).throw(RuntimeError("boom")),
            id="generic_runtime_error",
        ),
    ],
)
def test_execute_run_sanitises_leaky_exceptions_to_a_generic_message(
    session: Session,
    client_row: Client,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    boom,
):
    upload = _upload_sample(session, client_row, tmp_path)
    run = create_run(session, client_row, upload.id)

    def _raise(df, config):
        boom()

    monkeypatch.setattr("app.services.analysis.analyze_all_dimensions", _raise)

    execute_run(run.id)

    session.expire_all()
    run = session.get(AnalysisRun, run.id)
    assert run.status == "failed"
    assert run.error_message == "the analysis could not be completed"
    for marker in _LEAK_MARKERS:
        assert marker not in run.error_message
    assert upload.file_sha256 not in run.error_message


def test_execute_run_file_not_found_keeps_its_friendly_message(
    session: Session, client_row: Client, tmp_path: Path
):
    upload = _upload_sample(session, client_row, tmp_path)
    run = create_run(session, client_row, upload.id)
    get_storage().delete(upload.file_path)

    execute_run(run.id)

    session.expire_all()
    run = session.get(AnalysisRun, run.id)
    assert run.status == "failed"
    assert run.error_message == "the uploaded file could not be read"
