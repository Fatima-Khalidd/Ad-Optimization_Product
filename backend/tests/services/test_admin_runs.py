from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.core.errors import ConflictError, NotFoundError
from app.models import AuditLog
from app.services import admin
from app.services.analysis import get_report
from tests.api.helpers import make_admin, make_client, make_run

AUG = datetime(2026, 8, 15, tzinfo=UTC)
SEP = datetime(2026, 9, 15, tzinfo=UTC)


def test_list_runs_is_newest_first_and_filters_by_review_status(session):
    client = make_client(session)
    older = make_run(session, client, created_at=AUG, review_status="approved")
    newer = make_run(session, client, created_at=SEP, review_status="pending")
    session.commit()

    assert [r.id for r in admin.list_runs(session)] == [newer.id, older.id]
    assert [r.id for r in admin.list_runs(session, review_status="pending")] == [newer.id]
    assert [r.id for r in admin.list_runs(session, review_status="approved")] == [older.id]
    assert admin.list_runs(session, review_status="rejected") == []


def test_approve_run_sets_reviewer_fields_and_audits(session):
    actor = make_admin(session)
    client = make_client(session)
    run = make_run(session, client, created_at=AUG, headline_waste=Decimal("52000"))
    session.commit()

    approved = admin.approve_run(session, actor, run.id, note="numbers checked against the CSV")

    assert approved.review_status == "approved"
    assert approved.reviewed_by == actor.id
    assert approved.reviewed_at is not None
    assert approved.review_note == "numbers checked against the CSV"

    entry = session.query(AuditLog).one()
    assert entry.action == "run.approve"
    assert entry.entity_type == "analysis_run"
    assert entry.entity_id == run.id
    assert entry.actor_user_id == actor.id
    assert entry.before["review_status"] == "pending"
    assert entry.after["review_status"] == "approved"
    assert entry.after["review_note"] == "numbers checked against the CSV"


def test_reject_run_records_the_reason(session):
    actor = make_admin(session)
    client = make_client(session)
    run = make_run(session, client, created_at=AUG)
    session.commit()

    rejected = admin.reject_run(session, actor, run.id, note="client uploaded the wrong month")

    assert rejected.review_status == "rejected"
    assert rejected.review_note == "client uploaded the wrong month"
    assert session.query(AuditLog).one().action == "run.reject"


def test_a_run_can_only_be_reviewed_once(session):
    actor = make_admin(session)
    client = make_client(session)
    run = make_run(session, client, created_at=AUG)
    session.commit()
    admin.approve_run(session, actor, run.id, note=None)

    with pytest.raises(ConflictError, match="already approved"):
        admin.approve_run(session, actor, run.id, note=None)
    with pytest.raises(ConflictError, match="already approved"):
        admin.reject_run(session, actor, run.id, note=None)

    assert session.query(AuditLog).count() == 1


def test_a_failed_run_cannot_be_approved_but_can_be_rejected(session):
    actor = make_admin(session)
    client = make_client(session)
    run = make_run(session, client, created_at=AUG, status="failed", headline_waste=None)
    session.commit()

    with pytest.raises(ConflictError, match="status is failed"):
        admin.approve_run(session, actor, run.id, note=None)

    assert (
        admin.reject_run(session, actor, run.id, note="analysis crashed").review_status
        == "rejected"
    )


def test_reviewing_a_missing_run_raises_not_found(session):
    actor = make_admin(session)
    session.commit()

    with pytest.raises(NotFoundError, match="run 4242 not found"):
        admin.approve_run(session, actor, 4242, note=None)


def test_a_failed_audit_write_rolls_back_the_review_transition(session, monkeypatch):
    """The audit row and the state change share one transaction — if record() blows up,
    review_status must still read 'pending' on the next query, not 'approved'."""
    actor = make_admin(session)
    client = make_client(session)
    run = make_run(session, client, created_at=AUG)
    session.commit()

    def _boom(*args, **kwargs):
        raise RuntimeError("audit backend is down")

    monkeypatch.setattr(admin.audit, "record", _boom)

    with pytest.raises(RuntimeError, match="audit backend is down"):
        admin.approve_run(session, actor, run.id, note="should not stick")

    session.rollback()
    session.expire_all()
    assert admin.get_run(session, run.id).review_status == "pending"


def test_approving_a_run_is_what_makes_the_clients_report_visible(session):
    """Integration proof of the controller decision: a pending run is invisible to
    get_report(); approve_run() ungates it; reject_run() on a sibling run does not."""
    actor = make_admin(session)
    client = make_client(session)
    pending = make_run(
        session, client, created_at=AUG, segments=(("placement", "reels", "1000", True),)
    )
    other_pending = make_run(session, client, upload=None, created_at=SEP)
    session.commit()

    with pytest.raises(NotFoundError):
        get_report(session, client.id, pending.id)

    admin.approve_run(session, actor, pending.id, note="looks right")
    report = get_report(session, client.id, pending.id)
    assert report.run_id == pending.id

    admin.reject_run(session, actor, other_pending.id, note="wrong month")
    with pytest.raises(NotFoundError):
        get_report(session, client.id, other_pending.id)
