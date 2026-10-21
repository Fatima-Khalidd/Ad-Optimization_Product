"""Card payments through Lemon Squeezy: checkout, the signed webhook, and what it records."""

import hashlib
import hmac
import json
from decimal import Decimal

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.settings import get_settings
from app.models import AuditLog, Client, Invoice, Payment
from app.payments import lemonsqueezy
from tests.api.helpers import make_invoice

SECRET = "whsec-test"
WEBHOOK = "/api/webhooks/lemonsqueezy"


@pytest.fixture
def card_payments(monkeypatch):
    monkeypatch.setenv("LEMONSQUEEZY_API_KEY", "ls-key")
    monkeypatch.setenv("LEMONSQUEEZY_STORE_ID", "11")
    monkeypatch.setenv("LEMONSQUEEZY_VARIANT_ID", "22")
    monkeypatch.setenv("LEMONSQUEEZY_WEBHOOK_SECRET", SECRET)
    monkeypatch.setenv("PUBLIC_APP_URL", "https://app.example.com/")
    get_settings.cache_clear()


def _order(invoice_id: int, *, order_id: str = "9001", subtotal: int = 1960000, **attributes):
    return {
        "meta": {"event_name": "order_created", "custom_data": {"invoice_id": str(invoice_id)}},
        "data": {
            "type": "orders",
            "id": order_id,
            "attributes": {
                "status": "paid",
                "currency": "USD",
                "subtotal": subtotal,
                "total": subtotal,
                "created_at": "2026-10-20T09:45:53.000000Z",
                **attributes,
            },
        },
    }


def _deliver(api: TestClient, payload: dict, secret: str = SECRET):
    raw = json.dumps(payload).encode()
    signature = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    return api.post(
        WEBHOOK, content=raw, headers={"X-Signature": signature, "Content-Type": "application/json"}
    )


# --------------------------------------------------------------------------- webhook


def test_a_paid_order_settles_the_invoice_without_an_admin(
    api: TestClient, db: Session, client_a_row: Client, card_payments
):
    invoice = make_invoice(db, client_a_row)  # $19,600.00 owed

    response = _deliver(api, _order(invoice.id))

    assert response.status_code == 200
    assert response.json() == {"status": "recorded"}
    db.expire_all()
    assert db.get(Invoice, invoice.id).status == "paid"
    assert db.get(Invoice, invoice.id).amount_paid == Decimal("19600.00")
    payment = db.scalars(select(Payment)).one()
    assert (payment.method_type, payment.provider, payment.status) == (
        "card",
        "lemonsqueezy",
        "confirmed",
    )
    assert payment.transaction_ref == "9001"
    entry = db.scalars(select(AuditLog).where(AuditLog.action == "payment.gateway_confirm")).one()
    assert entry.actor_user_id is None


def test_a_redelivered_order_is_recorded_once(
    api: TestClient, db: Session, client_a_row: Client, card_payments
):
    invoice = make_invoice(db, client_a_row)

    _deliver(api, _order(invoice.id, subtotal=500000))
    _deliver(api, _order(invoice.id, subtotal=500000))

    db.expire_all()
    assert len(db.scalars(select(Payment)).all()) == 1
    assert db.get(Invoice, invoice.id).amount_paid == Decimal("5000.00")
    assert db.get(Invoice, invoice.id).status == "issued"  # part-paid, nothing pending


def test_a_bad_signature_is_401_and_records_nothing(
    api: TestClient, db: Session, client_a_row: Client, card_payments
):
    invoice = make_invoice(db, client_a_row)

    response = _deliver(api, _order(invoice.id), secret="someone-else")

    assert response.status_code == 401
    assert db.scalars(select(Payment)).all() == []


def test_events_we_do_not_act_on_are_acknowledged_and_ignored(
    api: TestClient, db: Session, client_a_row: Client, card_payments
):
    invoice = make_invoice(db, client_a_row)
    refund = _order(invoice.id)
    refund["meta"]["event_name"] = "order_refunded"

    for payload in (
        refund,
        _order(invoice.id, status="pending"),
        _order(invoice.id, currency="EUR"),
    ):
        assert _deliver(api, payload).json() == {"status": "ignored"}
    assert db.scalars(select(Payment)).all() == []


def test_an_order_for_a_void_invoice_is_not_credited(
    api: TestClient, db: Session, client_a_row: Client, card_payments
):
    invoice = make_invoice(db, client_a_row, status="void")

    assert _deliver(api, _order(invoice.id)).json() == {"status": "unmatched"}
    assert db.scalars(select(Payment)).all() == []


def test_the_webhook_is_503_until_card_payments_are_set_up(api: TestClient):
    assert api.post(WEBHOOK, content=b"{}").status_code == 503


# --------------------------------------------------------------------------- checkout


def test_checkout_charges_what_is_still_owed_and_tags_the_invoice(
    client_a: TestClient, db: Session, client_a_row: Client, card_payments, monkeypatch
):
    invoice = make_invoice(db, client_a_row, amount_paid=Decimal("600.00"))
    sent: dict = {}

    def fake_post(url, json, headers, timeout):
        sent.update(url=url, body=json, headers=headers)
        return httpx.Response(
            201,
            json={"data": {"attributes": {"url": "https://pay.example/checkout/abc"}}},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(lemonsqueezy.httpx, "post", fake_post)

    response = client_a.post(f"/api/billing/invoices/{invoice.id}/checkout")

    assert response.status_code == 200, response.text
    assert response.json() == {"url": "https://pay.example/checkout/abc"}
    attributes = sent["body"]["data"]["attributes"]
    assert attributes["custom_price"] == 1900000  # $19,000.00 still owed, in cents
    assert attributes["checkout_data"]["custom"] == {"invoice_id": str(invoice.id)}
    assert attributes["product_options"]["redirect_url"] == (
        f"https://app.example.com/dashboard/billing?paid={invoice.id}"
    )
    assert sent["headers"]["Authorization"] == "Bearer ls-key"


def test_a_gateway_failure_is_a_502(
    client_a: TestClient, db: Session, client_a_row: Client, card_payments, monkeypatch
):
    invoice = make_invoice(db, client_a_row)

    def failing_post(url, **kwargs):
        raise httpx.ConnectError("down")

    monkeypatch.setattr(lemonsqueezy.httpx, "post", failing_post)

    assert client_a.post(f"/api/billing/invoices/{invoice.id}/checkout").status_code == 502


def test_a_legacy_rupee_invoice_cannot_be_paid_by_card(
    client_a: TestClient, db: Session, client_a_row: Client, card_payments
):
    invoice = make_invoice(db, client_a_row, currency="PKR")

    assert client_a.post(f"/api/billing/invoices/{invoice.id}/checkout").status_code == 409


def test_checkout_is_503_until_card_payments_are_set_up(
    client_a: TestClient, db: Session, client_a_row: Client
):
    invoice = make_invoice(db, client_a_row)

    assert client_a.post(f"/api/billing/invoices/{invoice.id}/checkout").status_code == 503


def test_the_invoice_says_whether_card_payment_is_offered(
    client_a: TestClient, db: Session, client_a_row: Client, card_payments
):
    invoice = make_invoice(db, client_a_row)

    assert client_a.get(f"/api/billing/invoices/{invoice.id}").json()["pay_by_card"] is True


def test_another_clients_invoice_cannot_be_checked_out(
    client_b: TestClient, db: Session, client_a_row: Client, card_payments
):
    invoice = make_invoice(db, client_a_row)

    assert client_b.post(f"/api/billing/invoices/{invoice.id}/checkout").status_code == 404
