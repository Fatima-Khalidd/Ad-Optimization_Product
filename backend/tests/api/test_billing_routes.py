"""Client-facing billing over HTTP (docs/PLAN.md section 5, "Billing").

`db` and the request handler run on two Sessions over the one shared connection, so call
`db.expire_all()` before reading back a row a request has just changed.
"""

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Client, Invoice, Payment
from tests.api.helpers import PDF_BYTES, PNG_BYTES, make_invoice, make_method

FORM = {
    "method_type": "jazzcash",
    "transaction_ref": "JC-90001",
    "amount": "10000.00",
    "paid_at": "2026-10-02",
}


def test_invoice_list_hides_drafts_and_shows_the_money(
    client_a: TestClient, db: Session, client_a_row: Client
):
    make_invoice(db, client_a_row, number="INV-2026-0001", status="issued")
    make_invoice(db, client_a_row, number="INV-2026-0002", status="draft")

    response = client_a.get("/api/billing/invoices")

    assert response.status_code == 200
    body = response.json()
    assert [row["invoice_number"] for row in body] == ["INV-2026-0001"]
    assert body[0]["total"] == "19600.00"
    assert body[0]["amount_due"] == "19600.00"
    assert body[0]["is_overdue"] is False
    assert body[0]["payments"] == []


def test_invoice_detail_carries_payment_history_and_instructions(
    client_a: TestClient, db: Session, client_a_row: Client
):
    invoice = make_invoice(db, client_a_row)
    make_method(db, "jazzcash", sort_order=0)
    make_method(db, "raast", "PK36SCBL0000001123456702", sort_order=1)
    make_method(db, "nayapay", is_active=False, sort_order=2)

    body = client_a.get(f"/api/billing/invoices/{invoice.id}").json()

    assert body["invoice_number"] == "INV-2026-0001"
    assert [i["method_type"] for i in body["instructions"]] == ["jazzcash", "raast"]
    assert body["instructions"][0]["account_identifier"] == "03001234567"


def test_payment_methods_endpoint_returns_only_active_ones(client_a: TestClient, db: Session):
    make_method(db, "jazzcash")
    make_method(db, "nayapay", is_active=False)

    body = client_a.get("/api/billing/payment-methods").json()

    assert [m["type"] for m in body] == ["jazzcash"]
    assert body[0]["account_title"] == "Ali Raza"


def test_invoice_pdf_downloads_as_an_attachment(
    client_a: TestClient, db: Session, client_a_row: Client
):
    invoice = make_invoice(db, client_a_row)
    make_method(db)

    response = client_a.get(f"/api/billing/invoices/{invoice.id}/pdf")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert "INV-2026-0001.pdf" in response.headers["content-disposition"]
    assert response.content.startswith(b"%PDF-")


def test_submitting_a_payment_moves_the_invoice_to_payment_submitted(
    client_a: TestClient, db: Session, client_a_row: Client
):
    invoice = make_invoice(db, client_a_row)

    response = client_a.post(f"/api/billing/invoices/{invoice.id}/payments", data=FORM)

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "pending"
    assert body["transaction_ref"] == "JC-90001"
    assert body["amount"] == "10000.00"
    assert body["has_proof"] is False
    assert "proof_file_path" not in body  # the private path never leaves the server
    db.expire_all()
    reloaded = db.get(Invoice, invoice.id)
    assert reloaded.status == "payment_submitted"
    assert reloaded.amount_paid == Decimal("0.00")


def test_a_proof_screenshot_is_stored_privately(
    client_a: TestClient, db: Session, client_a_row: Client, tmp_path
):
    # api_env already points STORAGE_ROOT at tmp_path / "storage".
    invoice = make_invoice(db, client_a_row)

    response = client_a.post(
        f"/api/billing/invoices/{invoice.id}/payments",
        data=FORM,
        files={"proof": ("screenshot.png", PNG_BYTES, "image/png")},
    )

    assert response.status_code == 201, response.text
    assert response.json()["has_proof"] is True
    db.expire_all()
    payment = db.get(Payment, response.json()["id"])
    assert payment.proof_file_path.endswith(".png")
    stored = tmp_path / "storage" / "proofs" / str(client_a_row.id) / f"{payment.id}.png"
    assert stored.exists()


def test_a_pdf_receipt_is_also_accepted_as_proof(
    client_a: TestClient, db: Session, client_a_row: Client
):
    invoice = make_invoice(db, client_a_row)

    response = client_a.post(
        f"/api/billing/invoices/{invoice.id}/payments",
        data=FORM,
        files={"proof": ("receipt.pdf", PDF_BYTES, "application/pdf")},
    )

    assert response.status_code == 201, response.text


def test_a_reused_transaction_id_is_refused_with_409(
    client_a: TestClient, db: Session, client_a_row: Client
):
    invoice = make_invoice(db, client_a_row)
    assert (
        client_a.post(f"/api/billing/invoices/{invoice.id}/payments", data=FORM).status_code == 201
    )

    response = client_a.post(f"/api/billing/invoices/{invoice.id}/payments", data=FORM)

    assert response.status_code == 409
    assert "transaction id" in response.json()["detail"].lower()


def test_an_oversized_proof_is_413_and_a_wrong_file_type_is_415(
    client_a: TestClient, db: Session, client_a_row: Client
):
    invoice = make_invoice(db, client_a_row)

    too_big = b"\x89PNG\r\n\x1a\n" + b"0" * (5 * 1024 * 1024)
    big = client_a.post(
        f"/api/billing/invoices/{invoice.id}/payments",
        data=FORM,
        files={"proof": ("huge.png", too_big, "image/png")},
    )
    assert big.status_code == 413

    wrong = client_a.post(
        f"/api/billing/invoices/{invoice.id}/payments",
        data={**FORM, "transaction_ref": "JC-90002"},
        files={"proof": ("notes.txt", b"hello", "text/plain")},
    )
    assert wrong.status_code == 415
    # A refused upload must not leave a half-made payment behind.
    db.expire_all()
    assert db.scalars(select(Payment)).all() == []


def test_a_bad_form_is_422_not_500(client_a: TestClient, db: Session, client_a_row: Client):
    invoice = make_invoice(db, client_a_row)
    url = f"/api/billing/invoices/{invoice.id}/payments"

    assert client_a.post(url, data={**FORM, "amount": "0"}).status_code == 422
    assert client_a.post(url, data={**FORM, "method_type": "paypal"}).status_code == 422
    assert client_a.post(url, data={**FORM, "paid_at": "yesterday"}).status_code == 422
    assert client_a.post(url, data={**FORM, "transaction_ref": ""}).status_code == 422
    # A typo like an extra decimal digit, or a value with more digits/an exponent than the
    # PaymentSubmission schema (max_digits=14, decimal_places=2) allows, must be a 422 raised
    # by the Form() layer itself — never a bare pydantic.ValidationError escaping the handler.
    assert client_a.post(url, data={**FORM, "amount": "100.555"}).status_code == 422
    assert client_a.post(url, data={**FORM, "amount": "999999999999999.00"}).status_code == 422
    assert client_a.post(url, data={**FORM, "amount": "1e20"}).status_code == 422
    db.expire_all()
    assert db.scalars(select(Payment)).all() == []


def test_a_paid_invoice_does_not_take_more_payments(
    client_a: TestClient, db: Session, client_a_row: Client
):
    invoice = make_invoice(db, client_a_row, status="paid", amount_paid=Decimal("19600.00"))

    response = client_a.post(f"/api/billing/invoices/{invoice.id}/payments", data=FORM)

    assert response.status_code == 409
    assert "paid" in response.json()["detail"]


def test_client_b_can_neither_see_nor_pay_client_as_invoice(
    client_b: TestClient, db: Session, client_a_row: Client
):
    invoice = make_invoice(db, client_a_row)

    assert client_b.get("/api/billing/invoices").json() == []
    assert client_b.get(f"/api/billing/invoices/{invoice.id}").status_code == 404
    assert client_b.get(f"/api/billing/invoices/{invoice.id}/pdf").status_code == 404
    assert (
        client_b.post(f"/api/billing/invoices/{invoice.id}/payments", data=FORM).status_code == 404
    )
    db.expire_all()
    assert db.scalars(select(Payment)).all() == []


def test_billing_requires_a_logged_in_client(api: TestClient, db: Session, client_a_row: Client):
    invoice = make_invoice(db, client_a_row)

    assert api.get("/api/billing/invoices").status_code == 401
    assert api.post(f"/api/billing/invoices/{invoice.id}/payments", data=FORM).status_code == 401
