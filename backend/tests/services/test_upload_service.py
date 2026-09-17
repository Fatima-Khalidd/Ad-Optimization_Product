from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app.core.errors import DuplicateUploadError, FileTooLargeError, NotFoundError
from app.core.settings import get_settings
from app.models import Client
from app.pipeline.data_generator import write_sample_csv
from app.pipeline.loader import load_csv
from app.services.storage import get_storage
from app.services.upload import create_upload, get_upload, list_uploads, template_csv

HEADER = (
    b"date,campaign_id,placement,age_group,gender,device,time_slot,"
    b"spend,impressions,clicks,conversions,revenue\n"
)
GOOD_CSV = (
    HEADER
    + b"2026-08-01,C1,facebook_feed,25-34,male,mobile,morning,1200.50,10000,250,5,12500\n"
    + b"2026-08-03,C1,audience_network,25-34,female,mobile,evening,800,9000,180,0,0\n"
)
BAD_CSV = (
    HEADER
    + b"2026-08-01,C1,facebook_feed,25-34,male,mobile,morning,abc,1000,20,1,500\n"
    + b"not-a-date,C1,facebook_feed,25-34,male,mobile,morning,100,1000,20,1,500\n"
)


def test_valid_upload_is_stored_validated_and_summarised(session: Session, client_row: Client):
    upload = create_upload(session, client_row, "august.csv", GOOD_CSV)

    assert upload.id is not None
    assert upload.client_id == client_row.id
    assert upload.original_filename == "august.csv"
    assert upload.status == "validated"
    assert upload.row_count == 2
    assert str(upload.date_range_start) == "2026-08-01"
    assert str(upload.date_range_end) == "2026-08-03"
    assert upload.validation_report == {"errors": [], "warnings": []}
    assert upload.file_path == f"uploads/{client_row.id}/{upload.file_sha256}.csv"
    assert get_storage().read(upload.file_path) == GOOD_CSV


def test_invalid_upload_is_kept_with_row_level_errors(session: Session, client_row: Client):
    upload = create_upload(session, client_row, "broken.csv", BAD_CSV)

    assert upload.status == "failed"
    errors = upload.validation_report["errors"]
    assert any(e["row"] == 1 and e["column"] == "spend" for e in errors), errors
    assert any(e["row"] == 2 and e["column"] == "date" for e in errors), errors
    # the bytes are still stored, so the client can be shown exactly what they sent
    assert get_storage().read(upload.file_path) == BAD_CSV


def test_unreadable_bytes_fail_validation_instead_of_raising(session: Session, client_row: Client):
    upload = create_upload(session, client_row, "photo.jpg", b"\xff\xd8\xff\xe0\x00\x10JFIF")

    assert upload.status == "failed"
    assert upload.validation_report["errors"][0]["row"] is None
    assert "could not read the file as CSV" in upload.validation_report["errors"][0]["message"]


def test_same_bytes_twice_for_one_client_is_a_duplicate(session: Session, client_row: Client):
    first = create_upload(session, client_row, "august.csv", GOOD_CSV)

    with pytest.raises(DuplicateUploadError) as excinfo:
        create_upload(session, client_row, "august-copy.csv", GOOD_CSV)

    assert excinfo.value.detail["upload_id"] == first.id
    assert excinfo.value.status_code == 409


def test_the_same_bytes_from_another_client_are_not_a_duplicate(
    session: Session, client_row: Client, other_client_row: Client
):
    create_upload(session, client_row, "august.csv", GOOD_CSV)

    other = create_upload(session, other_client_row, "august.csv", GOOD_CSV)

    assert other.client_id == other_client_row.id
    assert other.file_path == f"uploads/{other_client_row.id}/{other.file_sha256}.csv"


def test_list_uploads_is_newest_first_and_tenant_scoped(
    session: Session, client_row: Client, other_client_row: Client
):
    first = create_upload(session, client_row, "one.csv", GOOD_CSV)
    second = create_upload(session, client_row, "two.csv", GOOD_CSV.replace(b"1200.50", b"1300.50"))
    create_upload(session, other_client_row, "theirs.csv", GOOD_CSV)

    listed = list_uploads(session, client_row.id)

    assert [u.id for u in listed] == [second.id, first.id]


def test_get_upload_from_another_tenant_is_not_found(
    session: Session, client_row: Client, other_client_row: Client
):
    theirs = create_upload(session, other_client_row, "theirs.csv", GOOD_CSV)

    with pytest.raises(NotFoundError) as excinfo:
        get_upload(session, client_row.id, theirs.id)

    assert excinfo.value.status_code == 404


def test_get_upload_missing_id_is_not_found(session: Session, client_row: Client):
    with pytest.raises(NotFoundError):
        get_upload(session, client_row.id, 4242)


def test_template_csv_round_trips_through_the_loader(tmp_path: Path):
    path = tmp_path / "template.csv"
    path.write_bytes(template_csv())

    result = load_csv(path)

    assert result.ok, result.errors
    assert result.warnings == []
    assert result.row_count == 3


def test_a_generated_sample_file_uploads_cleanly(
    session: Session, client_row: Client, tmp_path: Path
):
    path = write_sample_csv(tmp_path / "sample.csv", days=3, seed=5)

    upload = create_upload(session, client_row, "sample.csv", path.read_bytes())

    assert upload.status == "validated"
    assert upload.row_count == 3 * 4 * 5 * 3 * 4


def test_oversize_upload_is_rejected_before_storage_or_db(session: Session, client_row: Client):
    max_bytes = get_settings().max_upload_mb * 1024 * 1024
    oversize = HEADER + b"x" * (max_bytes + 1)

    with pytest.raises(FileTooLargeError) as excinfo:
        create_upload(session, client_row, "huge.csv", oversize)

    assert excinfo.value.status_code == 413
    assert list_uploads(session, client_row.id) == []
    storage_dir = get_storage().root / "uploads" / str(client_row.id)
    assert not storage_dir.exists()
