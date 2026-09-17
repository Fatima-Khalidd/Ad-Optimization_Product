from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Client
from tests.api.helpers import make_approved_run
from tests.pdf_utils import pdf_text


def test_approved_run_downloads_as_a_pdf(client_a: TestClient, db: Session, client_a_row: Client):
    run = make_approved_run(db, client_a_row)

    resp = client_a.get(f"/api/reports/{run.id}/pdf")

    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.headers["content-disposition"] == (
        f'attachment; filename="ad-waste-report-{run.id}.pdf"'
    )
    assert resp.content[:4] == b"%PDF"


def test_pdf_content_matches_the_stored_numbers(
    client_a: TestClient, db: Session, client_a_row: Client
):
    run = make_approved_run(db, client_a_row)

    text = pdf_text(client_a.get(f"/api/reports/{run.id}/pdf").content)

    assert client_a_row.business_name in text  # "Alpha Traders"
    assert "Rs. 84,000" in text  # audience_network spend
    assert "Rs. 53,000" in text  # headline waste
    assert "Audience Network" in text
    assert "largest single dimension" in text


def test_pending_run_is_404_not_a_pdf(client_a: TestClient, db: Session, client_a_row: Client):
    run = make_approved_run(db, client_a_row, review_status="pending")

    resp = client_a.get(f"/api/reports/{run.id}/pdf")

    assert resp.status_code == 404
    assert b"%PDF" not in resp.content


def test_failed_run_is_404(client_a: TestClient, db: Session, client_a_row: Client):
    run = make_approved_run(db, client_a_row, status="failed", review_status="approved")

    assert client_a.get(f"/api/reports/{run.id}/pdf").status_code == 404


def test_another_tenants_run_is_404_not_403(
    client_b: TestClient, db: Session, client_a_row: Client
):
    run = make_approved_run(db, client_a_row)

    resp = client_b.get(f"/api/reports/{run.id}/pdf")

    assert resp.status_code == 404  # 404, never 403: run ids must not be probeable
    assert b"%PDF" not in resp.content


def test_anonymous_request_is_401(api: TestClient, db: Session, client_a_row: Client):
    run = make_approved_run(db, client_a_row)

    assert api.get(f"/api/reports/{run.id}/pdf").status_code == 401


def test_an_admin_is_not_a_client_on_the_pdf_route(
    admin_client: TestClient, db: Session, client_a_row: Client
):
    run = make_approved_run(db, client_a_row)

    assert admin_client.get(f"/api/reports/{run.id}/pdf").status_code == 403


def test_latest_and_run_id_and_pdf_routes_all_still_resolve(
    client_a: TestClient, db: Session, client_a_row: Client
):
    """`/latest` must not be swallowed by `/{run_id}`, and `/{run_id}/pdf` must not be
    swallowed by `/{run_id}` — all three routes are declared on the same router.
    """
    run = make_approved_run(db, client_a_row)

    latest = client_a.get("/api/reports/latest")
    by_id = client_a.get(f"/api/reports/{run.id}")
    pdf = client_a.get(f"/api/reports/{run.id}/pdf")

    assert latest.status_code == 200
    assert latest.headers["content-type"].startswith("application/json")
    assert by_id.status_code == 200
    assert by_id.headers["content-type"].startswith("application/json")
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"
