from decimal import Decimal

from app.models import AuditLog
from app.services import audit
from tests.api.helpers import make_admin, make_client


def test_record_stores_actor_entity_and_both_snapshots(session):
    admin = make_admin(session)
    client = make_client(session)

    entry = audit.record(
        session,
        actor_user_id=admin.id,
        action="client.update",
        entity_type="client",
        entity_id=client.id,
        before={"base_fee": "15000.00"},
        after={"base_fee": "20000.00"},
    )

    assert entry.id is not None  # flushed, so later audit rows can be ordered
    stored = session.get(AuditLog, entry.id)
    assert stored.actor_user_id == admin.id
    assert stored.action == "client.update"
    assert stored.entity_type == "client"
    assert stored.entity_id == client.id
    assert stored.before == {"base_fee": "15000.00"}
    assert stored.after == {"base_fee": "20000.00"}
    assert stored.created_at is not None


def test_record_does_not_commit_so_a_rollback_takes_the_entry_with_it(session):
    admin = make_admin(session)
    session.commit()

    audit.record(
        session, admin.id, "run.approve", "analysis_run", 1, None, {"review_status": "approved"}
    )
    session.rollback()

    assert session.query(AuditLog).count() == 0


def test_snapshot_is_json_safe(session):
    import json

    client = make_client(session)
    client.config_overrides = {"waste_multiplier": 2.0}
    session.flush()

    data = audit.snapshot(
        client, ("base_fee", "performance_fee_pct", "config_overrides", "created_at")
    )

    json.dumps(data)  # must not raise: Decimal and datetime are stringified
    assert data["base_fee"] == "15000.00"
    assert data["performance_fee_pct"] == "20.00"
    assert data["config_overrides"] == {"waste_multiplier": 2.0}
    assert isinstance(data["created_at"], str)


def test_list_entries_is_newest_first_and_filterable(session):
    admin = make_admin(session)
    audit.record(session, admin.id, "client.update", "client", 1, None, None)
    audit.record(session, admin.id, "run.approve", "analysis_run", 7, None, None)
    audit.record(session, admin.id, "run.reject", "analysis_run", 8, None, None)
    session.flush()

    newest = audit.list_entries(session)
    assert [e.action for e in newest] == ["run.reject", "run.approve", "client.update"]

    runs_only = audit.list_entries(session, entity_type="analysis_run")
    assert [e.entity_id for e in runs_only] == [8, 7]

    assert [e.action for e in audit.list_entries(session, action="client.update")] == [
        "client.update"
    ]
    assert len(audit.list_entries(session, limit=1)) == 1


def test_decimal_amounts_survive_a_snapshot_round_trip(session):
    client = make_client(session, base_fee=Decimal("12345.67"))
    session.flush()

    data = audit.snapshot(client, ("base_fee",))

    assert data["base_fee"] == "12345.67"  # a string, so JSONB never sees a float
    assert Decimal(data["base_fee"]) == Decimal("12345.67")
