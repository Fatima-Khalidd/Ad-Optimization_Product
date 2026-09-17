from datetime import UTC, date, datetime
from decimal import Decimal

from app.services import billing
from tests.api.helpers import make_client, make_run

PERIOD_START = date(2026, 8, 1)
PERIOD_END = date(2026, 8, 31)
BEFORE = datetime(2026, 7, 20, tzinfo=UTC)   # baseline: the last approved run before August
INSIDE = datetime(2026, 8, 25, tzinfo=UTC)   # current: an approved run inside August


def _baseline(session, client):
    # Flagged in July: audience_network wasted 52,000 and reels wasted 1,000.
    return make_run(
        session,
        client,
        created_at=BEFORE,
        review_status="approved",
        segments=(
            ("placement", "audience_network", "52000", True),
            ("placement", "reels", "1000", True),
            ("placement", "facebook_feed", "0", False),
        ),
    )


def test_hand_computed_suggestion(session):
    client = make_client(session)
    _baseline(session, client)
    # In August audience_network is still flagged but only wastes 30,000, and reels is no
    # longer flagged at all (so its waste now is 0).
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
    session.commit()

    # (52,000 - 30,000) + (1,000 - 0) = 23,000
    assert billing.suggest_recovered_waste(session, client.id, PERIOD_START, PERIOD_END) == Decimal(
        "23000.00"
    )


def test_a_segment_that_disappeared_from_the_current_run_counts_in_full(session):
    client = make_client(session)
    _baseline(session, client)
    make_run(
        session,
        client,
        created_at=INSIDE,
        review_status="approved",
        segments=(("placement", "audience_network", "52000", True),),
    )
    session.commit()

    # audience_network unchanged (0) + reels missing entirely (1,000 - 0) = 1,000
    assert billing.suggest_recovered_waste(session, client.id, PERIOD_START, PERIOD_END) == Decimal(
        "1000.00"
    )


def test_waste_that_got_worse_never_goes_negative(session):
    client = make_client(session)
    _baseline(session, client)
    make_run(
        session,
        client,
        created_at=INSIDE,
        review_status="approved",
        segments=(
            ("placement", "audience_network", "70000", True),
            ("placement", "reels", "1000", True),
        ),
    )
    session.commit()

    assert billing.suggest_recovered_waste(session, client.id, PERIOD_START, PERIOD_END) == Decimal(
        "0.00"
    )


def test_missing_baseline_returns_zero(session):
    client = make_client(session)
    make_run(
        session,
        client,
        created_at=INSIDE,
        review_status="approved",
        segments=(("placement", "audience_network", "30000", True),),
    )
    session.commit()

    assert billing.suggest_recovered_waste(session, client.id, PERIOD_START, PERIOD_END) == Decimal(
        "0.00"
    )


def test_missing_current_run_returns_zero(session):
    client = make_client(session)
    _baseline(session, client)
    session.commit()

    assert billing.suggest_recovered_waste(session, client.id, PERIOD_START, PERIOD_END) == Decimal(
        "0.00"
    )


def test_unapproved_runs_are_ignored_on_both_sides(session):
    client = make_client(session)
    _baseline(session, client)
    make_run(
        session,
        client,
        created_at=INSIDE,
        review_status="pending",
        segments=(("placement", "audience_network", "30000", True),),
    )
    session.commit()

    assert billing.suggest_recovered_waste(session, client.id, PERIOD_START, PERIOD_END) == Decimal(
        "0.00"
    )


def test_another_clients_runs_are_never_mixed_in(session):
    client = make_client(session)
    other = make_client(session, email="other@example.com", business_name="Other Co")
    _baseline(session, other)
    make_run(
        session,
        other,
        created_at=INSIDE,
        review_status="approved",
        segments=(("placement", "audience_network", "0", True),),
    )
    session.commit()

    assert billing.suggest_recovered_waste(session, client.id, PERIOD_START, PERIOD_END) == Decimal(
        "0.00"
    )


def test_only_flagged_baseline_segments_are_counted(session):
    client = make_client(session)
    make_run(
        session,
        client,
        created_at=BEFORE,
        review_status="approved",
        segments=(("placement", "facebook_feed", "5000", False),),  # unflagged in the baseline
    )
    make_run(
        session,
        client,
        created_at=INSIDE,
        review_status="approved",
        segments=(("placement", "facebook_feed", "0", False),),
    )
    session.commit()

    assert billing.suggest_recovered_waste(session, client.id, PERIOD_START, PERIOD_END) == Decimal(
        "0.00"
    )


def test_the_run_on_the_last_day_of_the_period_still_counts(session):
    client = make_client(session)
    _baseline(session, client)
    make_run(
        session,
        client,
        created_at=datetime(2026, 8, 31, 23, 59, tzinfo=UTC),
        review_status="approved",
        segments=(
            ("placement", "audience_network", "30000", True),
            ("placement", "reels", "0", False),
        ),
    )
    session.commit()

    assert billing.suggest_recovered_waste(session, client.id, PERIOD_START, PERIOD_END) == Decimal(
        "23000.00"
    )
