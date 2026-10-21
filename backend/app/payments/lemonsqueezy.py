"""Card payments in USD through Lemon Squeezy.

Lemon Squeezy is the merchant of record: it charges the client's card, handles sales tax, and
pays out in USD to the owner's bank account (Pakistan included, which Stripe does not serve).

Two halves, both stateless:
  * `create_checkout` asks the API for a hosted checkout page for one invoice's balance. The
    invoice id rides along as custom data so the webhook can find it again.
  * `verify_signature` + `parse_paid_order` read the `order_created` webhook that Lemon Squeezy
    sends once the card is charged. app/services/payments.py records it as a confirmed payment.

Unlike the manual route, a gateway payment needs no admin review: the money has already moved,
and the webhook's HMAC signature proves the notice came from Lemon Squeezy.
"""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

import httpx

from app.core.errors import GatewayError, ServiceUnavailableError
from app.core.settings import Settings

PROVIDER = "lemonsqueezy"
METHOD_TYPE = "card"
CHECKOUTS_URL = "https://api.lemonsqueezy.com/v1/checkouts"
JSON_API = "application/vnd.api+json"
TIMEOUT_SECONDS = 15.0
CENTS = Decimal("100")


@dataclass(frozen=True)
class PaidOrder:
    """The parts of an `order_created` webhook that billing needs."""

    invoice_id: int
    order_id: str
    amount: Decimal  # USD, pre-tax: the tax Lemon Squeezy collects is not ours to credit
    paid_at: date


def create_checkout(
    settings: Settings, *, invoice_id: int, invoice_number: str, amount: Decimal, email: str
) -> str:
    """A one-off hosted checkout URL that charges `amount` USD against `invoice_id`."""
    if not settings.card_payments_enabled:
        raise ServiceUnavailableError("card payments are not set up")
    product_options: dict = {
        "name": f"Invoice {invoice_number}",
        "enabled_variants": [int(settings.lemonsqueezy_variant_id)],
    }
    if settings.public_app_url:
        product_options["redirect_url"] = (
            f"{settings.public_app_url.rstrip('/')}/dashboard/billing?paid={invoice_id}"
        )
    body = {
        "data": {
            "type": "checkouts",
            "attributes": {
                "custom_price": int((amount * CENTS).to_integral_value()),
                "product_options": product_options,
                "checkout_data": {"email": email, "custom": {"invoice_id": str(invoice_id)}},
            },
            "relationships": {
                "store": {"data": {"type": "stores", "id": settings.lemonsqueezy_store_id}},
                "variant": {"data": {"type": "variants", "id": settings.lemonsqueezy_variant_id}},
            },
        }
    }
    try:
        response = httpx.post(
            CHECKOUTS_URL,
            json=body,
            headers={
                "Accept": JSON_API,
                "Content-Type": JSON_API,
                "Authorization": f"Bearer {settings.lemonsqueezy_api_key}",
            },
            timeout=TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        return response.json()["data"]["attributes"]["url"]
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        raise GatewayError("could not start a card payment; try again shortly") from exc


def verify_signature(secret: str, raw_body: bytes, signature: str | None) -> bool:
    """`X-Signature` is the hex HMAC-SHA256 of the raw request body under the webhook secret."""
    if not signature:
        return False
    expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def parse_paid_order(payload: dict) -> PaidOrder | None:
    """The paid USD order in an `order_created` webhook, or None for anything else.

    Other events, unpaid orders, other currencies and orders without our invoice id are
    ignored rather than rejected, so Lemon Squeezy does not keep retrying them.
    """
    meta = payload.get("meta") or {}
    data = payload.get("data") or {}
    attributes = data.get("attributes") or {}
    invoice_id = (meta.get("custom_data") or {}).get("invoice_id")
    if (
        meta.get("event_name") != "order_created"
        or attributes.get("status") != "paid"
        or attributes.get("currency") != "USD"
        or not str(invoice_id or "").isdigit()
    ):
        return None
    created_at = attributes.get("created_at")
    paid_at = datetime.fromisoformat(created_at).date() if created_at else date.today()
    return PaidOrder(
        invoice_id=int(invoice_id),
        order_id=str(data["id"]),
        amount=(Decimal(attributes["subtotal"]) / CENTS).quantize(Decimal("0.01")),
        paid_at=paid_at,
    )
