"""Admin review of manual payments, over HTTP.

`client_a` and `admin_client` are two logged-in TestClients from tests/api/conftest.py, so no
test here logs anybody in by hand. `db.expire_all()` precedes every read-back of a row a
request has changed.
"""

from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditLog, Client, Invoice, PaymentMethod
from tests.api.helpers import PNG_BYTES, make_invoice, make_method

FORM = {
    "method_type": "jazzcash",
    "transaction_ref": "JC-90001",
    "amount": "10000.00",
    "paid_at": "2026-10-02",
}


def _client_submits(
    db: Session, client_a: TestClient, client_a_row: Client, *, due_date=date(2026, 10, 7)
):
    """One issued invoice for client_a plus one pending payment on it."""
    invoice = make_invoice(db, client_a_row, due_date=due_date)
    response = client_a.post(f"/api/billing/invoices/{invoice.id}/payments", data=FORM)
    assert response.status_code == 201, response.text
    return invoice, response.json()["id"]


def test_the_queue_shows_pending_payments_with_their_invoice_and_client(
    db: Session, client_a: TestClient, client_a_row: Client, admin_client: TestClient
):
    _, payment_id = _client_submits(db, client_a, client_a_row)

    body = admin_client.get("/api/admin/payments?status=pending").json()

    assert len(body) == 1
    row = body[0]
    assert row["id"] == payment_id
    assert row["transaction_ref"] == "JC-90001"
    assert row["business_name"] == "Alpha Traders"  # client_a's business name
    assert row["invoice_number"] == "INV-2026-0001"
    assert row["invoice_total"] == "19600.00"
    assert row["invoice_is_overdue"] is False
    assert row["has_proof"] is False


def test_an_invoice_past_its_due_date_is_flagged_overdue(
    db: Session, client_a: TestClient, client_a_row: Client, admin_client: TestClient
):
    _client_submits(db, client_a, client_a_row, due_date=date(2020, 1, 7))

    row = admin_client.get("/api/admin/payments?status=pending").json()[0]

    assert row["invoice_due_date"] == "2020-01-07"
    assert row["invoice_is_overdue"] is True


def test_confirming_a_partial_payment_leaves_the_invoice_unpaid_then_a_second_one_pays_it(
    db: Session, client_a: TestClient, client_a_row: Client, admin_client: TestClient
):
    invoice, payment_id = _client_submits(db, client_a, client_a_row)

    first = admin_client.post(
        f"/api/admin/payments/{payment_id}/confirm", json={"note": "seen in app"}
    )

    assert first.status_code == 200
    assert first.json()["status"] == "confirmed"
    assert first.json()["invoice_status"] == "issued"
    db.expire_all()
    assert db.get(Invoice, invoice.id).amount_paid == Decimal("10000.00")

    second = client_a.post(
        f"/api/billing/invoices/{invoice.id}/payments",
        data={**FORM, "transaction_ref": "JC-90002", "amount": "9600.00"},
    )
    admin_client.post(f"/api/admin/payments/{second.json()['id']}/confirm", json={})

    db.expire_all()
    reloaded = db.get(Invoice, invoice.id)
    assert reloaded.amount_paid == Decimal("19600.00")
    assert reloaded.status == "paid"
    assert admin_client.get("/api/admin/payments?status=pending").json() == []


def test_rejecting_needs_a_reason_and_the_client_can_read_it(
    db: Session, client_a: TestClient, client_a_row: Client, admin_client: TestClient
):
    invoice, payment_id = _client_submits(db, client_a, client_a_row)

    assert admin_client.post(f"/api/admin/payments/{payment_id}/reject", json={}).status_code == 422
    assert (
        admin_client.post(f"/api/admin/payments/{payment_id}/reject", json={"note": ""}).status_code
        == 422
    )

    rejected = admin_client.post(
        f"/api/admin/payments/{payment_id}/reject", json={"note": "no such TID in my JazzCash app"}
    )

    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"
    detail = client_a.get(f"/api/billing/invoices/{invoice.id}").json()
    assert detail["status"] == "issued"
    assert detail["payments"][0]["review_note"] == "no such TID in my JazzCash app"
    assert detail["amount_paid"] == "0.00"


def test_confirming_twice_is_409_and_an_unknown_payment_is_404(
    db: Session, client_a: TestClient, client_a_row: Client, admin_client: TestClient
):
    _, payment_id = _client_submits(db, client_a, client_a_row)
    admin_client.post(f"/api/admin/payments/{payment_id}/confirm", json={})

    assert (
        admin_client.post(f"/api/admin/payments/{payment_id}/confirm", json={}).status_code == 409
    )
    assert admin_client.post("/api/admin/payments/999/confirm", json={}).status_code == 404


def test_the_admin_can_download_the_private_proof_file(
    db: Session, client_a: TestClient, client_a_row: Client, admin_client: TestClient
):
    # api_env already points STORAGE_ROOT at this test's own tmp_path.
    invoice = make_invoice(db, client_a_row)
    payment_id = client_a.post(
        f"/api/billing/invoices/{invoice.id}/payments",
        data=FORM,
        files={"proof": ("screenshot.png", PNG_BYTES, "image/png")},
    ).json()["id"]

    response = admin_client.get(f"/api/admin/payments/{payment_id}/proof")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content == PNG_BYTES


def test_asking_for_a_proof_that_was_never_uploaded_is_404(
    db: Session, client_a: TestClient, client_a_row: Client, admin_client: TestClient
):
    _, payment_id = _client_submits(db, client_a, client_a_row)
    assert admin_client.get(f"/api/admin/payments/{payment_id}/proof").status_code == 404


def test_payment_method_crud_over_http(db: Session, admin_client: TestClient):
    make_method(db, "nayapay", is_active=False, sort_order=5)

    created = admin_client.post(
        "/api/admin/payment-methods",
        json={
            "type": "raast",
            "account_title": "Ali Raza",
            "account_identifier": "PK36SCBL0000001123456702",
            "instructions": "Any bank app -> Raast -> IBAN.",
            "sort_order": 1,
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["is_active"] is True

    listed = admin_client.get("/api/admin/payment-methods").json()
    assert [m["type"] for m in listed] == [
        "raast",
        "nayapay",
    ]  # sort_order 1 then 5, inactive included

    patched = admin_client.patch(
        f"/api/admin/payment-methods/{created.json()['id']}",
        json={"is_active": False, "sort_order": 9},
    )
    assert patched.status_code == 200
    assert patched.json()["is_active"] is False
    assert patched.json()["sort_order"] == 9
    assert patched.json()["account_title"] == "Ali Raza"  # untouched by the patch
    db.expire_all()
    assert db.get(PaymentMethod, created.json()["id"]).is_active is False

    assert (
        admin_client.patch("/api/admin/payment-methods/999", json={"sort_order": 1}).status_code
        == 404
    )
    bad = admin_client.post(
        "/api/admin/payment-methods",
        json={"type": "paypal", "account_title": "x", "account_identifier": "y"},
    )
    assert bad.status_code == 422


def test_every_admin_decision_is_audited(
    db: Session, client_a: TestClient, client_a_row: Client, admin_client: TestClient
):
    _, payment_id = _client_submits(db, client_a, client_a_row)
    admin_client.post(f"/api/admin/payments/{payment_id}/confirm", json={"note": "ok"})
    admin_client.post(
        "/api/admin/payment-methods",
        json={
            "type": "raast",
            "account_title": "Ali Raza",
            "account_identifier": "PK36SCBL0000001123456702",
        },
    )

    db.expire_all()
    actions = [row.action for row in db.scalars(select(AuditLog).order_by(AuditLog.id))]
    assert actions == ["payment.confirm", "payment_method.create"]


def test_a_client_cannot_touch_the_admin_payment_routes(
    db: Session, client_a: TestClient, client_a_row: Client
):
    _, payment_id = _client_submits(db, client_a, client_a_row)

    assert client_a.get("/api/admin/payments?status=pending").status_code == 403
    assert client_a.post(f"/api/admin/payments/{payment_id}/confirm", json={}).status_code == 403
    assert client_a.get("/api/admin/payment-methods").status_code == 403
    assert (
        client_a.post(
            "/api/admin/payment-methods",
            json={"type": "raast", "account_title": "x", "account_identifier": "y"},
        ).status_code
        == 403
    )
