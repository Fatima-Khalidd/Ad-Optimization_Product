"""The audit trail. Every admin state change calls record() inside its own transaction.

Nothing here commits: the caller commits once, so the change and its audit row land
together or not at all (docs/PLAN.md section 6, section 8 "billing disputes").
"""

from collections.abc import Sequence
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditLog


def _jsonable(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime | date):
        return value.isoformat()
    return value


def snapshot(obj: Any, fields: Sequence[str]) -> dict[str, Any]:
    """A JSON-safe before/after picture of the named columns of a model row."""
    return {name: _jsonable(getattr(obj, name)) for name in fields}


def record(
    session: Session,
    actor_user_id: int | None,
    action: str,
    entity_type: str,
    entity_id: int,
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
) -> AuditLog:
    entry = AuditLog(
        actor_user_id=actor_user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        before=before,
        after=after,
    )
    session.add(entry)
    session.flush()  # assign the id; the caller owns the commit
    return entry


def list_entries(
    session: Session,
    limit: int = 200,
    entity_type: str | None = None,
    action: str | None = None,
) -> list[AuditLog]:
    stmt = select(AuditLog)
    if entity_type is not None:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
    if action is not None:
        stmt = stmt.where(AuditLog.action == action)
    stmt = stmt.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(limit)
    return list(session.scalars(stmt))
