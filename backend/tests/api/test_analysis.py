import io
from decimal import Decimal
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AnalysisRun, Client
from app.pipeline.analyzer import analyze_all_dimensions
from app.pipeline.config import PipelineConfig
from app.pipeline.data_generator import write_sample_csv
from app.pipeline.loader import load_csv
from app.pipeline.optimizer import headline_waste
from app.services.analysis import to_money

WASTE = {"placement": {"audience_network": 3.0}}


def _sample_bytes(tmp_path: Path, name: str = "sample.csv", seed: int = 42) -> bytes:
    return write_sample_csv(tmp_path / name, days=30, seed=seed, waste=WASTE).read_bytes()


def _upload(http: TestClient, body: bytes, name: str = "sample.csv") -> int:
    response = http.post("/api/uploads", files={"file": (name, body, "text/csv")})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _approve(db: Session, run_id: int) -> None:
    run = db.get(AnalysisRun, run_id)
    run.review_status = "approved"  # Stage 6 replaces this with POST /api/admin/runs/{id}/approve
    db.commit()


def test_analyze_returns_202_and_the_run_reaches_done(
    client_a: TestClient, tmp_path: Path, db: Session
):
    upload_id = _upload(client_a, _sample_bytes(tmp_path))

    response = client_a.post(f"/api/analyze/{upload_id}")

    assert response.status_code == 202, response.text
    run = response.json()
    assert run["upload_id"] == upload_id
    assert run["review_status"] == "pending"
    assert "client_id" not in run

    # TestClient runs BackgroundTasks inside the request, so the job is already finished.
    polled = client_a.get(f"/api/runs/{run['id']}").json()
    assert polled["status"] == "done", polled
    assert polled["error_message"] is None
    assert Decimal(polled["headline_waste"]) > 0
    db.expire_all()
    assert db.get(AnalysisRun, run["id"]).status == "done"


def test_analyze_on_an_upload_that_failed_validation_is_422(client_a: TestClient):
    header = (
        "date,campaign_id,placement,age_group,gender,device,time_slot,"
        "spend,impressions,clicks,conversions,revenue\n"
    )
    bad = header + "2026-08-01,C1,facebook_feed,25-34,male,mobile,morning,abc,1000,20,1,500\n"
    rejected = client_a.post("/api/uploads", files={"file": ("bad.csv", bad.encode(), "text/csv")})
    upload_id = rejected.json()["detail"]["upload_id"]

    response = client_a.post(f"/api/analyze/{upload_id}")

    assert response.status_code == 422


def test_analyze_on_another_tenants_upload_is_404(
    client_a: TestClient, client_b: TestClient, tmp_path: Path
):
    upload_id = _upload(client_b, _sample_bytes(tmp_path))

    assert client_a.post(f"/api/analyze/{upload_id}").status_code == 404


def test_analyze_requires_authentication(api: TestClient):
    assert api.post("/api/analyze/1").status_code == 401


def test_analyze_is_not_reachable_by_an_admin(admin_client: TestClient):
    assert admin_client.post("/api/analyze/1").status_code == 403


def test_analyze_with_a_corrupt_client_override_is_422_not_500(
    client_a: TestClient, tmp_path: Path, db: Session, client_a_row: Client
):
    upload_id = _upload(client_a, _sample_bytes(tmp_path))

    row = db.get(Client, client_a_row.id)
    row.config_overrides = {"waste_multiplier": "not-a-number"}
    db.commit()

    response = client_a.post(f"/api/analyze/{upload_id}")

    assert response.status_code == 422, response.text
    assert "detail" in response.json()


def test_report_numbers_match_the_pipeline_on_the_same_file(
    client_a: TestClient, tmp_path: Path, db: Session
):
    body = _sample_bytes(tmp_path)
    upload_id = _upload(client_a, body)
    run_id = client_a.post(f"/api/analyze/{upload_id}").json()["id"]
    _approve(db, run_id)

    report = client_a.get(f"/api/reports/{run_id}").json()

    loaded = load_csv(io.BytesIO(body), PipelineConfig())
    assert loaded.ok, loaded.errors
    expected = analyze_all_dimensions(loaded.df, PipelineConfig())

    assert Decimal(report["headline_waste"]) == to_money(headline_waste(expected))
    assert {d["dimension"] for d in report["dimensions"]} == set(expected)
    for dim in report["dimensions"]:
        result = expected[dim["dimension"]]
        assert Decimal(dim["total_wasted_spend"]) == to_money(result.total_wasted_spend)
        assert Decimal(dim["total_spend"]) == to_money(result.total_spend)
        assert Decimal(dim["benchmark_cpa"]) == to_money(result.benchmark_cpa)
        assert len(dim["segments"]) == len(result.segments)

    placement = next(d for d in report["dimensions"] if d["dimension"] == "placement")
    assert [s["segment"] for s in placement["segments"] if s["is_flagged"]] == ["audience_network"]
    assert Decimal(report["recovery_pct"]) > 0
    assert report["config_snapshot"] == PipelineConfig().to_dict()


def test_report_is_404_while_pending_and_200_once_approved(
    client_a: TestClient, tmp_path: Path, db: Session
):
    upload_id = _upload(client_a, _sample_bytes(tmp_path))
    run_id = client_a.post(f"/api/analyze/{upload_id}").json()["id"]

    pending = client_a.get(f"/api/reports/{run_id}")
    assert pending.status_code == 404
    assert client_a.get("/api/reports/latest").status_code == 404

    _approve(db, run_id)

    approved = client_a.get(f"/api/reports/{run_id}")
    assert approved.status_code == 200
    assert approved.json()["run_id"] == run_id
    assert client_a.get("/api/reports/latest").json()["run_id"] == run_id


def test_report_for_an_unknown_run_id_is_404(client_a: TestClient):
    assert client_a.get("/api/reports/999999").status_code == 404


def test_report_for_a_run_that_is_still_queued_is_404(
    client_a: TestClient, tmp_path: Path, db: Session, client_a_row: Client
):
    # Task 6 review regression: get_report must 404 a run whose status is not "done" yet,
    # even when review_status is already "approved" (never reachable via /api/analyze in
    # these tests since TestClient runs the background task synchronously - so this
    # bypasses the HTTP layer and inserts the row directly).
    upload_id = _upload(client_a, _sample_bytes(tmp_path))
    run = AnalysisRun(
        client_id=client_a_row.id,
        upload_id=upload_id,
        config_snapshot={},
        status="queued",
        review_status="approved",
    )
    db.add(run)
    db.commit()

    assert client_a.get(f"/api/reports/{run.id}").status_code == 404


def test_client_a_cannot_reach_client_bs_run_or_report(
    client_a: TestClient, client_b: TestClient, tmp_path: Path, db: Session
):
    upload_id = _upload(client_b, _sample_bytes(tmp_path))
    run_id = client_b.post(f"/api/analyze/{upload_id}").json()["id"]
    _approve(db, run_id)
    assert client_b.get(f"/api/reports/{run_id}").status_code == 200

    assert client_a.get(f"/api/uploads/{upload_id}").status_code == 404
    assert client_a.get(f"/api/runs/{run_id}").status_code == 404
    assert client_a.get(f"/api/reports/{run_id}").status_code == 404
    assert client_a.post(f"/api/analyze/{upload_id}").status_code == 404
    assert client_a.get("/api/reports/latest").status_code == 404


def test_the_run_is_owned_by_the_caller_from_the_jwt(
    client_a: TestClient, tmp_path: Path, db: Session, client_a_row: Client
):
    upload_id = _upload(client_a, _sample_bytes(tmp_path))

    run_id = client_a.post(f"/api/analyze/{upload_id}").json()["id"]

    db.expire_all()
    run = db.scalars(select(AnalysisRun).where(AnalysisRun.id == run_id)).one()
    assert run.client_id == client_a_row.id


def test_an_admin_is_not_a_client_on_client_routes(admin_client: TestClient):
    assert admin_client.get("/api/reports/latest").status_code == 403
    assert admin_client.get("/api/uploads").status_code == 403


def test_run_for_an_unknown_id_is_404(client_a: TestClient):
    assert client_a.get("/api/runs/999999").status_code == 404


def test_runs_require_authentication(api: TestClient):
    assert api.get("/api/runs/1").status_code == 401
