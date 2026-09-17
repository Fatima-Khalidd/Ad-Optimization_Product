import io  # noqa: F401 - used by Task 5's tests appended to this same file
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.core.db import session_scope
from app.core.errors import InvalidUploadError, NotFoundError
from app.models import AdDataUpload, AnalysisRun, Client
from app.pipeline.config import PipelineConfig
from app.services.analysis import create_run, get_run, to_money
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
