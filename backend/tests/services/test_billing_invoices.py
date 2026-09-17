from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from app.core.errors import ConflictError, NotFoundError
from app.models import AuditLog, Invoice
from app.services import billing
from tests.api.helpers import make_admin, make_client, make_run

PERIOD_START = date(2026, 8, 1)
PERIOD_END = date(2026, 8, 31)
BEFORE = datetime(2026, 7, 20, tzinfo=UTC)
INSIDE = datetime(2026, 8, 25, tzinfo=UTC)


def _client_with_23k_recovered(session, **kwargs):
    """A client whose August suggestion is exactly 23,000 (see Task 4's hand computation)."""
    client = make_client(session, **kwargs)
    make_run(
        session,
        client,
        created_at=BEFORE,
        review_status="approved",
        segments=(
            ("placement", "audience_network", "52000", True),
            ("placement", "reels", "1000", True),
        ),
    )
    make_run(
        session,
        client,
        created_at=INSIDE,
        review_status="approved",
        segments=(
            ("placement", "audience_network", "30000", True),
            ("placement", "reels", "0", False),
        ),
    )
    return client


def test_draft_uses_hand_computed_fees(session):
    actor = make_admin(session)
    client = _client_with_23k_recovered(session)  # base_fee 15,000 ; performance_fee_pct 20
    session.commit()

    invoice = billing.draft_invoice(session, actor, client.id, PERIOD_START, PERIOD_END)

    assert invoice.invoice_number == "INV-2026-0001"
    assert invoice.status == "draft"
    assert invoice.base_fee == Decimal("15000.00")
    assert invoice.suggested_recovered_waste == Decimal("23000.00")
    assert invoice.confirmed_recovered_waste == Decimal("0.00")  # nothing confirmed yet
    assert invoice.performance_fee == Decimal("4600.00")  # 20% of 23,000
    assert invoice.total == Decimal("19600.00")  # 15,000 + 4,600
    assert invoice.due_date == date(2026, 9, 14)  # period_end + 14 days, until issue() sets it
    assert invoice.confirmed_by is None
    assert invoice.issued_at is None

    entry = session.query(AuditLog).one()
    assert entry.action == "invoice.draft"
    assert entry.entity_type == "invoice"
    assert entry.entity_id == invoice.id
    assert entry.before is None
    assert entry.after["total"] == "19600.00"


def test_invoice_numbers_are_sequential_per_year(session):
    actor = make_admin(session)
    client = _client_with_23k_recovered(session)
    session.commit()

    first = billing.draft_invoice(session, actor, client.id, PERIOD_START, PERIOD_END)
    second = billing.draft_invoice(session, actor, client.id, date(2026, 9, 1), date(2026, 9, 30))
    third = billing.draft_invoice(session, actor, client.id, date(2027, 1, 1), date(2027, 1, 31))

    assert [first.invoice_number, second.invoice_number, third.invoice_number] == [
        "INV-2026-0001",
        "INV-2026-0002",
        "INV-2027-0001",
    ]


def test_drafting_the_same_period_twice_is_a_conflict(session):
    actor = make_admin(session)
    client = _client_with_23k_recovered(session)
    session.commit()
    billing.draft_invoice(session, actor, client.id, PERIOD_START, PERIOD_END)

    with pytest.raises(ConflictError, match="INV-2026-0001 already covers"):
        billing.draft_invoice(session, actor, client.id, PERIOD_START, PERIOD_END)


def test_draft_with_no_comparable_runs_bills_the_base_fee_only(session):
    actor = make_admin(session)
    client = make_client(session)
    session.commit()

    invoice = billing.draft_invoice(session, actor, client.id, PERIOD_START, PERIOD_END)

    assert invoice.suggested_recovered_waste == Decimal("0.00")
    assert invoice.performance_fee == Decimal("0.00")
    assert invoice.total == Decimal("15000.00")


def test_confirm_accepts_the_suggestion_unchanged(session):
    actor = make_admin(session)
    client = _client_with_23k_recovered(session)
    session.commit()
    invoice = billing.draft_invoice(session, actor, client.id, PERIOD_START, PERIOD_END)

    confirmed = billing.confirm_invoice(session, actor, invoice.id, Decimal("23000"))

    assert confirmed.confirmed_recovered_waste == Decimal("23000.00")
    assert confirmed.performance_fee == Decimal("4600.00")
    assert confirmed.total == Decimal("19600.00")
    assert confirmed.confirmed_by == actor.id
    assert confirmed.status == "draft"  # confirming does not issue

    actions = [e.action for e in session.query(AuditLog).order_by(AuditLog.id).all()]
    assert actions == ["invoice.draft", "invoice.confirm"]


def test_confirm_with_an_edited_amount_recomputes_the_fee(session):
    actor = make_admin(session)
    client = _client_with_23k_recovered(session)
    session.commit()
    invoice = billing.draft_invoice(session, actor, client.id, PERIOD_START, PERIOD_END)

    confirmed = billing.confirm_invoice(session, actor, invoice.id, Decimal("10000"))

    assert confirmed.suggested_recovered_waste == Decimal("23000.00")  # the suggestion is kept
    assert confirmed.confirmed_recovered_waste == Decimal("10000.00")
    assert confirmed.performance_fee == Decimal("2000.00")
    assert confirmed.total == Decimal("17000.00")

    entry = session.query(AuditLog).order_by(AuditLog.id.desc()).first()
    assert entry.before["performance_fee"] == "4600.00"
    assert entry.after["performance_fee"] == "2000.00"


def test_confirm_applies_the_clients_performance_fee_cap(session):
    actor = make_admin(session)
    client = _client_with_23k_recovered(session, config_overrides={"performance_fee_cap": "3000"})
    session.commit()
    invoice = billing.draft_invoice(session, actor, client.id, PERIOD_START, PERIOD_END)

    assert invoice.performance_fee == Decimal("3000.00")  # capped, not 4,600
    confirmed = billing.confirm_invoice(session, actor, invoice.id, Decimal("23000"))
    assert confirmed.performance_fee == Decimal("3000.00")
    assert confirmed.total == Decimal("18000.00")


def test_confirm_rejects_a_negative_amount(session):
    actor = make_admin(session)
    client = _client_with_23k_recovered(session)
    session.commit()
    invoice = billing.draft_invoice(session, actor, client.id, PERIOD_START, PERIOD_END)

    with pytest.raises(ConflictError, match="must be >= 0"):
        billing.confirm_invoice(session, actor, invoice.id, Decimal("-1"))


def test_issue_requires_a_confirmed_fee_then_sets_status_and_dates(session):
    actor = make_admin(session)
    client = _client_with_23k_recovered(session)
    session.commit()
    invoice = billing.draft_invoice(session, actor, client.id, PERIOD_START, PERIOD_END)

    with pytest.raises(ConflictError, match="confirm the performance fee"):
        billing.issue_invoice(session, actor, invoice.id, date(2026, 9, 20))

    billing.confirm_invoice(session, actor, invoice.id, Decimal("23000"))
    issued = billing.issue_invoice(session, actor, invoice.id, date(2026, 9, 20))

    assert issued.status == "issued"
    assert issued.due_date == date(2026, 9, 20)
    assert issued.issued_at is not None

    with pytest.raises(ConflictError, match="is issued, not draft"):
        billing.issue_invoice(session, actor, invoice.id, date(2026, 9, 25))


def test_void_records_the_reason_in_the_audit_row(session):
    actor = make_admin(session)
    client = _client_with_23k_recovered(session)
    session.commit()
    invoice = billing.draft_invoice(session, actor, client.id, PERIOD_START, PERIOD_END)

    voided = billing.void_invoice(session, actor, invoice.id, note="drafted for the wrong month")

    assert voided.status == "void"
    entry = session.query(AuditLog).order_by(AuditLog.id.desc()).first()
    assert entry.action == "invoice.void"
    assert entry.after["note"] == "drafted for the wrong month"

    with pytest.raises(ConflictError, match="is void"):
        billing.void_invoice(session, actor, invoice.id, note="again")


def test_list_invoices_filters_by_client_and_status(session):
    actor = make_admin(session)
    one = _client_with_23k_recovered(session)
    two = make_client(session, email="two@example.com", business_name="Two Co")
    session.commit()
    a = billing.draft_invoice(session, actor, one.id, PERIOD_START, PERIOD_END)
    billing.draft_invoice(session, actor, two.id, PERIOD_START, PERIOD_END)
    billing.confirm_invoice(session, actor, a.id, Decimal("23000"))
    billing.issue_invoice(session, actor, a.id, date(2026, 9, 20))

    assert len(billing.list_invoices(session)) == 2
    assert [i.client_id for i in billing.list_invoices(session, client_id=two.id)] == [two.id]
    assert [i.invoice_number for i in billing.list_invoices(session, status="issued")] == [
        "INV-2026-0001"
    ]


def test_missing_invoice_raises_not_found(session):
    actor = make_admin(session)
    session.commit()
    with pytest.raises(NotFoundError, match="invoice 77 not found"):
        billing.confirm_invoice(session, actor, 77, Decimal("0"))


# --- Fix round 1 -----------------------------------------------------------------------


def test_confirm_freezes_the_base_fee_at_draft_time(session):
    """F1: an admin editing the client's base_fee between draft and confirm must not
    silently change an already-drafted invoice's total (Stage 6 Task 2 shipped fee edits).
    """
    actor = make_admin(session)
    client = _client_with_23k_recovered(session)  # base_fee 15,000 at draft time
    session.commit()
    invoice = billing.draft_invoice(session, actor, client.id, PERIOD_START, PERIOD_END)
    assert invoice.base_fee == Decimal("15000.00")

    client.base_fee = Decimal("99000.00")
    session.commit()

    confirmed = billing.confirm_invoice(session, actor, invoice.id, Decimal("23000"))

    # base_fee stays what it was at draft time...
    assert confirmed.base_fee == Decimal("15000.00")
    # ...but the performance_fee_pct is still the client's CURRENT value (unaffected here,
    # still 20%), and the fee/total use the frozen base_fee, not the edited 99,000.
    assert confirmed.performance_fee == Decimal("4600.00")
    assert confirmed.total == Decimal("19600.00")


def test_confirm_still_uses_the_clients_current_performance_fee_pct(session):
    actor = make_admin(session)
    client = _client_with_23k_recovered(session)
    session.commit()
    invoice = billing.draft_invoice(session, actor, client.id, PERIOD_START, PERIOD_END)

    client.performance_fee_pct = Decimal("30.00")
    session.commit()

    confirmed = billing.confirm_invoice(session, actor, invoice.id, Decimal("23000"))

    # base_fee frozen at 15,000, but the pct is the new 30%: 23,000 * 30% = 6,900.
    assert confirmed.base_fee == Decimal("15000.00")
    assert confirmed.performance_fee == Decimal("6900.00")
    assert confirmed.total == Decimal("21900.00")


def test_overlapping_period_is_blocked_even_with_different_end_dates(session):
    """F3: a one-day-shifted period must not slip past an exact-match-only guard."""
    actor = make_admin(session)
    client = _client_with_23k_recovered(session)
    session.commit()
    billing.draft_invoice(session, actor, client.id, PERIOD_START, PERIOD_END)  # Aug 1-31

    with pytest.raises(ConflictError, match="already covers"):
        billing.draft_invoice(session, actor, client.id, PERIOD_START, date(2026, 8, 30))


def test_adjacent_non_overlapping_period_is_allowed(session):
    actor = make_admin(session)
    client = _client_with_23k_recovered(session)
    session.commit()
    billing.draft_invoice(session, actor, client.id, PERIOD_START, PERIOD_END)  # Aug 1-31

    september = billing.draft_invoice(
        session, actor, client.id, date(2026, 9, 1), date(2026, 9, 30)
    )
    assert september.invoice_number == "INV-2026-0002"


def test_new_draft_is_allowed_after_the_overlapping_invoice_is_voided(session):
    actor = make_admin(session)
    client = _client_with_23k_recovered(session)
    session.commit()
    first = billing.draft_invoice(session, actor, client.id, PERIOD_START, PERIOD_END)
    billing.void_invoice(session, actor, first.id, note="wrong period")

    second = billing.draft_invoice(session, actor, client.id, PERIOD_START, date(2026, 8, 30))
    assert second.status == "draft"


def test_invoice_number_collision_retries_and_succeeds(session, monkeypatch):
    """F4: a colliding invoice_number must retry rather than surface a raw IntegrityError."""
    actor = make_admin(session)
    client = _client_with_23k_recovered(session)
    session.commit()
    first = billing.draft_invoice(session, actor, client.id, PERIOD_START, PERIOD_END)
    assert first.invoice_number == "INV-2026-0001"

    real_next = billing._next_invoice_number
    calls = {"n": 0}

    def colliding_once(session, year):
        calls["n"] += 1
        if calls["n"] == 1:
            return first.invoice_number  # force a UNIQUE collision on the first attempt
        return real_next(session, year)

    monkeypatch.setattr(billing, "_next_invoice_number", colliding_once)

    second = billing.draft_invoice(session, actor, client.id, date(2026, 9, 1), date(2026, 9, 30))
    assert second.invoice_number == "INV-2026-0002"
    assert calls["n"] == 2


def _seed_invoice_number(session, client, number):
    session.add(
        Invoice(
            invoice_number=number,
            client_id=client.id,
            period_start=date(2020, 1, 1),
            period_end=date(2020, 1, 31),
            due_date=date(2020, 2, 14),
            base_fee=Decimal("0.00"),
            suggested_recovered_waste=Decimal("0.00"),
            confirmed_recovered_waste=Decimal("0.00"),
            performance_fee=Decimal("0.00"),
            total=Decimal("0.00"),
            amount_paid=Decimal("0.00"),
            status="void",
        )
    )


def test_invoice_numbering_survives_the_9999_to_10000_boundary(session):
    """F5: a text MAX() over BOTH suffix widths compares "...-9999" > "...-10000"
    lexicographically ('9' > '1' at the first differing character), so with both rows
    present a text MAX() picks "9999" and regenerates "...-10000" forever instead of
    advancing to "...-10001".
    """
    client = make_client(session)
    _seed_invoice_number(session, client, "INV-2026-9999")
    _seed_invoice_number(session, client, "INV-2026-10000")
    session.commit()

    assert billing._next_invoice_number(session, 2026) == "INV-2026-10001"


def test_invoice_numbering_keeps_advancing_past_10000(session):
    client = make_client(session)
    _seed_invoice_number(session, client, "INV-2026-10000")
    _seed_invoice_number(session, client, "INV-2026-10001")
    session.commit()

    assert billing._next_invoice_number(session, 2026) == "INV-2026-10002"


def test_draft_rejects_an_inverted_period(session):
    actor = make_admin(session)
    client = _client_with_23k_recovered(session)
    session.commit()

    with pytest.raises(ConflictError, match="period_end is before period_start"):
        billing.draft_invoice(session, actor, client.id, PERIOD_END, PERIOD_START)


def test_confirm_rejects_a_non_draft_invoice(session):
    actor = make_admin(session)
    client = _client_with_23k_recovered(session)
    session.commit()
    invoice = billing.draft_invoice(session, actor, client.id, PERIOD_START, PERIOD_END)
    billing.confirm_invoice(session, actor, invoice.id, Decimal("23000"))
    billing.issue_invoice(session, actor, invoice.id, date(2026, 9, 20))

    with pytest.raises(ConflictError, match="is issued, not draft"):
        billing.confirm_invoice(session, actor, invoice.id, Decimal("1"))


def test_void_rejects_a_paid_invoice(session):
    actor = make_admin(session)
    client = _client_with_23k_recovered(session)
    session.commit()
    invoice = billing.draft_invoice(session, actor, client.id, PERIOD_START, PERIOD_END)
    billing.confirm_invoice(session, actor, invoice.id, Decimal("23000"))
    billing.issue_invoice(session, actor, invoice.id, date(2026, 9, 20))
    invoice.status = "paid"
    session.commit()

    with pytest.raises(ConflictError, match="invoice INV-2026-0001 is paid"):
        billing.void_invoice(session, actor, invoice.id, note="too late")
