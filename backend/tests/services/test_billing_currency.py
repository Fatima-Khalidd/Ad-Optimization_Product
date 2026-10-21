"""USD invoices: the performance fee on PKR recovered waste, converted at a frozen rate."""

from decimal import Decimal

import pytest

from app.core.settings import get_settings
from app.pipeline.optimizer import calculate_fee
from app.services import billing
from tests.api.helpers import make_admin, make_invoice
from tests.services.test_billing_invoices import (
    PERIOD_END,
    PERIOD_START,
    _client_with_23k_recovered,
)


@pytest.fixture
def rate_276(monkeypatch):
    monkeypatch.setenv("PKR_PER_USD", "276")
    get_settings.cache_clear()


def test_the_performance_fee_is_converted_once_then_rounded():
    # 20% of Rs. 23,000 = Rs. 4,600 = $16.6666... -> $16.67
    fee = calculate_fee(Decimal("65"), Decimal("20"), Decimal("23000"), exchange_rate=276)
    assert fee.performance_fee == Decimal("16.67")
    assert fee.total == Decimal("81.67")
    assert fee.recovered_waste == Decimal("23000.00")  # still rupees


def test_a_cap_applies_to_the_converted_fee():
    fee = calculate_fee(Decimal("65"), Decimal("20"), Decimal("23000"), cap=10, exchange_rate=276)
    assert fee.performance_fee == Decimal("10.00")
    assert fee.cap_applied is True


@pytest.mark.parametrize("rate", [0, -276])
def test_a_non_positive_rate_is_refused(rate):
    with pytest.raises(ValueError, match="exchange_rate"):
        calculate_fee(Decimal("65"), Decimal("20"), Decimal("23000"), exchange_rate=rate)


def test_a_draft_is_in_usd_and_freezes_todays_rate(session, rate_276):
    actor = make_admin(session)
    client = _client_with_23k_recovered(session, base_fee=Decimal("65.00"))
    session.commit()

    invoice = billing.draft_invoice(session, actor, client.id, PERIOD_START, PERIOD_END)

    assert invoice.currency == "USD"
    assert invoice.pkr_per_usd == Decimal("276")
    assert invoice.suggested_recovered_waste == Decimal("23000.00")
    assert invoice.performance_fee == Decimal("16.67")
    assert invoice.total == Decimal("81.67")


def test_confirming_uses_the_drafts_rate_not_todays(session, rate_276, monkeypatch):
    actor = make_admin(session)
    client = _client_with_23k_recovered(session, base_fee=Decimal("65.00"))
    session.commit()
    invoice = billing.draft_invoice(session, actor, client.id, PERIOD_START, PERIOD_END)

    monkeypatch.setenv("PKR_PER_USD", "300")
    get_settings.cache_clear()
    invoice = billing.confirm_invoice(session, actor, invoice.id, Decimal("23000.00"))

    assert invoice.pkr_per_usd == Decimal("276")
    assert invoice.performance_fee == Decimal("16.67")


def test_confirming_a_legacy_pkr_invoice_converts_nothing(session, rate_276):
    actor = make_admin(session)
    client = _client_with_23k_recovered(session)
    invoice = make_invoice(session, client, status="draft", currency="PKR")

    invoice = billing.confirm_invoice(session, actor, invoice.id, Decimal("23000.00"))

    assert invoice.currency == "PKR"
    assert invoice.performance_fee == Decimal("4600.00")
    assert invoice.total == Decimal("19600.00")
