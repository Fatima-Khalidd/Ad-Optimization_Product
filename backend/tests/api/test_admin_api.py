"""Stage 6 exit criteria, exercised over HTTP (docs/PLAN.md section 6)."""

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import event

from tests.api.helpers import login_as, make_admin, make_client, make_run, user_for

BEFORE = datetime(2026, 7, 20, tzinfo=UTC)
INSIDE = datetime(2026, 8, 25, tzinfo=UTC)
AUGUST = {"period_start": "2026-08-01", "period_end": "2026-08-31"}


def _client_with_pending_run(db):
    client = make_client(db)
    run = make_run(
        db,
        client,
        created_at=INSIDE,
        review_status="pending",
        headline_waste=Decimal("52000"),
        segments=(
            ("placement", "audience_network", "52000", True),
            ("placement", "facebook_feed", "0", False),
            ("age_group", "55-64", "12000", True),
        ),
    )
    db.commit()
    return client, run


def test_approving_a_run_is_what_lets_the_client_see_the_report(api, db):
    admin = make_admin(db)
    client, run = _client_with_pending_run(db)

    # Before approval the client cannot see it at all.
    login_as(api, user_for(db, client))
    assert api.get(f"/api/reports/{run.id}").status_code == 404

    login_as(api, admin)
    approved = api.post(f"/api/admin/runs/{run.id}/approve", json={"note": "checked"})
    assert approved.status_code == 200
    assert approved.json()["review_status"] == "approved"

    login_as(api, user_for(db, client))
    report = api.get(f"/api/reports/{run.id}")
    assert report.status_code == 200
    assert report.json()["run_id"] == run.id


def test_a_rejected_run_stays_invisible_to_the_client(api, db):
    admin = make_admin(db)
    client, run = _client_with_pending_run(db)

    login_as(api, admin)
    rejected = api.post(f"/api/admin/runs/{run.id}/reject", json={"note": "wrong month"})
    assert rejected.status_code == 200
    assert rejected.json()["review_status"] == "rejected"

    login_as(api, user_for(db, client))
    assert api.get(f"/api/reports/{run.id}").status_code == 404


def test_reviewing_the_same_run_twice_is_409(api, db):
    admin = make_admin(db)
    _client, run = _client_with_pending_run(db)
    login_as(api, admin)

    assert api.post(f"/api/admin/runs/{run.id}/approve", json={"note": None}).status_code == 200
    second = api.post(f"/api/admin/runs/{run.id}/reject", json={"note": None})
    assert second.status_code == 409
    assert "already approved" in second.json()["detail"]


def test_the_queue_carries_dimension_totals_flagged_segments_and_the_config_snapshot(api, db):
    admin = make_admin(db)
    client, run = _client_with_pending_run(db)
    login_as(api, admin)

    rows = api.get("/api/admin/runs", params={"review_status": "pending"}).json()

    assert len(rows) == 1
    row = rows[0]
    assert row["id"] == run.id
    assert row["business_name"] == client.business_name
    assert row["headline_waste"] == "52000.00"
    assert {d["dimension"] for d in row["dimensions"]} == {"age_group", "placement"}
    assert [s["segment_value"] for s in row["flagged_segments"]] == ["audience_network", "55-64"]
    assert row["config_snapshot"]["benchmark_mode"] == "account_avg"


def test_the_queue_avoids_n_plus_1_client_lookups(api, db, bound_engine):
    """Three runs across three distinct clients must not issue one clients query per row.

    The router fetches every distinct client behind the queue in a single `clients` SELECT
    keyed by id, builds an in-memory {id: Client} map, and passes each run's row straight
    into serialize_run() — so however many runs are in the queue, the number of queries
    against `clients` stays flat (one), not O(n).
    """
    admin = make_admin(db)
    for i in range(3):
        client = make_client(db, email=f"c{i}@example.com", business_name=f"Biz {i}")
        make_run(db, client, created_at=INSIDE, review_status="pending")
    db.commit()
    login_as(api, admin)

    statements: list[str] = []

    def _capture(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(bound_engine, "before_cursor_execute", _capture)
    try:
        response = api.get("/api/admin/runs", params={"review_status": "pending"})
    finally:
        event.remove(bound_engine, "before_cursor_execute", _capture)

    assert response.status_code == 200
    assert len(response.json()) == 3

    client_queries = [s for s in statements if "FROM clients" in s]
    assert len(client_queries) == 1, client_queries


def test_patching_a_client_changes_fees_and_shows_up_in_the_audit_log(api, db):
    admin = make_admin(db)
    client = make_client(db)
    db.commit()
    login_as(api, admin)

    response = api.patch(
        f"/api/admin/clients/{client.id}",
        json={"base_fee": "25000", "config_overrides": {"waste_multiplier": 2.0}},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["base_fee"] == "25000.00"
    assert body["config_overrides"] == {"waste_multiplier": 2.0}

    entries = api.get("/api/admin/audit-log", params={"entity_type": "client"}).json()
    assert [e["action"] for e in entries] == ["client.update"]
    assert entries[0]["before"]["base_fee"] == "15000.00"
    assert entries[0]["after"]["base_fee"] == "25000.00"
    assert entries[0]["actor_user_id"] == admin.id


def test_an_unknown_config_override_key_is_422(api, db):
    admin = make_admin(db)
    client = make_client(db)
    db.commit()
    login_as(api, admin)

    response = api.patch(
        f"/api/admin/clients/{client.id}", json={"config_overrides": {"typo_key": 1}}
    )

    assert response.status_code == 422
    assert "unknown config key: typo_key" in response.json()["detail"]
    assert api.get(f"/api/admin/clients/{client.id}").json()["config_overrides"] == {}


def test_invoice_draft_confirm_issue_happy_path_with_exact_numbers(api, db):
    admin = make_admin(db)
    client = make_client(db)  # base_fee 15,000 ; performance_fee_pct 20
    make_run(
        db,
        client,
        created_at=BEFORE,
        review_status="approved",
        segments=(
            ("placement", "audience_network", "52000", True),
            ("placement", "reels", "1000", True),
        ),
    )
    make_run(
        db,
        client,
        created_at=INSIDE,
        review_status="approved",
        segments=(
            ("placement", "audience_network", "30000", True),
            ("placement", "reels", "0", False),
        ),
    )
    db.commit()
    login_as(api, admin)

    draft = api.post("/api/admin/invoices", json={"client_id": client.id, **AUGUST})
    assert draft.status_code == 201
    drafted = draft.json()
    assert drafted["invoice_number"] == "INV-2026-0001"
    assert drafted["status"] == "draft"
    assert drafted["suggested_recovered_waste"] == "23000.00"
    assert drafted["base_fee"] == "15000.00"
    assert drafted["performance_fee"] == "4600.00"
    assert drafted["total"] == "19600.00"

    invoice_id = drafted["id"]
    confirmed = api.post(
        f"/api/admin/invoices/{invoice_id}/confirm", json={"confirmed_recovered_waste": "23000"}
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["confirmed_recovered_waste"] == "23000.00"
    assert confirmed.json()["performance_fee"] == "4600.00"
    assert confirmed.json()["total"] == "19600.00"
    assert confirmed.json()["status"] == "draft"

    issued = api.post(f"/api/admin/invoices/{invoice_id}/issue", json={"due_date": "2026-09-20"})
    assert issued.status_code == 200
    assert issued.json()["status"] == "issued"
    assert issued.json()["due_date"] == "2026-09-20"
    assert issued.json()["issued_at"] is not None

    listed = api.get("/api/admin/invoices", params={"status": "issued"}).json()
    assert [i["invoice_number"] for i in listed] == ["INV-2026-0001"]

    actions = [
        e["action"]
        for e in api.get("/api/admin/audit-log", params={"entity_type": "invoice"}).json()
    ]
    assert actions == ["invoice.issue", "invoice.confirm", "invoice.draft"]  # newest first


def test_issuing_before_confirming_is_409(api, db):
    admin = make_admin(db)
    client = make_client(db)
    db.commit()
    login_as(api, admin)
    invoice_id = api.post("/api/admin/invoices", json={"client_id": client.id, **AUGUST}).json()[
        "id"
    ]

    response = api.post(f"/api/admin/invoices/{invoice_id}/issue", json={"due_date": "2026-09-20"})

    assert response.status_code == 409
    assert "confirm the performance fee" in response.json()["detail"]


def test_voiding_a_draft_records_the_reason(api, db):
    admin = make_admin(db)
    client = make_client(db)
    db.commit()
    login_as(api, admin)
    invoice_id = api.post("/api/admin/invoices", json={"client_id": client.id, **AUGUST}).json()[
        "id"
    ]

    response = api.post(f"/api/admin/invoices/{invoice_id}/void", json={"note": "wrong month"})

    assert response.status_code == 200
    assert response.json()["status"] == "void"
    entry = api.get("/api/admin/audit-log", params={"action": "invoice.void"}).json()[0]
    assert entry["after"]["note"] == "wrong month"


def test_drafting_for_a_missing_client_is_404(api, db):
    admin = make_admin(db)
    db.commit()
    login_as(api, admin)

    response = api.post("/api/admin/invoices", json={"client_id": 999, **AUGUST})

    assert response.status_code == 404
    assert response.json()["detail"] == "client 999 not found"


def test_a_negative_confirmed_amount_is_rejected_by_the_schema(api, db):
    admin = make_admin(db)
    client = make_client(db)
    db.commit()
    login_as(api, admin)
    invoice_id = api.post("/api/admin/invoices", json={"client_id": client.id, **AUGUST}).json()[
        "id"
    ]

    response = api.post(
        f"/api/admin/invoices/{invoice_id}/confirm", json={"confirmed_recovered_waste": "-5"}
    )

    assert response.status_code == 422


def test_an_absurdly_large_confirmed_amount_is_422_not_a_db_error(api, db):
    """F5: NUMERIC(14,2) allows 12 integer digits; confirmed_recovered_waste alone feeding
    into total (base_fee + performance_fee) must stay well inside that headroom, so the
    schema bound should reject before the value ever reaches the database."""
    admin = make_admin(db)
    client = make_client(db)
    db.commit()
    login_as(api, admin)
    invoice_id = api.post("/api/admin/invoices", json={"client_id": client.id, **AUGUST}).json()[
        "id"
    ]

    response = api.post(
        f"/api/admin/invoices/{invoice_id}/confirm",
        json={"confirmed_recovered_waste": "99999999999999"},
    )

    assert response.status_code == 422


def test_invoice_rows_carry_the_clients_business_name(api, db):
    admin = make_admin(db)
    client = make_client(db)
    db.commit()
    login_as(api, admin)
    draft = api.post("/api/admin/invoices", json={"client_id": client.id, **AUGUST})

    assert draft.json()["business_name"] == client.business_name
    listed = api.get("/api/admin/invoices").json()
    assert listed[0]["business_name"] == client.business_name


# --------------------------------------------------------------------------- F5(e): requeue

STALE = datetime(2020, 1, 1, tzinfo=UTC)


def test_admin_can_requeue_a_stale_running_run(api, db):
    admin = make_admin(db)
    client = make_client(db)
    run = make_run(db, client, created_at=STALE, status="running", headline_waste=None)
    db.commit()

    login_as(api, admin)
    response = api.post(f"/api/admin/runs/{run.id}/requeue")

    assert response.status_code == 200
    assert response.json()["status"] == "queued"


def test_requeuing_a_fresh_running_run_is_409(api, db):
    admin = make_admin(db)
    client = make_client(db)
    run = make_run(db, client, created_at=datetime.now(UTC), status="running", headline_waste=None)
    db.commit()

    login_as(api, admin)
    response = api.post(f"/api/admin/runs/{run.id}/requeue")

    assert response.status_code == 409
