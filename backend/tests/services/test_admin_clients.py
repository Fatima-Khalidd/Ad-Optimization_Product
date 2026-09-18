from decimal import Decimal

import pytest

from app.core.errors import InvalidConfigError, NotFoundError
from app.models import AuditLog
from app.schemas.admin import ClientPatch
from app.services import admin
from tests.api.helpers import make_admin, make_client


def test_list_clients_is_alphabetical(session):
    make_client(session, email="z@example.com", business_name="Zephyr Foods")
    make_client(session, email="a@example.com", business_name="Alpha Motors")
    session.commit()

    assert [c.business_name for c in admin.list_clients(session)] == [
        "Alpha Motors",
        "Zephyr Foods",
    ]


def test_get_client_raises_not_found_for_a_missing_id(session):
    with pytest.raises(NotFoundError, match="client 999 not found"):
        admin.get_client(session, 999)


def test_update_client_changes_fees_and_writes_one_audit_row(session):
    actor = make_admin(session)
    client = make_client(session, base_fee=Decimal("15000"), performance_fee_pct=Decimal("20"))
    session.commit()

    updated = admin.update_client(
        session,
        actor,
        client.id,
        ClientPatch(base_fee=Decimal("25000"), performance_fee_pct=Decimal("15")),
    )

    assert updated.base_fee == Decimal("25000.00")
    assert updated.performance_fee_pct == Decimal("15.00")

    entries = session.query(AuditLog).all()
    assert len(entries) == 1
    entry = entries[0]
    assert entry.action == "client.update"
    assert entry.entity_type == "client"
    assert entry.entity_id == client.id
    assert entry.actor_user_id == actor.id
    assert entry.before["base_fee"] == "15000.00"
    assert entry.after["base_fee"] == "25000.00"
    assert entry.before["performance_fee_pct"] == "20.00"
    assert entry.after["performance_fee_pct"] == "15.00"


def test_update_client_leaves_unmentioned_fields_alone(session):
    actor = make_admin(session)
    client = make_client(session, base_fee=Decimal("15000"), config_overrides={"min_spend": 9000})
    session.commit()

    updated = admin.update_client(session, actor, client.id, ClientPatch(base_fee=Decimal("18000")))

    assert updated.base_fee == Decimal("18000.00")
    assert updated.performance_fee_pct == Decimal("20.00")
    assert updated.config_overrides == {"min_spend": 9000}


def test_update_client_accepts_valid_config_overrides(session):
    actor = make_admin(session)
    client = make_client(session)
    session.commit()

    updated = admin.update_client(
        session,
        actor,
        client.id,
        ClientPatch(config_overrides={"waste_multiplier": 2.0, "min_clicks": 50}),
    )

    assert updated.config_overrides == {"waste_multiplier": 2.0, "min_clicks": 50}


def test_update_client_rejects_an_unknown_config_key_and_writes_nothing(session):
    actor = make_admin(session)
    client = make_client(session)
    session.commit()

    with pytest.raises(InvalidConfigError, match="unknown config key: typo_key"):
        admin.update_client(
            session, actor, client.id, ClientPatch(config_overrides={"typo_key": 1})
        )

    session.rollback()
    assert session.query(AuditLog).count() == 0
    assert admin.get_client(session, client.id).config_overrides == {}


def test_update_client_rejects_a_bad_benchmark_mode(session):
    actor = make_admin(session)
    client = make_client(session)
    session.commit()

    with pytest.raises(InvalidConfigError, match="benchmark_mode"):
        admin.update_client(
            session, actor, client.id, ClientPatch(config_overrides={"benchmark_mode": "median"})
        )


def test_client_patch_forbids_unknown_fields():
    with pytest.raises(ValueError):
        ClientPatch(role="admin")


def test_update_client_with_no_actual_change_writes_no_audit_row(session):
    """F4: the UI always posts all three fields, so a Save with unchanged values must not
    dilute the audit log with a before == after row."""
    actor = make_admin(session)
    client = make_client(
        session,
        base_fee=Decimal("15000"),
        performance_fee_pct=Decimal("20"),
        config_overrides={"min_spend": 9000},
    )
    session.commit()

    updated = admin.update_client(
        session,
        actor,
        client.id,
        ClientPatch(
            base_fee=Decimal("15000"),
            performance_fee_pct=Decimal("20"),
            config_overrides={"min_spend": 9000},
        ),
    )

    assert updated.base_fee == Decimal("15000.00")
    assert session.query(AuditLog).count() == 0


def test_update_client_with_one_real_change_writes_exactly_one_row(session):
    actor = make_admin(session)
    client = make_client(session, base_fee=Decimal("15000"), performance_fee_pct=Decimal("20"))
    session.commit()

    admin.update_client(
        session,
        actor,
        client.id,
        ClientPatch(base_fee=Decimal("15000"), performance_fee_pct=Decimal("25")),
    )

    entries = session.query(AuditLog).all()
    assert len(entries) == 1
    assert entries[0].before["performance_fee_pct"] == "20.00"
    assert entries[0].after["performance_fee_pct"] == "25.00"


def test_a_failed_audit_write_rolls_back_the_fee_change(session, monkeypatch):
    """The audit row and the fee change share one transaction — if record() blows up,
    base_fee must still read the old value on the next query, not the new one."""
    actor = make_admin(session)
    client = make_client(session, base_fee=Decimal("15000"))
    session.commit()

    def _boom(*args, **kwargs):
        raise RuntimeError("audit backend is down")

    monkeypatch.setattr(admin.audit, "record", _boom)

    with pytest.raises(RuntimeError, match="audit backend is down"):
        admin.update_client(session, actor, client.id, ClientPatch(base_fee=Decimal("99000")))

    session.rollback()
    session.expire_all()
    assert admin.get_client(session, client.id).base_fee == Decimal("15000.00")
