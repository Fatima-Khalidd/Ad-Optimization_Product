"""Provider registry. Adding a gateway later (docs/PLAN.md section 9) means one new entry here."""

from app.core.settings import get_settings
from app.payments.base import PaymentInstruction, PaymentProvider
from app.payments.manual import ManualProvider

_PROVIDERS: dict[str, type] = {"manual": ManualProvider}

__all__ = ["ManualProvider", "PaymentInstruction", "PaymentProvider", "get_payment_provider"]


def get_payment_provider() -> PaymentProvider:
    name = get_settings().payment_provider
    provider_cls = _PROVIDERS.get(name)
    if provider_cls is None:
        raise ValueError(f"unknown payment provider: {name}")
    return provider_cls()
