from datetime import UTC, datetime

from sqlalchemy import JSON, Numeric
from sqlalchemy.dialects.postgresql import JSONB

# JSONB on Postgres, plain JSON on SQLite (tests).
JSONVariant = JSON().with_variant(JSONB(), "postgresql")

# All PKR amounts. NUMERIC(14,2) per docs/PLAN.md section 1 #6 — never floats.
Money = Numeric(14, 2)


def utcnow() -> datetime:
    return datetime.now(UTC)
