"""Inbound webhooks from payment gateways. No session cookie: the signature is the auth."""

import json

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.db import get_session
from app.core.errors import InvalidSignatureError, ServiceUnavailableError, ValidationError
from app.core.settings import get_settings
from app.payments import lemonsqueezy
from app.services import payments as payments_service

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


@router.post("/lemonsqueezy")
async def lemonsqueezy_webhook(
    request: Request, session: Session = Depends(get_session)
) -> dict[str, str]:
    """Lemon Squeezy's `order_created`: a card payment has gone through.

    The signature is checked against the RAW body before anything is parsed. Any 2xx tells
    Lemon Squeezy to stop retrying, so events we do not act on still get 200.
    """
    settings = get_settings()
    if not settings.card_payments_enabled:
        raise ServiceUnavailableError("card payments are not set up")
    raw = await request.body()
    if not lemonsqueezy.verify_signature(
        settings.lemonsqueezy_webhook_secret, raw, request.headers.get("x-signature")
    ):
        raise InvalidSignatureError("invalid signature")
    try:
        order = lemonsqueezy.parse_paid_order(json.loads(raw))
    except (ValueError, KeyError, TypeError) as exc:
        raise ValidationError("malformed webhook payload") from exc
    if order is None:
        return {"status": "ignored"}
    payment = payments_service.record_gateway_payment(session, order)
    return {"status": "recorded" if payment is not None else "unmatched"}
