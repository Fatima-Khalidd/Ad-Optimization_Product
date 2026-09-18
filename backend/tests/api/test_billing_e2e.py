"""docs/PLAN.md section 6, Stage 7, "Done when" — every bullet, in one month-long flow."""

from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditLog, Client, Invoice, User
from app.services.billing import confirm_invoice, draft_invoice, issue_invoice
from tests.api.helpers import make_method


def _issued_invoice(db: Session, admin: User, client: Client) -> Invoice:
    """Admin drafts September, confirms 23,000 of recovered waste, then issues.

    Commits at the end, because the HTTP calls that follow run on their own Session.
    """
    invoice = draft_invoice(db, admin, client.id, date(2026, 9, 1), date(2026, 9, 30))
    assert invoice.status == "draft"
    invoice = confirm_invoice(db, admin, invoice.id, Decimal("23000.00"))
    assert invoice.performance_fee == Decimal("4600.00")  # 20% of 23,000
    assert invoice.total == Decimal("19600.00")  # + the 15,000 base fee
    assert invoice.status == "draft"  # confirming a fee does not issue the invoice
    invoice = issue_invoice(db, admin, invoice.id, date(2026, 10, 7))
    assert invoice.status == "issued"
    db.commit()
    return invoice


def test_a_full_month_runs_generate_issue_submit_confirm_paid(
    db: Session,
    client_a: TestClient,
    client_a_row: Client,
    admin_client: TestClient,
    admin_row: User,
):
    make_method(db, "jazzcash", sort_order=0)
    invoice = _issued_invoice(db, admin_row, client_a_row)

    # 1. The client sees the invoice and where to pay.
    listed = client_a.get("/api/billing/invoices").json()
    assert [row["invoice_number"] for row in listed] == [invoice.invoice_number]
    detail = client_a.get(f"/api/billing/invoices/{invoice.id}").json()
    assert detail["total"] == "19600.00"
    assert detail["instructions"][0]["account_identifier"] == "03001234567"
    assert client_a.get(f"/api/billing/invoices/{invoice.id}/pdf").content.startswith(b"%PDF-")

    # 2. The client pays 10,000 and reports the transaction ID.
    first = client_a.post(
        f"/api/billing/invoices/{invoice.id}/payments",
        data={
            "method_type": "jazzcash",
            "transaction_ref": "JC-90001",
            "amount": "10000.00",
            "paid_at": "2026-10-02",
        },
    )
    assert first.status_code == 201
    db.expire_all()
    submitted = db.get(Invoice, invoice.id)
    assert submitted.status == "payment_submitted"
    assert submitted.amount_paid == Decimal("0.00")  # a claim never marks money as received

    # 3. A partial payment leaves the invoice unpaid.
    admin_client.post(
        f"/api/admin/payments/{first.json()['id']}/confirm", json={"note": "JazzCash app"}
    )
    db.expire_all()
    after_partial = db.get(Invoice, invoice.id)
    assert after_partial.amount_paid == Decimal("10000.00")
    assert after_partial.status == "issued"
    assert client_a.get(f"/api/billing/invoices/{invoice.id}").json()["amount_due"] == "9600.00"

    # 4. The same transaction ID cannot be reused.
    reused = client_a.post(
        f"/api/billing/invoices/{invoice.id}/payments",
        data={
            "method_type": "jazzcash",
            "transaction_ref": "JC-90001",
            "amount": "9600.00",
            "paid_at": "2026-10-05",
        },
    )
    assert reused.status_code == 409

    # 5. The rest is paid and confirmed -> the invoice is paid.
    second = client_a.post(
        f"/api/billing/invoices/{invoice.id}/payments",
        data={
            "method_type": "jazzcash",
            "transaction_ref": "JC-90002",
            "amount": "9600.00",
            "paid_at": "2026-10-05",
        },
    )
    admin_client.post(f"/api/admin/payments/{second.json()['id']}/confirm", json={})

    db.expire_all()
    final = db.get(Invoice, invoice.id)
    assert final.amount_paid == Decimal("19600.00")
    assert final.status == "paid"
    assert client_a.get(f"/api/billing/invoices/{invoice.id}").json()["is_overdue"] is False

    # 6. Every decision is on the record.
    actions = [row.action for row in db.scalars(select(AuditLog).order_by(AuditLog.id))]
    assert actions.count("payment.confirm") == 2
    assert "invoice.issue" in actions


def test_another_client_cannot_see_or_pay_this_invoice(
    db: Session, client_b: TestClient, client_a_row: Client, admin_row: User
):
    make_method(db)
    invoice = _issued_invoice(db, admin_row, client_a_row)

    assert client_b.get("/api/billing/invoices").json() == []
    assert client_b.get(f"/api/billing/invoices/{invoice.id}").status_code == 404
    assert (
        client_b.post(
            f"/api/billing/invoices/{invoice.id}/payments",
            data={
                "method_type": "jazzcash",
                "transaction_ref": "JC-99999",
                "amount": "100.00",
                "paid_at": "2026-10-02",
            },
        ).status_code
        == 404
    )
