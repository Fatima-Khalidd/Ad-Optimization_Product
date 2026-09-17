from pathlib import Path

from fastapi.testclient import TestClient

from app.core.settings import get_settings
from app.pipeline.data_generator import write_sample_csv
from app.pipeline.loader import load_csv

HEADER = (
    "date,campaign_id,placement,age_group,gender,device,time_slot,"
    "spend,impressions,clicks,conversions,revenue\n"
)
GOOD_ROW = "2026-08-01,C1,facebook_feed,25-34,male,mobile,morning,1200.50,10000,250,5,12500\n"
BAD_CSV = HEADER + "2026-08-01,C1,facebook_feed,25-34,male,mobile,morning,abc,1000,20,1,500\n"


def _post(http: TestClient, name: str, body: bytes):
    return http.post("/api/uploads", files={"file": (name, body, "text/csv")})


def test_upload_happy_path_returns_201_and_a_validated_upload(client_a: TestClient, tmp_path: Path):
    path = write_sample_csv(tmp_path / "sample.csv", days=3, seed=5)

    response = _post(client_a, "sample.csv", path.read_bytes())

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "validated"
    assert body["original_filename"] == "sample.csv"
    assert body["row_count"] == 3 * 4 * 5 * 3 * 4
    assert body["date_range_start"] == "2026-08-01"
    assert body["validation_report"] == {"errors": [], "warnings": []}
    assert "client_id" not in body, "the response must not leak tenant ids"


def test_invalid_csv_returns_422_with_row_level_errors(client_a: TestClient):
    response = _post(client_a, "broken.csv", BAD_CSV.encode())

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["status"] == "failed"
    assert isinstance(detail["upload_id"], int)
    assert any(e["row"] == 1 and e["column"] == "spend" for e in detail["errors"]), detail


def test_invalid_csv_422_body_matches_the_uploadrejected_shape(client_a: TestClient):
    """F6: the 422 body is now built from `UploadRejected(...).model_dump()`, not a
    hand-written dict - the JSON shape Stage 4 depends on must not change."""
    response = _post(client_a, "broken.csv", BAD_CSV.encode())

    assert response.status_code == 422
    body = response.json()
    assert set(body.keys()) == {"detail"}
    assert set(body["detail"].keys()) == {"status", "upload_id", "errors", "warnings"}
    assert isinstance(body["detail"]["errors"], list)
    assert isinstance(body["detail"]["warnings"], list)


def test_duplicate_upload_returns_409_naming_the_first_upload(client_a: TestClient):
    first = _post(client_a, "aug.csv", (HEADER + GOOD_ROW).encode()).json()

    response = _post(client_a, "aug-again.csv", (HEADER + GOOD_ROW).encode())

    assert response.status_code == 409
    assert response.json()["detail"]["upload_id"] == first["id"]


def test_oversize_upload_returns_413(client_a: TestClient, monkeypatch):
    monkeypatch.setenv("MAX_UPLOAD_MB", "1")
    get_settings.cache_clear()
    body = (HEADER + GOOD_ROW * 20000).encode()  # ~1.5 MB
    assert len(body) > 1024 * 1024

    response = _post(client_a, "huge.csv", body)

    assert response.status_code == 413
    detail = response.json()["detail"]
    assert "larger than 1 MB" in detail["message"]
    assert detail["max_upload_mb"] == 1


def test_oversize_upload_is_rejected_by_content_length_before_parsing(
    client_a: TestClient, monkeypatch
):
    """A genuinely oversize body must be caught by the Content-Length short-circuit."""
    monkeypatch.setenv("MAX_UPLOAD_MB", "1")
    get_settings.cache_clear()
    body = (HEADER + GOOD_ROW * 20000).encode()  # ~1.5 MB, so Content-Length is genuine
    assert len(body) > 1024 * 1024

    response = _post(client_a, "huge.csv", body)

    assert response.status_code == 413
    detail = response.json()["detail"]
    assert detail["message"] == "file is larger than 1 MB"
    assert detail["max_upload_mb"] == 1


def test_upload_within_the_limit_still_succeeds(client_a: TestClient, monkeypatch):
    """The Content-Length short-circuit must not reject a legitimately sized upload."""
    monkeypatch.setenv("MAX_UPLOAD_MB", "1")
    get_settings.cache_clear()

    response = _post(client_a, "small.csv", (HEADER + GOOD_ROW).encode())

    assert response.status_code == 201, response.text


def test_upload_requires_authentication():
    from app.main import create_app

    anonymous = TestClient(create_app())

    response = _post(anonymous, "aug.csv", (HEADER + GOOD_ROW).encode())

    assert response.status_code == 401


def test_list_and_detail_are_scoped_to_the_caller(client_a: TestClient, client_b: TestClient):
    mine = _post(client_a, "mine.csv", (HEADER + GOOD_ROW).encode()).json()
    _post(client_b, "theirs.csv", (HEADER + GOOD_ROW).encode())

    listed = client_a.get("/api/uploads").json()

    assert [u["id"] for u in listed] == [mine["id"]]
    assert client_a.get(f"/api/uploads/{mine['id']}").json()["id"] == mine["id"]


def test_client_a_cannot_read_client_bs_upload(client_a: TestClient, client_b: TestClient):
    theirs = _post(client_b, "theirs.csv", (HEADER + GOOD_ROW).encode()).json()

    response = client_a.get(f"/api/uploads/{theirs['id']}")

    assert response.status_code == 404, "another tenant's id must look missing, not forbidden"
    assert response.json()["detail"] == "upload not found"


def test_template_csv_downloads_and_round_trips(client_a: TestClient, tmp_path: Path):
    response = client_a.get("/api/uploads/template.csv")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment" in response.headers["content-disposition"]

    path = tmp_path / "template.csv"
    path.write_bytes(response.content)
    result = load_csv(path)

    assert result.ok, result.errors
    assert result.row_count == 3


def test_the_downloaded_template_can_be_uploaded_as_is(client_a: TestClient):
    template = client_a.get("/api/uploads/template.csv").content

    response = _post(client_a, "template.csv", template)

    assert response.status_code == 201
    assert response.json()["status"] == "validated"


def test_admin_cannot_call_the_client_upload_route(admin_client: TestClient):
    response = _post(admin_client, "aug.csv", (HEADER + GOOD_ROW).encode())

    assert response.status_code == 403


def test_template_csv_is_public_and_needs_no_session_cookie(api: TestClient):
    """F5 / Stage 3 close-out #5: the template contains no tenant data, so it stays public
    while every other /api/uploads route requires a client session."""
    response = api.get("/api/uploads/template.csv")

    assert response.status_code == 200
    assert response.content.startswith(b"date,campaign_id,placement")


def test_upload_with_a_corrupt_client_override_is_422_not_500(
    client_a: TestClient, db, client_a_row
):
    """F2: create_upload calls PipelineConfig.from_overrides(client.config_overrides),
    which raises a plain ValueError on a corrupt override dict - that must not escape as a
    bare 500, mirroring the identical guard in app/routers/analysis.py."""
    from app.models import Client

    row = db.get(Client, client_a_row.id)
    row.config_overrides = {"waste_multiplier": "not-a-number"}
    db.commit()

    response = _post(client_a, "aug.csv", (HEADER + GOOD_ROW).encode())

    assert response.status_code == 422, response.text
    assert "detail" in response.json()
