# Stage 6 — Admin Panel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The operator-facing half of the product: an audited approval queue that decides which analysis runs clients are allowed to see, per-client fee and threshold editing, invoice drafting with a system-suggested recovered-waste figure the admin confirms, and a dense, animation-free admin UI over all of it.

**Architecture:** Three thin service modules over the Stage 0 models — `services/audit.py` (one `record()` used by everything), `services/admin.py` (clients + run review) and `services/billing.py` (recovered-waste suggestion + invoice lifecycle) — exposed by a single `routers/admin.py` mounted at `/api/admin`, every route gated by `CurrentAdmin`. Services own their transaction: they mutate, `flush()`, write the `AuditLog` row, then `commit()` **once**, so a state change and its audit entry are atomic. The frontend adds an `/admin` segment whose server-side layout re-checks the role, with pages that are plain tables — no hero, no Framer Motion.

**Tech Stack:** Python 3.11, FastAPI 0.141, SQLAlchemy 2.0 (Mapped style), Pydantic 2.13, pytest 9; Next.js 16 App Router, React 19, Tailwind v4, Vitest + Testing Library. No new backend dependency, no new table, no migration.

**Spec:** `docs/PLAN.md` §6 "Stage 6" (authoritative), §5 "API surface" (admin block), §1 #5 (recovered waste), §4 (`audit_log`, `invoices`, `analysis_runs`), §7 decision #2. Cross-stage contract: `docs/superpowers/plans/INTERFACES.md` (Stage 6 section; also Stage 1 `calculate_fee`/`PipelineConfig.from_overrides`, Stage 2 `CurrentAdmin`, Stage 3 runs/reports, Stage 4 `apiFetch`/`formatPKR`).

**Additions to `INTERFACES.md`** (permitted by its "a plan may add to this list and must say so in its header" rule; nothing there is renamed):
- `services/audit.py::list_entries(session, limit=200, entity_type=None, action=None) -> list[AuditLog]` — backs `GET /api/admin/audit-log`, which `docs/PLAN.md` §5 requires but the contract left without a service function.
- `services/audit.py::snapshot(obj, fields) -> dict` — JSON-safe before/after builder, used only by `record()` callers.
- `services/billing.py::list_invoices(session, client_id=None, status=None) -> list[Invoice]` and `GET /api/admin/invoices` — the admin invoices page needs a list; `docs/PLAN.md` §5 names only the POST verbs. (Stage 7's `services/payments.py::list_invoices(session, client_id)` is a different module and is unaffected.)
- `app/core/errors.py` with `AppError`/`NotFoundError`/`ConflictError`/`InvalidConfigError` (`docs/PLAN.md` §2 already lists `core/errors`). Create only what is missing if Stage 3 already added the module.

## Global Constraints

- **Stages 2–4 are complete before this stage starts.** This plan consumes `app.core.deps.CurrentAdmin` / `require_admin` (Stage 2), `app.services.analysis.get_report` and the `/api/reports/*` routes (Stage 3), and the frontend's `apiFetch` / `formatPKR` / design tokens / Vitest setup (Stage 4). It renames none of them.
- **Every approve, reject, confirm, issue, void and client update writes an `AuditLog` row through `audit.record()` in the SAME transaction as the change** (`docs/PLAN.md` §6 "Done when", §8 risk mitigation). Concretely: mutate → `session.flush()` → `audit.record(...)` → **one** `session.commit()`. A service must never commit the change and the audit row separately.
- **Clients see a run only after approval** (`docs/PLAN.md` §4 "Tenant isolation"). Stage 3 enforces it in `get_report`; Stage 6 supplies the state transition and must prove it end to end.
- **Money is `Decimal`, never float** (`docs/PLAN.md` §1 #6). Amounts are quantized to 2 places with `ROUND_HALF_UP`. Fee arithmetic goes through `app.pipeline.optimizer.calculate_fee` — this stage never re-implements it.
- **Recovered waste** = waste on previously flagged segments in the baseline period minus waste on those same segments in the current period; the system only ever *suggests*, the admin confirms (`docs/PLAN.md` §1 #5, §7 #2).
- **Headline waste is the largest single-dimension total, never a sum** (`docs/PLAN.md` §1 #1). The admin run view shows each dimension separately and reuses the stored `AnalysisRun.headline_waste`; it never adds dimensions together.
- Every route in `routers/admin.py` depends on `CurrentAdmin`; a logged-in client gets **403** on all of them, and that is tested per route.
- Invoice numbers are `INV-{YYYY}-{NNNN}`, unique (`docs/PLAN.md` §4 `invoices`).
- Payments, payment methods and issuing-to-client flows are **Stage 7**. Stage 6 stops at draft → confirm → issue/void plus the admin UI.
- SQLAlchemy 2.0 `Mapped[...]` style; ruff `line-length = 100`, lint select `E,F,I,B,UP`.
- Windows Git Bash: backend commands run as `backend/.venv/Scripts/python -m ...`, `backend/.venv/Scripts/ruff ...`.
- Every commit passes the trailer as a second `-m`: `-m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"`.
- **No Alembic migration in this stage.** `audit_log` and `invoices` already exist from Stage 0's `55eb15843c97_initial_schema`; no model gains or loses a column. Task 11 asserts `alembic check` reports no new operations.
- Admin UI is dense tables with hairline dividers, no hero, no Framer Motion, no Three.js, no transitions.

---

## File Structure

```
backend/
├── app/
│   ├── core/errors.py                    # AppError + NotFoundError/ConflictError/InvalidConfigError  (create if absent)
│   ├── main.py                           # MODIFY: include admin router + AppError handler
│   ├── schemas/admin.py                  # NEW: admin request/response models
│   ├── services/
│   │   ├── audit.py                      # NEW: record(), snapshot(), list_entries()
│   │   ├── admin.py                      # NEW: clients + run review queue
│   │   └── billing.py                    # NEW: recovered waste + invoice lifecycle
│   └── routers/admin.py                  # NEW: /api/admin/*
└── tests/
    ├── conftest.py                       # UNCHANGED: bound_engine / session / client (Stage 2)
    ├── api/conftest.py                   # UNCHANGED: api / db / admin_client (Stages 2-3)
    ├── api/helpers.py                    # UNCHANGED: make_admin/make_client/make_run/login_as
    ├── services/
    │   ├── test_audit.py
    │   ├── test_admin_clients.py
    │   ├── test_admin_runs.py
    │   ├── test_billing_recovered_waste.py
    │   └── test_billing_invoices.py
    └── api/
        ├── test_admin_permissions.py     # 403 for clients, parametrized over every route
        └── test_admin_api.py             # integration: approve/reject/report visibility, invoices, audit

frontend/src/
├── app/admin/
│   ├── layout.tsx                        # server guard + nav
│   ├── page.tsx                          # redirect to /admin/runs
│   ├── clients/page.tsx
│   ├── clients/[id]/page.tsx
│   ├── runs/page.tsx
│   ├── invoices/page.tsx
│   └── audit/page.tsx
├── components/admin/
│   ├── Table.tsx                         # Table/Th/Td primitives (hairline dividers)
│   ├── RunQueueRow.tsx  + RunQueueRow.test.tsx
│   ├── ClientEditForm.tsx
│   └── InvoiceForm.tsx  + InvoiceForm.test.tsx
└── lib/admin-types.ts                    # TS mirrors of the admin schemas
```

Responsibility split: `audit.py` knows nothing about what it is auditing; `admin.py` never touches invoices; `billing.py` never touches runs except read-only for the waste comparison; the router does no business logic beyond mapping query params and serializing.

---

### Task 1: Audit trail (`services/audit.py`) and test scaffolding

**Files:**
- Create: `backend/app/core/errors.py` (if Stage 3 already created it, add only the missing classes)
- Create: `backend/app/services/audit.py`
- Create: `backend/app/services/__init__.py` (if absent; empty file)
- Create: `backend/tests/services/__init__.py` (empty, if absent; `backend/tests/api/__init__.py` came with Stage 2)
- Verify only: `backend/tests/api/helpers.py` and `backend/tests/api/conftest.py` (Stages 2-3 built every builder and fixture this stage needs — see Step 5)
- Modify: `backend/app/main.py` (register the `AppError` handler)
- Test: `backend/tests/services/test_audit.py`

**Interfaces:**
- Consumes: `app.models.AuditLog`, `app.core.db.get_session`, `app.core.security.create_access_token` (Stage 2).
- Produces:
  ```python
  # app/core/errors.py
  class AppError(Exception): status_code: int = 400; detail: str
  class NotFoundError(AppError): status_code = 404
  class ConflictError(AppError): status_code = 409
  class InvalidConfigError(AppError): status_code = 422

  # app/services/audit.py
  record(session: Session, actor_user_id: int | None, action: str, entity_type: str,
         entity_id: int, before: dict | None, after: dict | None) -> AuditLog   # flush, never commit
  snapshot(obj: Any, fields: Sequence[str]) -> dict[str, Any]                   # JSON-safe
  list_entries(session, limit: int = 200, entity_type: str | None = None,
               action: str | None = None) -> list[AuditLog]                     # newest first

  # No test module is created by this stage. Everything it needs already exists in
  # tests/api/helpers.py and tests/api/conftest.py (INTERFACES.md "Test-fixture contract"):
  #   login_as(api: TestClient, user: User) -> None
  #   user_for(db: Session, client: Client) -> User
  #   make_admin(db, email="admin@example.com") -> User
  #   make_client(db, email="client@example.com", business_name="Biz", *, base_fee=...,
  #               performance_fee_pct=..., config_overrides=None) -> Client
  #   make_upload(db, client, *, status="validated") -> AdDataUpload
  #   make_run(db, client, upload=None, *, status, review_status, created_at,
  #            headline_waste, segments=()) -> AnalysisRun
  #   fixtures: db, api, admin_client, admin_row, client_a, client_b, client_a_row
  ```
  The service tests in this stage keep using the Stage 0 `session` fixture (which rides on
  `bound_engine`) and pass it as the builders' first argument; the API tests use `db`.

- [ ] **Step 1: Write the failing test**

`backend/tests/services/__init__.py` and `backend/tests/api/__init__.py`: empty files.

`backend/tests/services/test_audit.py`:
```python
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

    audit.record(session, admin.id, "run.approve", "analysis_run", 1, None, {"review_status": "approved"})
    session.rollback()

    assert session.query(AuditLog).count() == 0


def test_snapshot_is_json_safe(session):
    import json

    client = make_client(session)
    client.config_overrides = {"waste_multiplier": 2.0}
    session.flush()

    data = audit.snapshot(client, ("base_fee", "performance_fee_pct", "config_overrides", "created_at"))

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

    assert [e.action for e in audit.list_entries(session, action="client.update")] == ["client.update"]
    assert len(audit.list_entries(session, limit=1)) == 1


def test_decimal_amounts_survive_a_snapshot_round_trip(session):
    client = make_client(session, base_fee=Decimal("12345.67"))
    session.flush()

    data = audit.snapshot(client, ("base_fee",))

    assert data["base_fee"] == "12345.67"  # a string, so JSONB never sees a float
    assert Decimal(data["base_fee"]) == Decimal("12345.67")
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd backend && .venv/Scripts/python -m pytest tests/services/test_audit.py -v`
Expected: FAIL with `ImportError: cannot import name 'audit' from 'app.services'` — the builders in `tests/api/helpers.py` import fine; only the module under test is missing.

- [ ] **Step 3: Write the error types**

`backend/app/core/errors.py` (if the file already exists from Stage 3, add only the classes it is missing — do not change existing ones):
```python
"""Service-layer errors. The API layer turns these into HTTP responses in create_app()."""


class AppError(Exception):
    """Base for errors that map straight onto an HTTP status."""

    status_code: int = 400

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class NotFoundError(AppError):
    status_code = 404


class ConflictError(AppError):
    """The row exists but is in the wrong state for this transition."""

    status_code = 409


class InvalidConfigError(AppError):
    """A config_overrides payload PipelineConfig refuses."""

    status_code = 422
```

- [ ] **Step 4: Write `services/audit.py`**

`backend/app/services/__init__.py`: empty file (skip if it exists).

`backend/app/services/audit.py`:
```python
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
```

Note on ordering: rows written inside one request share a `created_at` to the microsecond on some platforms, so `id DESC` is the tiebreaker — without it `test_list_entries_is_newest_first_and_filterable` is flaky.

- [ ] **Step 5: Confirm the shared builders already cover this stage**

This stage writes **no** test-helper code. `INTERFACES.md` §"Test-fixture contract" puts every
row builder in `backend/tests/api/helpers.py`, and Stages 2, 3 and 5 filled it: `TEST_PASSWORD`,
`login_as`, `user_for`, `make_client`, `make_admin` (Stage 2), `make_upload`, `make_run`
(Stage 3), `make_approved_run` (Stage 5). `make_client` already takes `base_fee`,
`performance_fee_pct` and `config_overrides` keyword arguments and `make_run` already takes
`created_at`, `headline_waste` and `segments`, which is everything this stage's tests pass.
**Do not create a local factories module and do not add a second `api` fixture** — `api`, `db`,
`admin_client` and `admin_row` come from `backend/tests/api/conftest.py`.

Run: `cd backend && grep -nE '^def (login_as|user_for|make_client|make_admin|make_upload|make_run|make_approved_run)\(' tests/api/helpers.py`
Expected: seven lines, one per builder. If any is missing, the corresponding earlier stage is
not merged — stop and merge it rather than writing a local copy.

- [ ] **Step 6: Register the error handler**

In `backend/app/main.py`, inside `create_app()` before `return application` (skip if Stage 3 already registered an identical handler):
```python
    from fastapi import Request
    from fastapi.responses import JSONResponse

    from app.core.errors import AppError

    @application.exception_handler(AppError)
    async def _app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `cd backend && .venv/Scripts/python -m pytest tests/services/test_audit.py -v`
Expected: `5 passed`

- [ ] **Step 8: Lint and commit**

Run: `cd backend && .venv/Scripts/ruff check . && .venv/Scripts/ruff format .`
```bash
git add backend/app/core/errors.py backend/app/services backend/app/main.py backend/tests
git commit -m "feat(admin): audit trail service and admin test scaffolding" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 2: `services/admin.py` — client list, detail and fee/override editing

**Files:**
- Create: `backend/app/schemas/admin.py` (the `ClientPatch` half; the rest arrives in Task 6)
- Create: `backend/app/services/admin.py`
- Test: `backend/tests/services/test_admin_clients.py`

**Interfaces:**
- Consumes: `audit.record`, `audit.snapshot`, `NotFoundError`, `InvalidConfigError`, `app.pipeline.config.PipelineConfig.from_overrides` (Stage 1), `app.models.Client`, `app.models.User`.
- Produces:
  ```python
  # app/schemas/admin.py
  class ClientPatch(BaseModel):          # extra="forbid"
      base_fee: Decimal | None            # ge=0
      performance_fee_pct: Decimal | None  # ge=0, le=100
      config_overrides: dict[str, Any] | None

  # app/services/admin.py
  CLIENT_AUDIT_FIELDS = ("base_fee", "performance_fee_pct", "config_overrides")
  list_clients(session) -> list[Client]                       # ordered by business_name
  get_client(session, client_id: int) -> Client               # NotFoundError
  update_client(session, actor: User, client_id: int, patch: ClientPatch) -> Client
  ```

- [ ] **Step 1: Write the failing test**

`backend/tests/services/test_admin_clients.py`:
```python
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

    assert [c.business_name for c in admin.list_clients(session)] == ["Alpha Motors", "Zephyr Foods"]


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
        admin.update_client(session, actor, client.id, ClientPatch(config_overrides={"typo_key": 1}))

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
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd backend && .venv/Scripts/python -m pytest tests/services/test_admin_clients.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.schemas.admin'`

- [ ] **Step 3: Write the schema**

`backend/app/schemas/__init__.py`: empty file (skip if it exists).

`backend/app/schemas/admin.py`:
```python
"""Request and response models for /api/admin. Decimals serialize as JSON strings."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ClientPatch(BaseModel):
    """A partial client update. Only the fields actually sent are applied."""

    model_config = ConfigDict(extra="forbid")

    base_fee: Decimal | None = Field(default=None, ge=0)
    performance_fee_pct: Decimal | None = Field(default=None, ge=0, le=100)
    config_overrides: dict[str, Any] | None = None
```

- [ ] **Step 4: Write `services/admin.py`**

`backend/app/services/admin.py`:
```python
"""Admin operations on clients and analysis runs. Every mutation is audited."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import InvalidConfigError, NotFoundError
from app.models import Client, User
from app.pipeline.config import PipelineConfig
from app.schemas.admin import ClientPatch
from app.services import audit

CLIENT_AUDIT_FIELDS = ("base_fee", "performance_fee_pct", "config_overrides")


def list_clients(session: Session) -> list[Client]:
    return list(session.scalars(select(Client).order_by(Client.business_name)))


def get_client(session: Session, client_id: int) -> Client:
    client = session.get(Client, client_id)
    if client is None:
        raise NotFoundError(f"client {client_id} not found")
    return client


def update_client(session: Session, actor: User, client_id: int, patch: ClientPatch) -> Client:
    client = get_client(session, client_id)
    # `exclude_unset` keeps a PATCH partial; an explicit null is dropped because every
    # one of these columns is NOT NULL (docs/PLAN.md section 4).
    data = {k: v for k, v in patch.model_dump(exclude_unset=True).items() if v is not None}

    if "config_overrides" in data:
        try:
            PipelineConfig.from_overrides(data["config_overrides"])
        except (ValueError, TypeError, ArithmeticError) as exc:
            raise InvalidConfigError(str(exc)) from exc

    before = audit.snapshot(client, CLIENT_AUDIT_FIELDS)
    for field, value in data.items():
        setattr(client, field, value)
    session.flush()
    audit.record(
        session,
        actor.id,
        "client.update",
        "client",
        client.id,
        before,
        audit.snapshot(client, CLIENT_AUDIT_FIELDS),
    )
    session.commit()
    return client
```

Why validation runs before the snapshot: `PipelineConfig.from_overrides` is the single source of truth for which keys exist (Stage 1), and raising before any `setattr` keeps the failed request from leaving a half-applied row in the identity map.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd backend && .venv/Scripts/python -m pytest tests/services/test_admin_clients.py -v`
Expected: `8 passed`

- [ ] **Step 6: Lint and commit**

Run: `cd backend && .venv/Scripts/ruff check . && .venv/Scripts/ruff format .`
```bash
git add backend/app/schemas backend/app/services/admin.py backend/tests/services/test_admin_clients.py
git commit -m "feat(admin): client list, detail and audited fee/override editing" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 3: `services/admin.py` — the run approval queue

**Files:**
- Modify: `backend/app/services/admin.py`
- Test: `backend/tests/services/test_admin_runs.py`

**Interfaces:**
- Consumes: `app.models.AnalysisRun`, `audit.record`, `audit.snapshot`, `NotFoundError`, `ConflictError`.
- Produces:
  ```python
  RUN_AUDIT_FIELDS = ("status", "review_status", "reviewed_by", "reviewed_at", "review_note")
  list_runs(session, review_status: str | None = None) -> list[AnalysisRun]   # newest first
  approve_run(session, actor: User, run_id: int, note: str | None = None) -> AnalysisRun
  reject_run(session, actor: User, run_id: int, note: str | None = None) -> AnalysisRun
  ```
  Both transitions require `review_status == "pending"` (409 otherwise). `approve_run` additionally
  requires `status == "done"` — an unfinished or failed run has no report to show.

- [ ] **Step 1: Write the failing test**

`backend/tests/services/test_admin_runs.py`:
```python
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.core.errors import ConflictError, NotFoundError
from app.models import AuditLog
from app.services import admin
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

    assert admin.reject_run(session, actor, run.id, note="analysis crashed").review_status == "rejected"


def test_reviewing_a_missing_run_raises_not_found(session):
    actor = make_admin(session)
    session.commit()

    with pytest.raises(NotFoundError, match="run 4242 not found"):
        admin.approve_run(session, actor, 4242, note=None)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd backend && .venv/Scripts/python -m pytest tests/services/test_admin_runs.py -v`
Expected: FAIL with `AttributeError: module 'app.services.admin' has no attribute 'list_runs'`

- [ ] **Step 3: Extend `services/admin.py`**

Add to the imports at the top of `backend/app/services/admin.py`:
```python
from datetime import UTC, datetime

from app.core.errors import ConflictError, InvalidConfigError, NotFoundError
from app.models import AnalysisRun, Client, User
```

Append to `backend/app/services/admin.py`:
```python
RUN_AUDIT_FIELDS = ("status", "review_status", "reviewed_by", "reviewed_at", "review_note")


def list_runs(session: Session, review_status: str | None = None) -> list[AnalysisRun]:
    stmt = select(AnalysisRun)
    if review_status is not None:
        stmt = stmt.where(AnalysisRun.review_status == review_status)
    stmt = stmt.order_by(AnalysisRun.created_at.desc(), AnalysisRun.id.desc())
    return list(session.scalars(stmt))


def get_run(session: Session, run_id: int) -> AnalysisRun:
    run = session.get(AnalysisRun, run_id)
    if run is None:
        raise NotFoundError(f"run {run_id} not found")
    return run


def _review_run(
    session: Session, actor: User, run_id: int, new_status: str, note: str | None
) -> AnalysisRun:
    run = get_run(session, run_id)
    if run.review_status != "pending":
        raise ConflictError(f"run {run_id} is already {run.review_status}")
    if new_status == "approved" and run.status != "done":
        # Approving unlocks the report for the client; there is nothing to unlock yet.
        raise ConflictError(f"run {run_id} status is {run.status}, not done")

    before = audit.snapshot(run, RUN_AUDIT_FIELDS)
    run.review_status = new_status
    run.reviewed_by = actor.id
    run.reviewed_at = datetime.now(UTC)
    run.review_note = note
    session.flush()
    action = "run.approve" if new_status == "approved" else "run.reject"
    audit.record(
        session, actor.id, action, "analysis_run", run.id, before, audit.snapshot(run, RUN_AUDIT_FIELDS)
    )
    session.commit()
    return run


def approve_run(session: Session, actor: User, run_id: int, note: str | None = None) -> AnalysisRun:
    return _review_run(session, actor, run_id, "approved", note)


def reject_run(session: Session, actor: User, run_id: int, note: str | None = None) -> AnalysisRun:
    return _review_run(session, actor, run_id, "rejected", note)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && .venv/Scripts/python -m pytest tests/services/test_admin_runs.py -v`
Expected: `6 passed`

- [ ] **Step 5: Lint and commit**

Run: `cd backend && .venv/Scripts/ruff check . && .venv/Scripts/ruff format .`
```bash
git add backend/app/services/admin.py backend/tests/services/test_admin_runs.py
git commit -m "feat(admin): audited approve/reject queue for analysis runs" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 4: `services/billing.py` — `suggest_recovered_waste`

**Files:**
- Create: `backend/app/services/billing.py`
- Test: `backend/tests/services/test_billing_recovered_waste.py`

**Interfaces:**
- Consumes: `app.models.AnalysisRun`, `WasteReport`, `SegmentMetric`.
- Produces:
  ```python
  TWO_PLACES = Decimal("0.01")
  suggest_recovered_waste(session, client_id: int, period_start: date, period_end: date) -> Decimal
  ```
  Exactly the `INTERFACES.md` definition: sum, over the segments **flagged in the latest approved
  run before `period_start`**, of `max(0, waste_then − waste_now)`, where `waste_now` comes from the
  **latest approved run inside `[period_start, period_end]`**; `Decimal("0.00")` if either run is
  missing. A segment key is `(dimension, segment_value)`; a segment absent from the current run
  contributes `waste_now = 0`.

- [ ] **Step 1: Write the failing test**

`backend/tests/services/test_billing_recovered_waste.py`:
```python
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
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd backend && .venv/Scripts/python -m pytest tests/services/test_billing_recovered_waste.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.billing'`

- [ ] **Step 3: Write `services/billing.py`**

`backend/app/services/billing.py`:
```python
"""Invoice drafting and the performance fee.

"Recovered waste" is the before/after comparison from docs/PLAN.md section 1 #5 and
section 7 #2: the system only ever *suggests* a number and the admin confirms it.
Every amount here is a Decimal quantized to 2 places; nothing is ever a float.
"""

from datetime import UTC, date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AnalysisRun, SegmentMetric, WasteReport

TWO_PLACES = Decimal("0.01")

SegmentKey = tuple[str, str]  # (dimension, segment_value)


def _money(value: Decimal | int | float | str | None) -> Decimal:
    return Decimal(str(value or 0)).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def _midnight(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=UTC)


def _latest_approved_run(
    session: Session,
    client_id: int,
    *,
    before: datetime | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
) -> AnalysisRun | None:
    stmt = select(AnalysisRun).where(
        AnalysisRun.client_id == client_id,
        AnalysisRun.review_status == "approved",
        AnalysisRun.status == "done",
    )
    if before is not None:
        stmt = stmt.where(AnalysisRun.created_at < before)
    if start is not None:
        stmt = stmt.where(AnalysisRun.created_at >= start)
    if end is not None:
        stmt = stmt.where(AnalysisRun.created_at < end)
    stmt = stmt.order_by(AnalysisRun.created_at.desc(), AnalysisRun.id.desc()).limit(1)
    return session.scalars(stmt).first()


def _waste_by_segment(session: Session, run_id: int) -> dict[SegmentKey, tuple[bool, Decimal]]:
    """(dimension, segment_value) -> (is_flagged, wasted_spend) for one run."""
    rows = session.execute(
        select(
            WasteReport.dimension,
            SegmentMetric.segment_value,
            SegmentMetric.is_flagged,
            SegmentMetric.wasted_spend,
        )
        .join(SegmentMetric, SegmentMetric.report_id == WasteReport.id)
        .where(WasteReport.run_id == run_id)
    ).all()
    return {(dimension, segment): (bool(flagged), _money(waste)) for dimension, segment, flagged, waste in rows}


def suggest_recovered_waste(
    session: Session, client_id: int, period_start: date, period_end: date
) -> Decimal:
    baseline = _latest_approved_run(session, client_id, before=_midnight(period_start))
    current = _latest_approved_run(
        session,
        client_id,
        start=_midnight(period_start),
        end=_midnight(period_end + timedelta(days=1)),  # period_end is inclusive
    )
    if baseline is None or current is None:
        return Decimal("0.00")

    waste_then = _waste_by_segment(session, baseline.id)
    waste_now = _waste_by_segment(session, current.id)

    total = Decimal("0")
    for key, (flagged, then) in waste_then.items():
        if not flagged:
            continue
        # A segment missing from the current run wastes nothing now. An unflagged segment
        # already carries wasted_spend = 0 (Stage 1 only assigns waste to flagged segments).
        now = waste_now.get(key, (False, Decimal("0")))[1]
        if then > now:
            total += then - now
    return total.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && .venv/Scripts/python -m pytest tests/services/test_billing_recovered_waste.py -v`
Expected: `9 passed`

- [ ] **Step 5: Lint and commit**

Run: `cd backend && .venv/Scripts/ruff check . && .venv/Scripts/ruff format .`
```bash
git add backend/app/services/billing.py backend/tests/services/test_billing_recovered_waste.py
git commit -m "feat(billing): suggested recovered waste from the before/after comparison" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 5: `services/billing.py` — invoice draft, confirm, issue, void

**Files:**
- Modify: `backend/app/services/billing.py`
- Test: `backend/tests/services/test_billing_invoices.py`

**Interfaces:**
- Consumes: `suggest_recovered_waste` (Task 4), `admin.get_client` (Task 2), `audit.record`/`snapshot` (Task 1), `app.pipeline.optimizer.calculate_fee` and `app.pipeline.config.PipelineConfig` (Stage 1), `app.models.Invoice`.
- Produces:
  ```python
  INVOICE_AUDIT_FIELDS = ("invoice_number", "status", "base_fee", "suggested_recovered_waste",
                          "confirmed_recovered_waste", "performance_fee", "total", "due_date",
                          "issued_at", "confirmed_by")
  DEFAULT_DUE_DAYS = 14
  get_invoice(session, invoice_id: int) -> Invoice                                    # NotFoundError
  list_invoices(session, client_id: int | None = None, status: str | None = None) -> list[Invoice]
  draft_invoice(session, actor: User, client_id: int, period_start: date, period_end: date) -> Invoice
  confirm_invoice(session, actor: User, invoice_id: int, confirmed_recovered_waste: Decimal) -> Invoice
  issue_invoice(session, actor: User, invoice_id: int, due_date: date) -> Invoice
  void_invoice(session, actor: User, invoice_id: int, note: str | None = None) -> Invoice
  ```

- [ ] **Step 1: Write the failing test**

`backend/tests/services/test_billing_invoices.py`:
```python
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from app.core.errors import ConflictError, NotFoundError
from app.models import AuditLog
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
    client = _client_with_23k_recovered(
        session, config_overrides={"performance_fee_cap": "3000"}
    )
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
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd backend && .venv/Scripts/python -m pytest tests/services/test_billing_invoices.py -v`
Expected: FAIL with `AttributeError: module 'app.services.billing' has no attribute 'draft_invoice'`

- [ ] **Step 3: Extend `services/billing.py`**

Replace the import block at the top of `backend/app/services/billing.py` with:
```python
from datetime import UTC, date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError
from app.models import AnalysisRun, Client, Invoice, SegmentMetric, User, WasteReport
from app.pipeline.config import PipelineConfig
from app.pipeline.optimizer import calculate_fee
from app.services import audit
from app.services.admin import get_client
```

Append to `backend/app/services/billing.py`:
```python
DEFAULT_DUE_DAYS = 14

INVOICE_AUDIT_FIELDS = (
    "invoice_number",
    "status",
    "base_fee",
    "suggested_recovered_waste",
    "confirmed_recovered_waste",
    "performance_fee",
    "total",
    "due_date",
    "issued_at",
    "confirmed_by",
)


def get_invoice(session: Session, invoice_id: int) -> Invoice:
    invoice = session.get(Invoice, invoice_id)
    if invoice is None:
        raise NotFoundError(f"invoice {invoice_id} not found")
    return invoice


def list_invoices(
    session: Session, client_id: int | None = None, status: str | None = None
) -> list[Invoice]:
    stmt = select(Invoice)
    if client_id is not None:
        stmt = stmt.where(Invoice.client_id == client_id)
    if status is not None:
        stmt = stmt.where(Invoice.status == status)
    stmt = stmt.order_by(Invoice.created_at.desc(), Invoice.id.desc())
    return list(session.scalars(stmt))


def _fee_cap(client: Client) -> Decimal | None:
    return PipelineConfig.from_overrides(client.config_overrides or {}).performance_fee_cap


def _next_invoice_number(session: Session, year: int) -> str:
    """Highest existing number for the year, plus one.

    Suffixes are zero-padded to 4 digits, so MAX() on the text column is the numeric
    maximum. RACE: two admins drafting in the same instant can both read this MAX and
    build the same number. There is no SELECT ... FOR UPDATE on SQLite and the MVP has a
    single admin, so we lean on the UNIQUE constraint on invoices.invoice_number: the
    loser gets an IntegrityError and simply drafts again. Revisit if a second operator
    is ever hired (docs/PLAN.md section 4).
    """
    prefix = f"INV-{year}-"
    highest = session.scalar(
        select(func.max(Invoice.invoice_number)).where(Invoice.invoice_number.like(f"{prefix}%"))
    )
    nxt = 1 if highest is None else int(highest.rsplit("-", 1)[1]) + 1
    return f"{prefix}{nxt:04d}"


def draft_invoice(
    session: Session, actor: User, client_id: int, period_start: date, period_end: date
) -> Invoice:
    if period_end < period_start:
        raise ConflictError("period_end is before period_start")
    client = get_client(session, client_id)

    existing = session.scalars(
        select(Invoice).where(
            Invoice.client_id == client_id,
            Invoice.period_start == period_start,
            Invoice.period_end == period_end,
            Invoice.status != "void",
        )
    ).first()
    if existing is not None:
        raise ConflictError(
            f"invoice {existing.invoice_number} already covers {period_start} to {period_end}"
        )

    suggested = suggest_recovered_waste(session, client_id, period_start, period_end)
    # The draft shows what the bill would be if the admin accepts the suggestion; the
    # confirmed figure stays 0 until a human confirms it (docs/PLAN.md section 1 #5).
    fee = calculate_fee(
        _money(client.base_fee), Decimal(client.performance_fee_pct), suggested, cap=_fee_cap(client)
    )
    invoice = Invoice(
        invoice_number=_next_invoice_number(session, period_end.year),
        client_id=client.id,
        period_start=period_start,
        period_end=period_end,
        due_date=period_end + timedelta(days=DEFAULT_DUE_DAYS),  # issue_invoice() overwrites it
        base_fee=fee.base_fee,
        suggested_recovered_waste=suggested,
        confirmed_recovered_waste=Decimal("0.00"),
        performance_fee=fee.performance_fee,
        total=fee.total,
        amount_paid=Decimal("0.00"),
        status="draft",
    )
    session.add(invoice)
    session.flush()
    audit.record(
        session,
        actor.id,
        "invoice.draft",
        "invoice",
        invoice.id,
        None,
        audit.snapshot(invoice, INVOICE_AUDIT_FIELDS),
    )
    session.commit()
    return invoice


def confirm_invoice(
    session: Session, actor: User, invoice_id: int, confirmed_recovered_waste: Decimal
) -> Invoice:
    invoice = get_invoice(session, invoice_id)
    if invoice.status != "draft":
        raise ConflictError(f"invoice {invoice.invoice_number} is {invoice.status}, not draft")
    if confirmed_recovered_waste < 0:
        raise ConflictError("confirmed_recovered_waste must be >= 0")

    client = get_client(session, invoice.client_id)
    before = audit.snapshot(invoice, INVOICE_AUDIT_FIELDS)
    fee = calculate_fee(
        _money(client.base_fee),
        Decimal(client.performance_fee_pct),
        _money(confirmed_recovered_waste),
        cap=_fee_cap(client),
    )
    invoice.base_fee = fee.base_fee
    invoice.confirmed_recovered_waste = fee.recovered_waste
    invoice.performance_fee = fee.performance_fee
    invoice.total = fee.total
    invoice.confirmed_by = actor.id
    session.flush()
    audit.record(
        session,
        actor.id,
        "invoice.confirm",
        "invoice",
        invoice.id,
        before,
        audit.snapshot(invoice, INVOICE_AUDIT_FIELDS),
    )
    session.commit()
    return invoice


def issue_invoice(session: Session, actor: User, invoice_id: int, due_date: date) -> Invoice:
    invoice = get_invoice(session, invoice_id)
    if invoice.status != "draft":
        raise ConflictError(f"invoice {invoice.invoice_number} is {invoice.status}, not draft")
    if invoice.confirmed_by is None:
        raise ConflictError("confirm the performance fee before issuing")

    before = audit.snapshot(invoice, INVOICE_AUDIT_FIELDS)
    invoice.status = "issued"
    invoice.issued_at = datetime.now(UTC)
    invoice.due_date = due_date
    session.flush()
    audit.record(
        session,
        actor.id,
        "invoice.issue",
        "invoice",
        invoice.id,
        before,
        audit.snapshot(invoice, INVOICE_AUDIT_FIELDS),
    )
    session.commit()
    return invoice


def void_invoice(session: Session, actor: User, invoice_id: int, note: str | None = None) -> Invoice:
    invoice = get_invoice(session, invoice_id)
    if invoice.status in ("paid", "void"):
        raise ConflictError(f"invoice {invoice.invoice_number} is {invoice.status}")

    before = audit.snapshot(invoice, INVOICE_AUDIT_FIELDS)
    invoice.status = "void"
    session.flush()
    after = audit.snapshot(invoice, INVOICE_AUDIT_FIELDS)
    after["note"] = note  # audit_log has no note column; the reason rides in `after`
    audit.record(session, actor.id, "invoice.void", "invoice", invoice.id, before, after)
    session.commit()
    return invoice
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && .venv/Scripts/python -m pytest tests/services/test_billing_invoices.py -v`
Expected: `12 passed`

- [ ] **Step 5: Run every service test together**

Run: `cd backend && .venv/Scripts/python -m pytest tests/services -v`
Expected: `40 passed`

- [ ] **Step 6: Lint and commit**

Run: `cd backend && .venv/Scripts/ruff check . && .venv/Scripts/ruff format .`
```bash
git add backend/app/services/billing.py backend/tests/services/test_billing_invoices.py
git commit -m "feat(billing): invoice draft, confirm, issue and void with audit entries" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 6: Admin schemas, router and the 403 wall

**Files:**
- Modify: `backend/app/schemas/admin.py`
- Modify: `backend/app/services/admin.py` (add `serialize_run`)
- Create: `backend/app/routers/admin.py`
- Modify: `backend/app/main.py` (include the router)
- Test: `backend/tests/api/test_admin_permissions.py`

**Interfaces:**
- Consumes: `CurrentAdmin` (Stage 2), `get_session` (Stage 0), all of Tasks 1–5.
- Produces:
  ```python
  # app/schemas/admin.py (added to ClientPatch)
  AdminClientOut, RunDimensionOut, FlaggedSegmentOut, RunAdminOut, ReviewIn,
  InvoiceDraftIn, ConfirmInvoiceIn, IssueInvoiceIn, VoidInvoiceIn, AdminInvoiceOut, AuditLogOut
  # app/services/admin.py
  serialize_run(session, run: AnalysisRun) -> RunAdminOut
  # app/routers/admin.py
  router = APIRouter(prefix="/api/admin", tags=["admin"])
  GET    /api/admin/clients                  -> list[AdminClientOut]
  GET    /api/admin/clients/{client_id}      -> AdminClientOut
  PATCH  /api/admin/clients/{client_id}      -> AdminClientOut       (422 on a bad override key)
  GET    /api/admin/runs?review_status=      -> list[RunAdminOut]
  POST   /api/admin/runs/{run_id}/approve    -> RunAdminOut          (409 unless pending+done)
  POST   /api/admin/runs/{run_id}/reject     -> RunAdminOut
  GET    /api/admin/invoices?client_id=&status= -> list[AdminInvoiceOut]
  POST   /api/admin/invoices                 -> 201 AdminInvoiceOut
  POST   /api/admin/invoices/{id}/confirm    -> AdminInvoiceOut
  POST   /api/admin/invoices/{id}/issue      -> AdminInvoiceOut
  POST   /api/admin/invoices/{id}/void       -> AdminInvoiceOut
  GET    /api/admin/audit-log?limit=&entity_type=&action= -> list[AuditLogOut]
  ```

- [ ] **Step 1: Write the failing test**

`backend/tests/api/test_admin_permissions.py`:
```python
"""Every /api/admin route must be admin-only (docs/PLAN.md section 5, Stage 2 "Done when")."""

import pytest

from tests.api.helpers import login_as, make_admin, make_client, user_for

ROUTES = [
    ("GET", "/api/admin/clients", None),
    ("GET", "/api/admin/clients/1", None),
    ("PATCH", "/api/admin/clients/1", {"base_fee": "20000"}),
    ("GET", "/api/admin/runs", None),
    ("POST", "/api/admin/runs/1/approve", {"note": "ok"}),
    ("POST", "/api/admin/runs/1/reject", {"note": "no"}),
    ("GET", "/api/admin/invoices", None),
    ("POST", "/api/admin/invoices", {"client_id": 1, "period_start": "2026-08-01", "period_end": "2026-08-31"}),
    ("POST", "/api/admin/invoices/1/confirm", {"confirmed_recovered_waste": "23000"}),
    ("POST", "/api/admin/invoices/1/issue", {"due_date": "2026-09-20"}),
    ("POST", "/api/admin/invoices/1/void", {"note": "wrong month"}),
    ("GET", "/api/admin/audit-log", None),
]


@pytest.mark.parametrize(("method", "path", "body"), ROUTES)
def test_a_logged_in_client_gets_403(api, db, method, path, body):
    client = make_client(db)
    db.commit()
    login_as(api, user_for(db, client))

    response = api.request(method, path, json=body)

    assert response.status_code == 403, response.text


@pytest.mark.parametrize(("method", "path", "body"), ROUTES)
def test_an_anonymous_caller_gets_401(api, db, method, path, body):
    response = api.request(method, path, json=body)
    assert response.status_code == 401, response.text


def test_an_admin_gets_past_the_guard(api, db):
    admin = make_admin(db)
    db.commit()
    login_as(api, admin)

    assert api.get("/api/admin/clients").status_code == 200
    assert api.get("/api/admin/audit-log").status_code == 200
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd backend && .venv/Scripts/python -m pytest tests/api/test_admin_permissions.py -v`
Expected: FAIL — every parametrized case returns `404` because `/api/admin/*` is not mounted yet.

- [ ] **Step 3: Finish the schemas**

Append to `backend/app/schemas/admin.py`:
```python
class AdminClientOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    business_name: str
    contact_info: str | None = None
    pricing_model: str
    base_fee: Decimal
    performance_fee_pct: Decimal
    config_overrides: dict[str, Any]
    created_at: datetime


class RunDimensionOut(BaseModel):
    dimension: str
    total_spend: Decimal
    total_wasted_spend: Decimal
    benchmark_cpa: Decimal | None = None


class FlaggedSegmentOut(BaseModel):
    dimension: str
    segment_value: str
    spend: Decimal
    conversions: int
    cpa: Decimal | None = None
    wasted_spend: Decimal


class RunAdminOut(BaseModel):
    id: int
    client_id: int
    business_name: str
    upload_id: int
    status: str
    review_status: str
    headline_waste: Decimal | None = None
    review_note: str | None = None
    reviewed_by: int | None = None
    reviewed_at: datetime | None = None
    created_at: datetime
    dimensions: list[RunDimensionOut]
    flagged_segments: list[FlaggedSegmentOut]
    config_snapshot: dict[str, Any]


class ReviewIn(BaseModel):
    note: str | None = Field(default=None, max_length=2000)


class InvoiceDraftIn(BaseModel):
    client_id: int
    period_start: date
    period_end: date


class ConfirmInvoiceIn(BaseModel):
    confirmed_recovered_waste: Decimal = Field(ge=0)


class IssueInvoiceIn(BaseModel):
    due_date: date


class VoidInvoiceIn(BaseModel):
    note: str | None = Field(default=None, max_length=2000)


class AdminInvoiceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    invoice_number: str
    client_id: int
    period_start: date
    period_end: date
    due_date: date
    base_fee: Decimal
    suggested_recovered_waste: Decimal
    confirmed_recovered_waste: Decimal
    performance_fee: Decimal
    total: Decimal
    amount_paid: Decimal
    status: str
    confirmed_by: int | None = None
    issued_at: datetime | None = None
    created_at: datetime


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    actor_user_id: int | None = None
    action: str
    entity_type: str
    entity_id: int
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    created_at: datetime
```

- [ ] **Step 4: Add `serialize_run` to `services/admin.py`**

Add to the imports of `backend/app/services/admin.py`:
```python
from app.models import AnalysisRun, Client, SegmentMetric, User, WasteReport
from app.schemas.admin import ClientPatch, FlaggedSegmentOut, RunAdminOut, RunDimensionOut
```

Append to `backend/app/services/admin.py`:
```python
def serialize_run(session: Session, run: AnalysisRun) -> RunAdminOut:
    """One run with everything the approval queue shows: per-dimension totals, the flagged
    segments behind them and the config snapshot it was produced with.

    Dimension totals are listed side by side and never summed — the headline figure is the
    largest single dimension and is already stored on the run (docs/PLAN.md section 1 #1).
    """
    reports = list(
        session.scalars(
            select(WasteReport).where(WasteReport.run_id == run.id).order_by(WasteReport.dimension)
        )
    )
    dimensions = [
        RunDimensionOut(
            dimension=r.dimension,
            total_spend=r.total_spend,
            total_wasted_spend=r.total_wasted_spend,
            benchmark_cpa=r.benchmark_cpa,
        )
        for r in reports
    ]

    flagged: list[FlaggedSegmentOut] = []
    if reports:
        by_id = {r.id: r.dimension for r in reports}
        rows = session.scalars(
            select(SegmentMetric)
            .where(SegmentMetric.report_id.in_(by_id), SegmentMetric.is_flagged.is_(True))
            .order_by(SegmentMetric.wasted_spend.desc())
        )
        flagged = [
            FlaggedSegmentOut(
                dimension=by_id[s.report_id],
                segment_value=s.segment_value,
                spend=s.spend,
                conversions=s.conversions,
                cpa=s.cpa,
                wasted_spend=s.wasted_spend,
            )
            for s in rows
        ]

    client = session.get(Client, run.client_id)
    return RunAdminOut(
        id=run.id,
        client_id=run.client_id,
        business_name=client.business_name if client else "",
        upload_id=run.upload_id,
        status=run.status,
        review_status=run.review_status,
        headline_waste=run.headline_waste,
        review_note=run.review_note,
        reviewed_by=run.reviewed_by,
        reviewed_at=run.reviewed_at,
        created_at=run.created_at,
        dimensions=dimensions,
        flagged_segments=flagged,
        config_snapshot=run.config_snapshot or {},
    )
```

- [ ] **Step 5: Write the router**

`backend/app/routers/__init__.py`: empty file (skip if it exists).

`backend/app/routers/admin.py`:
```python
"""/api/admin — operator routes. Every one of them is gated by CurrentAdmin."""

from typing import Literal

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.db import get_session
from app.core.deps import CurrentAdmin
from app.schemas.admin import (
    AdminClientOut,
    AdminInvoiceOut,
    AuditLogOut,
    ClientPatch,
    ConfirmInvoiceIn,
    InvoiceDraftIn,
    IssueInvoiceIn,
    ReviewIn,
    RunAdminOut,
    VoidInvoiceIn,
)
from app.services import admin as admin_service
from app.services import audit as audit_service
from app.services import billing as billing_service

router = APIRouter(prefix="/api/admin", tags=["admin"])

ReviewStatus = Literal["pending", "approved", "rejected"]
InvoiceStatus = Literal["draft", "issued", "payment_submitted", "paid", "void"]


@router.get("/clients", response_model=list[AdminClientOut])
def list_clients(actor: CurrentAdmin, session: Session = Depends(get_session)):
    return admin_service.list_clients(session)


@router.get("/clients/{client_id}", response_model=AdminClientOut)
def get_client(client_id: int, actor: CurrentAdmin, session: Session = Depends(get_session)):
    return admin_service.get_client(session, client_id)


@router.patch("/clients/{client_id}", response_model=AdminClientOut)
def update_client(
    client_id: int,
    patch: ClientPatch,
    actor: CurrentAdmin,
    session: Session = Depends(get_session),
):
    return admin_service.update_client(session, actor, client_id, patch)


@router.get("/runs", response_model=list[RunAdminOut])
def list_runs(
    actor: CurrentAdmin,
    review_status: ReviewStatus | None = Query(default=None),
    session: Session = Depends(get_session),
):
    runs = admin_service.list_runs(session, review_status)
    return [admin_service.serialize_run(session, run) for run in runs]


@router.post("/runs/{run_id}/approve", response_model=RunAdminOut)
def approve_run(
    run_id: int, body: ReviewIn, actor: CurrentAdmin, session: Session = Depends(get_session)
):
    run = admin_service.approve_run(session, actor, run_id, body.note)
    return admin_service.serialize_run(session, run)


@router.post("/runs/{run_id}/reject", response_model=RunAdminOut)
def reject_run(
    run_id: int, body: ReviewIn, actor: CurrentAdmin, session: Session = Depends(get_session)
):
    run = admin_service.reject_run(session, actor, run_id, body.note)
    return admin_service.serialize_run(session, run)


@router.get("/invoices", response_model=list[AdminInvoiceOut])
def list_invoices(
    actor: CurrentAdmin,
    client_id: int | None = Query(default=None),
    invoice_status: InvoiceStatus | None = Query(default=None, alias="status"),
    session: Session = Depends(get_session),
):
    return billing_service.list_invoices(session, client_id=client_id, status=invoice_status)


@router.post("/invoices", response_model=AdminInvoiceOut, status_code=status.HTTP_201_CREATED)
def draft_invoice(body: InvoiceDraftIn, actor: CurrentAdmin, session: Session = Depends(get_session)):
    return billing_service.draft_invoice(
        session, actor, body.client_id, body.period_start, body.period_end
    )


@router.post("/invoices/{invoice_id}/confirm", response_model=AdminInvoiceOut)
def confirm_invoice(
    invoice_id: int,
    body: ConfirmInvoiceIn,
    actor: CurrentAdmin,
    session: Session = Depends(get_session),
):
    return billing_service.confirm_invoice(
        session, actor, invoice_id, body.confirmed_recovered_waste
    )


@router.post("/invoices/{invoice_id}/issue", response_model=AdminInvoiceOut)
def issue_invoice(
    invoice_id: int,
    body: IssueInvoiceIn,
    actor: CurrentAdmin,
    session: Session = Depends(get_session),
):
    return billing_service.issue_invoice(session, actor, invoice_id, body.due_date)


@router.post("/invoices/{invoice_id}/void", response_model=AdminInvoiceOut)
def void_invoice(
    invoice_id: int,
    body: VoidInvoiceIn,
    actor: CurrentAdmin,
    session: Session = Depends(get_session),
):
    return billing_service.void_invoice(session, actor, invoice_id, body.note)


@router.get("/audit-log", response_model=list[AuditLogOut])
def list_audit_log(
    actor: CurrentAdmin,
    limit: int = Query(default=200, ge=1, le=1000),
    entity_type: str | None = Query(default=None),
    action: str | None = Query(default=None),
    session: Session = Depends(get_session),
):
    return audit_service.list_entries(session, limit=limit, entity_type=entity_type, action=action)
```

- [ ] **Step 6: Mount the router**

In `backend/app/main.py`, inside `create_app()` next to the other `include_router` calls:
```python
    from app.routers.admin import router as admin_router

    application.include_router(admin_router)
```

- [ ] **Step 7: Run the permission tests to verify they pass**

Run: `cd backend && .venv/Scripts/python -m pytest tests/api/test_admin_permissions.py -v`
Expected: `26 passed` (12 client-403 cases + 12 anonymous-401 cases + 2 admin cases)

- [ ] **Step 8: Check the OpenAPI surface matches `docs/PLAN.md` §5**

Run:
```bash
cd backend && .venv/Scripts/python -c "from app.main import create_app; import json; print(json.dumps(sorted(p for p in create_app().openapi()['paths'] if p.startswith('/api/admin')), indent=1))"
```
Expected exactly:
```
["/api/admin/audit-log", "/api/admin/clients", "/api/admin/clients/{client_id}",
 "/api/admin/invoices", "/api/admin/invoices/{invoice_id}/confirm",
 "/api/admin/invoices/{invoice_id}/issue", "/api/admin/invoices/{invoice_id}/void",
 "/api/admin/runs", "/api/admin/runs/{run_id}/approve", "/api/admin/runs/{run_id}/reject"]
```
No `/api/admin/payments*` or `/api/admin/payment-methods` — those are Stage 7.

- [ ] **Step 9: Lint and commit**

Run: `cd backend && .venv/Scripts/ruff check . && .venv/Scripts/ruff format .`
```bash
git add backend/app/schemas/admin.py backend/app/services/admin.py backend/app/routers backend/app/main.py backend/tests/api
git commit -m "feat(admin): /api/admin router, schemas and admin-only access" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 7: API integration tests — approval gate, invoice flow, audit trail

**Files:**
- Test: `backend/tests/api/test_admin_api.py`

**Interfaces:**
- Consumes: everything from Tasks 1–6, plus Stage 3's `GET /api/reports/{run_id}` and `CurrentClient`.
- Produces: no production code — this task is the Stage 6 "Done when" proof.

- [ ] **Step 1: Write the failing test**

`backend/tests/api/test_admin_api.py`:
```python
"""Stage 6 exit criteria, exercised over HTTP (docs/PLAN.md section 6)."""

from datetime import UTC, datetime
from decimal import Decimal

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

    issued = api.post(
        f"/api/admin/invoices/{invoice_id}/issue", json={"due_date": "2026-09-20"}
    )
    assert issued.status_code == 200
    assert issued.json()["status"] == "issued"
    assert issued.json()["due_date"] == "2026-09-20"
    assert issued.json()["issued_at"] is not None

    listed = api.get("/api/admin/invoices", params={"status": "issued"}).json()
    assert [i["invoice_number"] for i in listed] == ["INV-2026-0001"]

    actions = [e["action"] for e in api.get("/api/admin/audit-log", params={"entity_type": "invoice"}).json()]
    assert actions == ["invoice.issue", "invoice.confirm", "invoice.draft"]  # newest first


def test_issuing_before_confirming_is_409(api, db):
    admin = make_admin(db)
    client = make_client(db)
    db.commit()
    login_as(api, admin)
    invoice_id = api.post("/api/admin/invoices", json={"client_id": client.id, **AUGUST}).json()["id"]

    response = api.post(f"/api/admin/invoices/{invoice_id}/issue", json={"due_date": "2026-09-20"})

    assert response.status_code == 409
    assert "confirm the performance fee" in response.json()["detail"]


def test_voiding_a_draft_records_the_reason(api, db):
    admin = make_admin(db)
    client = make_client(db)
    db.commit()
    login_as(api, admin)
    invoice_id = api.post("/api/admin/invoices", json={"client_id": client.id, **AUGUST}).json()["id"]

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
    invoice_id = api.post("/api/admin/invoices", json={"client_id": client.id, **AUGUST}).json()["id"]

    response = api.post(
        f"/api/admin/invoices/{invoice_id}/confirm", json={"confirmed_recovered_waste": "-5"}
    )

    assert response.status_code == 422
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd backend && .venv/Scripts/python -m pytest tests/api/test_admin_api.py -v`
Expected: some cases already pass (the router exists); any failure here is a real defect. The two most likely: `test_approving_a_run_is_what_lets_the_client_see_the_report` failing because the report route needs `WasteReport` rows the factory does create, and audit ordering if `id DESC` was dropped from `list_entries`.

- [ ] **Step 3: Fix what the tests expose**

No new module is expected. If `GET /api/reports/{run_id}` returns 404 for the approved run, check Stage 3's `get_report` rule (`status == "done"` **and** `review_status == "approved"`) against the factory defaults (`status="done"`), and fix the factory call, not the rule.

- [ ] **Step 4: Run the whole backend suite**

Run: `cd backend && .venv/Scripts/python -m pytest -v`
Expected: every test passes, including the Stage 0–4 suites; `11 passed` for this file.

- [ ] **Step 5: Lint and commit**

Run: `cd backend && .venv/Scripts/ruff check . && .venv/Scripts/ruff format .`
```bash
git add backend/tests/api/test_admin_api.py
git commit -m "test(admin): end-to-end approval gate, invoice flow and audit trail" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 8: Admin shell and the clients pages

**Files:**
- Create: `frontend/src/lib/admin-types.ts`
- Create: `frontend/src/components/admin/Table.tsx`
- Create: `frontend/src/app/admin/layout.tsx`
- Create: `frontend/src/app/admin/page.tsx`
- Create: `frontend/src/app/admin/clients/page.tsx`
- Create: `frontend/src/app/admin/clients/[id]/page.tsx`
- Create: `frontend/src/components/admin/ClientEditForm.tsx`

**Interfaces:**
- Consumes: `apiFetch` from `@/lib/api` and `formatPKR` from `@/lib/format` (Stage 4), the Tailwind tokens from `globals.css`.
- Produces:
  ```ts
  // src/lib/admin-types.ts  — Decimals arrive as JSON strings; convert with Number() only for display
  export type AdminClient, RunDimension, FlaggedSegment, AdminRun, AdminInvoice, AuditEntry
  // src/components/admin/Table.tsx
  export function Table(props: { children: ReactNode })
  export function Th(props: { children: ReactNode; align?: "left" | "right" })
  export function Td(props: { children: ReactNode; align?: "left" | "right" })
  // src/components/admin/ClientEditForm.tsx
  export default function ClientEditForm({ client }: { client: AdminClient })
  ```

- [ ] **Step 1: Write the TS mirrors**

`frontend/src/lib/admin-types.ts`:
```ts
// Mirrors backend/app/schemas/admin.py. Every Decimal is a JSON string ("19600.00").

export type AdminClient = {
  id: number;
  business_name: string;
  contact_info: string | null;
  pricing_model: string;
  base_fee: string;
  performance_fee_pct: string;
  config_overrides: Record<string, unknown>;
  created_at: string;
};

export type RunDimension = {
  dimension: string;
  total_spend: string;
  total_wasted_spend: string;
  benchmark_cpa: string | null;
};

export type FlaggedSegment = {
  dimension: string;
  segment_value: string;
  spend: string;
  conversions: number;
  cpa: string | null;
  wasted_spend: string;
};

export type AdminRun = {
  id: number;
  client_id: number;
  business_name: string;
  upload_id: number;
  status: string;
  review_status: "pending" | "approved" | "rejected";
  headline_waste: string | null;
  review_note: string | null;
  reviewed_by: number | null;
  reviewed_at: string | null;
  created_at: string;
  dimensions: RunDimension[];
  flagged_segments: FlaggedSegment[];
  config_snapshot: Record<string, unknown>;
};

export type AdminInvoice = {
  id: number;
  invoice_number: string;
  client_id: number;
  period_start: string;
  period_end: string;
  due_date: string;
  base_fee: string;
  suggested_recovered_waste: string;
  confirmed_recovered_waste: string;
  performance_fee: string;
  total: string;
  amount_paid: string;
  status: "draft" | "issued" | "payment_submitted" | "paid" | "void";
  confirmed_by: number | null;
  issued_at: string | null;
  created_at: string;
};

export type AuditEntry = {
  id: number;
  actor_user_id: number | null;
  action: string;
  entity_type: string;
  entity_id: number;
  before: Record<string, unknown> | null;
  after: Record<string, unknown> | null;
  created_at: string;
};
```

- [ ] **Step 2: Write the table primitives**

`frontend/src/components/admin/Table.tsx`:
```tsx
import type { ReactNode } from "react";

// Admin tables are dense and static: hairline dividers, no zebra striping, no animation.
export function Table({ children }: { children: ReactNode }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-sm">{children}</table>
    </div>
  );
}

export function Th({
  children,
  align = "left",
}: {
  children: ReactNode;
  align?: "left" | "right";
}) {
  return (
    <th
      className={`border-b border-white/15 px-3 py-1.5 font-body text-xs font-medium uppercase tracking-wide text-slate ${
        align === "right" ? "text-right" : "text-left"
      }`}
    >
      {children}
    </th>
  );
}

export function Td({
  children,
  align = "left",
}: {
  children: ReactNode;
  align?: "left" | "right";
}) {
  return (
    <td
      className={`border-b border-white/10 px-3 py-1.5 align-top ${
        align === "right" ? "text-right tabular-nums" : "text-left"
      }`}
    >
      {children}
    </td>
  );
}
```

- [ ] **Step 3: Write the server-side admin guard**

`frontend/src/app/admin/layout.tsx`:
```tsx
import Link from "next/link";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

const BACKEND = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

const NAV = [
  { href: "/admin/runs", label: "Runs" },
  { href: "/admin/clients", label: "Clients" },
  { href: "/admin/invoices", label: "Invoices" },
  { href: "/admin/audit", label: "Audit log" },
];

async function requireAdmin() {
  const jar = await cookies();
  const response = await fetch(`${BACKEND}/api/auth/me`, {
    headers: { cookie: jar.toString() },
    cache: "no-store",
  });
  if (response.status === 401) redirect("/login");
  if (!response.ok) redirect("/login");
  const me = await response.json();
  if (me.user?.role !== "admin") redirect("/dashboard");
  return me;
}

export default async function AdminLayout({ children }: { children: React.ReactNode }) {
  const me = await requireAdmin();
  return (
    <div className="min-h-screen">
      <header className="flex items-baseline gap-6 border-b border-white/15 px-6 py-3">
        <span className="font-display text-base">Admin</span>
        <nav className="flex gap-4 text-sm text-slate">
          {NAV.map((item) => (
            <Link key={item.href} href={item.href} className="hover:text-paper">
              {item.label}
            </Link>
          ))}
        </nav>
        <span className="ml-auto text-xs text-slate">{me.user.email}</span>
      </header>
      <main className="px-6 py-5">{children}</main>
    </div>
  );
}
```

`frontend/src/app/admin/page.tsx`:
```tsx
import { redirect } from "next/navigation";

export default function AdminIndex() {
  redirect("/admin/runs");
}
```

- [ ] **Step 4: Write the clients list and detail pages**

`frontend/src/app/admin/clients/page.tsx`:
```tsx
"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Table, Td, Th } from "@/components/admin/Table";
import { apiFetch } from "@/lib/api";
import { formatPKR } from "@/lib/format";
import type { AdminClient } from "@/lib/admin-types";

export default function ClientsPage() {
  const [clients, setClients] = useState<AdminClient[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<AdminClient[]>("/api/admin/clients")
      .then(setClients)
      .catch((e: Error) => setError(e.message));
  }, []);

  if (error) return <p className="text-coral">{error}</p>;
  if (!clients) return <p className="text-slate">Loading…</p>;

  return (
    <Table>
      <thead>
        <tr>
          <Th>Business</Th>
          <Th align="right">Base fee</Th>
          <Th align="right">Performance %</Th>
          <Th>Overrides</Th>
          <Th>Joined</Th>
        </tr>
      </thead>
      <tbody>
        {clients.map((client) => (
          <tr key={client.id}>
            <Td>
              <Link href={`/admin/clients/${client.id}`} className="underline">
                {client.business_name}
              </Link>
            </Td>
            <Td align="right">{formatPKR(Number(client.base_fee))}</Td>
            <Td align="right">{Number(client.performance_fee_pct)}%</Td>
            <Td>{Object.keys(client.config_overrides).length || "—"}</Td>
            <Td>{client.created_at.slice(0, 10)}</Td>
          </tr>
        ))}
      </tbody>
    </Table>
  );
}
```

`frontend/src/components/admin/ClientEditForm.tsx`:
```tsx
"use client";

import { useState } from "react";

import { apiFetch } from "@/lib/api";
import type { AdminClient } from "@/lib/admin-types";

export default function ClientEditForm({ client }: { client: AdminClient }) {
  const [baseFee, setBaseFee] = useState(client.base_fee);
  const [pct, setPct] = useState(client.performance_fee_pct);
  const [overrides, setOverrides] = useState(JSON.stringify(client.config_overrides, null, 2));
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  async function save(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    setSaved(false);

    let parsed: unknown;
    try {
      parsed = JSON.parse(overrides || "{}");
    } catch {
      setError("Overrides must be valid JSON.");
      return;
    }

    try {
      await apiFetch<AdminClient>(`/api/admin/clients/${client.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          base_fee: baseFee,
          performance_fee_pct: pct,
          config_overrides: parsed,
        }),
      });
      setSaved(true);
    } catch (e) {
      // 422 from PipelineConfig.from_overrides: "unknown config key: typo_key"
      setError(e instanceof Error ? e.message : "Save failed.");
    }
  }

  return (
    <form onSubmit={save} className="max-w-xl space-y-3 text-sm">
      <label className="block">
        <span className="text-xs uppercase tracking-wide text-slate">Base fee (PKR)</span>
        <input
          value={baseFee}
          onChange={(e) => setBaseFee(e.target.value)}
          className="mt-1 w-full border border-white/15 bg-surface px-2 py-1 tabular-nums"
        />
      </label>
      <label className="block">
        <span className="text-xs uppercase tracking-wide text-slate">Performance fee %</span>
        <input
          value={pct}
          onChange={(e) => setPct(e.target.value)}
          className="mt-1 w-full border border-white/15 bg-surface px-2 py-1 tabular-nums"
        />
      </label>
      <label className="block">
        <span className="text-xs uppercase tracking-wide text-slate">
          Config overrides (JSON — keys must exist in PipelineConfig)
        </span>
        <textarea
          value={overrides}
          onChange={(e) => setOverrides(e.target.value)}
          rows={10}
          className="mt-1 w-full border border-white/15 bg-surface px-2 py-1 font-mono text-xs"
        />
      </label>
      {error && <p role="alert" className="text-coral">{error}</p>}
      {saved && <p className="text-teal">Saved.</p>}
      <button type="submit" className="border border-teal px-3 py-1 text-teal">
        Save
      </button>
    </form>
  );
}
```

`frontend/src/app/admin/clients/[id]/page.tsx`:
```tsx
"use client";

import { use, useEffect, useState } from "react";

import ClientEditForm from "@/components/admin/ClientEditForm";
import { apiFetch } from "@/lib/api";
import type { AdminClient } from "@/lib/admin-types";

export default function ClientDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [client, setClient] = useState<AdminClient | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<AdminClient>(`/api/admin/clients/${id}`)
      .then(setClient)
      .catch((e: Error) => setError(e.message));
  }, [id]);

  if (error) return <p className="text-coral">{error}</p>;
  if (!client) return <p className="text-slate">Loading…</p>;

  return (
    <div className="space-y-4">
      <h1 className="font-display text-xl">{client.business_name}</h1>
      <ClientEditForm client={client} />
    </div>
  );
}
```

- [ ] **Step 5: Typecheck, lint and build**

Run: `cd frontend && npx tsc --noEmit && npm run lint && npm run build`
Expected: no type errors, no lint errors, build succeeds with `/admin/clients` and `/admin/clients/[id]` in the route list.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/lib/admin-types.ts frontend/src/components/admin frontend/src/app/admin
git commit -m "feat(admin-ui): admin shell with role guard and client fee editing" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 9: The approval queue page and `RunQueueRow`

**Files:**
- Create: `frontend/src/components/admin/RunQueueRow.tsx`
- Create: `frontend/src/components/admin/RunQueueRow.test.tsx`
- Create: `frontend/src/app/admin/runs/page.tsx`
- Modify: `frontend/package.json` / `frontend/vitest.config.ts` (only if Stage 4 did not already set Vitest up)

**Interfaces:**
- Consumes: `AdminRun`, `FlaggedSegment` from `@/lib/admin-types`; `Td`/`Th`/`Table`; `formatPKR`.
- Produces:
  ```tsx
  export default function RunQueueRow(props: {
    run: AdminRun;
    expanded: boolean;
    busy?: boolean;
    onToggle: () => void;
    onApprove: (note: string) => void;
    onReject: (note: string) => void;
  })
  ```
  `RunQueueRow` is pure presentation — it never calls `apiFetch`, which is what makes it unit-testable.

- [ ] **Step 1: Make sure the test runner exists**

Run: `cd frontend && npm run test -- --run 2>&1 | head -5`
Expected: Vitest runs (Stage 4 added it). If instead you see `Missing script: "test"`, set it up now:
```bash
cd frontend && npm i -D vitest@3 @vitejs/plugin-react jsdom @testing-library/react @testing-library/jest-dom @testing-library/user-event
```
`frontend/vitest.config.ts`:
```ts
import path from "node:path";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { "@": path.resolve(__dirname, "src") } },
  test: { environment: "jsdom", globals: true, setupFiles: ["./vitest.setup.ts"] },
});
```
`frontend/vitest.setup.ts`:
```ts
import "@testing-library/jest-dom/vitest";
```
Add to `frontend/package.json` `scripts`: `"test": "vitest"`.

- [ ] **Step 2: Write the failing test**

`frontend/src/components/admin/RunQueueRow.test.tsx`:
```tsx
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import RunQueueRow from "./RunQueueRow";
import type { AdminRun } from "@/lib/admin-types";

const RUN: AdminRun = {
  id: 7,
  client_id: 3,
  business_name: "Acme Traders",
  upload_id: 11,
  status: "done",
  review_status: "pending",
  headline_waste: "52000.00",
  review_note: null,
  reviewed_by: null,
  reviewed_at: null,
  created_at: "2026-08-25T00:00:00Z",
  dimensions: [
    { dimension: "placement", total_spend: "100000.00", total_wasted_spend: "52000.00", benchmark_cpa: "800.00" },
    { dimension: "age_group", total_spend: "100000.00", total_wasted_spend: "12000.00", benchmark_cpa: "800.00" },
  ],
  flagged_segments: [
    { dimension: "placement", segment_value: "audience_network", spend: "84000.00", conversions: 40, cpa: "2100.00", wasted_spend: "52000.00" },
    { dimension: "age_group", segment_value: "55-64", spend: "20000.00", conversions: 5, cpa: "4000.00", wasted_spend: "12000.00" },
  ],
  config_snapshot: { benchmark_mode: "account_avg", waste_multiplier: 1.5 },
};

function renderRow(overrides: Partial<React.ComponentProps<typeof RunQueueRow>> = {}) {
  const props = {
    run: RUN,
    expanded: false,
    onToggle: vi.fn(),
    onApprove: vi.fn(),
    onReject: vi.fn(),
    ...overrides,
  };
  render(
    <table>
      <tbody>
        <RunQueueRow {...props} />
      </tbody>
    </table>,
  );
  return props;
}

describe("RunQueueRow", () => {
  it("shows the summary line with the headline waste", () => {
    renderRow();
    expect(screen.getByText("Acme Traders")).toBeInTheDocument();
    expect(screen.getByText("Rs. 52,000")).toBeInTheDocument();
  });

  it("hides the detail until the row is expanded", () => {
    renderRow();
    expect(screen.queryByText("audience_network")).not.toBeInTheDocument();
  });

  it("renders every flagged segment and per-dimension total when expanded", () => {
    renderRow({ expanded: true });

    expect(screen.getByText("audience_network")).toBeInTheDocument();
    expect(screen.getByText("55-64")).toBeInTheDocument();
    // per-dimension totals are listed side by side, never summed
    expect(screen.getByTestId("dimension-placement")).toHaveTextContent("Rs. 52,000");
    expect(screen.getByTestId("dimension-age_group")).toHaveTextContent("Rs. 12,000");
    expect(screen.getByText(/"benchmark_mode": "account_avg"/)).toBeInTheDocument();
  });

  it("passes the typed note to onApprove and onReject", () => {
    const props = renderRow({ expanded: true });

    fireEvent.change(screen.getByLabelText("Review note"), {
      target: { value: "numbers checked" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Approve" }));
    expect(props.onApprove).toHaveBeenCalledWith("numbers checked");

    fireEvent.click(screen.getByRole("button", { name: "Reject" }));
    expect(props.onReject).toHaveBeenCalledWith("numbers checked");
  });

  it("hides the review controls once a run has been reviewed", () => {
    renderRow({
      run: { ...RUN, review_status: "approved", review_note: "checked" },
      expanded: true,
    });
    expect(screen.queryByRole("button", { name: "Approve" })).not.toBeInTheDocument();
    expect(screen.getByText("checked")).toBeInTheDocument();
  });
});
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `cd frontend && npx vitest run src/components/admin/RunQueueRow.test.tsx`
Expected: FAIL with `Failed to resolve import "./RunQueueRow"`

- [ ] **Step 4: Write `RunQueueRow`**

`frontend/src/components/admin/RunQueueRow.tsx`:
```tsx
"use client";

import { useState } from "react";

import { Td } from "@/components/admin/Table";
import { formatPKR } from "@/lib/format";
import type { AdminRun } from "@/lib/admin-types";

export default function RunQueueRow({
  run,
  expanded,
  busy = false,
  onToggle,
  onApprove,
  onReject,
}: {
  run: AdminRun;
  expanded: boolean;
  busy?: boolean;
  onToggle: () => void;
  onApprove: (note: string) => void;
  onReject: (note: string) => void;
}) {
  const [note, setNote] = useState("");

  return (
    <>
      <tr>
        <Td>
          <button type="button" onClick={onToggle} className="underline">
            {expanded ? "−" : "+"} #{run.id}
          </button>
        </Td>
        <Td>{run.business_name}</Td>
        <Td>{run.created_at.slice(0, 10)}</Td>
        <Td>{run.status}</Td>
        <Td align="right">
          {run.headline_waste === null ? "—" : formatPKR(Number(run.headline_waste))}
        </Td>
        <Td align="right">{run.flagged_segments.length}</Td>
        <Td>{run.review_status}</Td>
      </tr>
      {expanded && (
        <tr>
          <Td>{null}</Td>
          <td colSpan={6} className="border-b border-white/10 px-3 py-3">
            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <h3 className="mb-1 font-display text-sm">Waste per dimension</h3>
                <ul className="space-y-0.5 text-sm">
                  {run.dimensions.map((d) => (
                    <li
                      key={d.dimension}
                      data-testid={`dimension-${d.dimension}`}
                      className="flex justify-between border-b border-white/10 py-0.5"
                    >
                      <span>{d.dimension}</span>
                      <span className="tabular-nums">
                        {formatPKR(Number(d.total_wasted_spend))} of{" "}
                        {formatPKR(Number(d.total_spend))}
                      </span>
                    </li>
                  ))}
                </ul>
                <p className="mt-1 text-xs text-slate">
                  Headline waste is the largest single dimension — dimensions are never added up.
                </p>
              </div>

              <div>
                <h3 className="mb-1 font-display text-sm">Flagged segments</h3>
                <ul className="space-y-0.5 text-sm">
                  {run.flagged_segments.map((s) => (
                    <li
                      key={`${s.dimension}:${s.segment_value}`}
                      className="flex justify-between border-b border-white/10 py-0.5"
                    >
                      <span className="text-coral">{s.segment_value}</span>
                      <span className="tabular-nums">
                        {formatPKR(Number(s.wasted_spend))} wasted · {s.conversions} conv
                      </span>
                    </li>
                  ))}
                </ul>
              </div>

              <div className="md:col-span-2">
                <h3 className="mb-1 font-display text-sm">Config snapshot</h3>
                <pre className="overflow-x-auto border border-white/15 bg-surface p-2 font-mono text-xs">
                  {JSON.stringify(run.config_snapshot, null, 2)}
                </pre>
              </div>

              {run.review_status === "pending" ? (
                <div className="md:col-span-2 flex flex-wrap items-end gap-2">
                  <label className="flex-1">
                    <span className="block text-xs uppercase tracking-wide text-slate">
                      Review note
                    </span>
                    <input
                      aria-label="Review note"
                      value={note}
                      onChange={(e) => setNote(e.target.value)}
                      className="mt-1 w-full border border-white/15 bg-surface px-2 py-1"
                    />
                  </label>
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => onApprove(note)}
                    className="border border-teal px-3 py-1 text-teal disabled:opacity-50"
                  >
                    Approve
                  </button>
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => onReject(note)}
                    className="border border-coral px-3 py-1 text-coral disabled:opacity-50"
                  >
                    Reject
                  </button>
                </div>
              ) : (
                <p className="md:col-span-2 text-sm text-slate">
                  {run.review_status} — {run.review_note ?? "no note"}
                </p>
              )}
            </div>
          </td>
        </tr>
      )}
    </>
  );
}
```

- [ ] **Step 5: Write the queue page**

`frontend/src/app/admin/runs/page.tsx`:
```tsx
"use client";

import { useCallback, useEffect, useState } from "react";

import RunQueueRow from "@/components/admin/RunQueueRow";
import { Table, Th } from "@/components/admin/Table";
import { apiFetch } from "@/lib/api";
import type { AdminRun } from "@/lib/admin-types";

const FILTERS = ["pending", "approved", "rejected", "all"] as const;
type Filter = (typeof FILTERS)[number];

export default function RunsPage() {
  const [filter, setFilter] = useState<Filter>("pending");
  const [runs, setRuns] = useState<AdminRun[] | null>(null);
  const [expanded, setExpanded] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    const query = filter === "all" ? "" : `?review_status=${filter}`;
    apiFetch<AdminRun[]>(`/api/admin/runs${query}`)
      .then(setRuns)
      .catch((e: Error) => setError(e.message));
  }, [filter]);

  useEffect(load, [load]);

  async function review(runId: number, action: "approve" | "reject", note: string) {
    setBusy(true);
    setError(null);
    try {
      await apiFetch<AdminRun>(`/api/admin/runs/${runId}/${action}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ note: note || null }),
      });
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Review failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-3">
      <div className="flex gap-2 text-sm">
        {FILTERS.map((f) => (
          <button
            key={f}
            type="button"
            onClick={() => setFilter(f)}
            className={`border px-2 py-0.5 ${
              filter === f ? "border-teal text-teal" : "border-white/15 text-slate"
            }`}
          >
            {f}
          </button>
        ))}
      </div>
      {error && <p className="text-coral">{error}</p>}
      {!runs ? (
        <p className="text-slate">Loading…</p>
      ) : runs.length === 0 ? (
        <p className="text-slate">Nothing waiting for review.</p>
      ) : (
        <Table>
          <thead>
            <tr>
              <Th>Run</Th>
              <Th>Client</Th>
              <Th>Created</Th>
              <Th>Status</Th>
              <Th align="right">Headline waste</Th>
              <Th align="right">Flagged</Th>
              <Th>Review</Th>
            </tr>
          </thead>
          <tbody>
            {runs.map((run) => (
              <RunQueueRow
                key={run.id}
                run={run}
                expanded={expanded === run.id}
                busy={busy}
                onToggle={() => setExpanded(expanded === run.id ? null : run.id)}
                onApprove={(note) => review(run.id, "approve", note)}
                onReject={(note) => review(run.id, "reject", note)}
              />
            ))}
          </tbody>
        </Table>
      )}
    </div>
  );
}
```

- [ ] **Step 6: Run the test to verify it passes**

Run: `cd frontend && npx vitest run src/components/admin/RunQueueRow.test.tsx`
Expected: `Test Files 1 passed`, `Tests 5 passed`

- [ ] **Step 7: Typecheck, lint, build and commit**

Run: `cd frontend && npx tsc --noEmit && npm run lint && npm run build`
Expected: clean.
```bash
git add frontend/src/components/admin/RunQueueRow.tsx frontend/src/components/admin/RunQueueRow.test.tsx frontend/src/app/admin/runs frontend/package.json frontend/vitest.config.ts frontend/vitest.setup.ts
git commit -m "feat(admin-ui): approval queue with per-dimension detail and config snapshot" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 10: Invoices page, `InvoiceForm` and the audit log page

**Files:**
- Create: `frontend/src/components/admin/InvoiceForm.tsx`
- Create: `frontend/src/components/admin/InvoiceForm.test.tsx`
- Create: `frontend/src/app/admin/invoices/page.tsx`
- Create: `frontend/src/app/admin/audit/page.tsx`

**Interfaces:**
- Consumes: `apiFetch`, `formatPKR`, `AdminClient`, `AdminInvoice`, `AuditEntry`, `Table`/`Th`/`Td`.
- Produces:
  ```tsx
  export default function InvoiceForm(props: {
    clients: AdminClient[];
    onCreated: (invoice: AdminInvoice) => void;
  })
  ```
  It POSTs `{ client_id: number, period_start: string, period_end: string }` to `/api/admin/invoices`.

- [ ] **Step 1: Write the failing test**

`frontend/src/components/admin/InvoiceForm.test.tsx`:
```tsx
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import InvoiceForm from "./InvoiceForm";
import { apiFetch } from "@/lib/api";
import type { AdminClient, AdminInvoice } from "@/lib/admin-types";

vi.mock("@/lib/api", () => ({ apiFetch: vi.fn() }));

const CLIENTS: AdminClient[] = [
  {
    id: 3,
    business_name: "Acme Traders",
    contact_info: null,
    pricing_model: "hybrid",
    base_fee: "15000.00",
    performance_fee_pct: "20.00",
    config_overrides: {},
    created_at: "2026-07-01T00:00:00Z",
  },
];

const DRAFT: AdminInvoice = {
  id: 1,
  invoice_number: "INV-2026-0001",
  client_id: 3,
  period_start: "2026-08-01",
  period_end: "2026-08-31",
  due_date: "2026-09-14",
  base_fee: "15000.00",
  suggested_recovered_waste: "23000.00",
  confirmed_recovered_waste: "0.00",
  performance_fee: "4600.00",
  total: "19600.00",
  amount_paid: "0.00",
  status: "draft",
  confirmed_by: null,
  issued_at: null,
  created_at: "2026-09-01T00:00:00Z",
};

describe("InvoiceForm", () => {
  beforeEach(() => vi.mocked(apiFetch).mockReset());

  it("posts the selected client and period, then hands the draft back", async () => {
    vi.mocked(apiFetch).mockResolvedValue(DRAFT);
    const onCreated = vi.fn();
    render(<InvoiceForm clients={CLIENTS} onCreated={onCreated} />);

    fireEvent.change(screen.getByLabelText("Client"), { target: { value: "3" } });
    fireEvent.change(screen.getByLabelText("Period start"), { target: { value: "2026-08-01" } });
    fireEvent.change(screen.getByLabelText("Period end"), { target: { value: "2026-08-31" } });
    fireEvent.click(screen.getByRole("button", { name: "Draft invoice" }));

    await waitFor(() => expect(apiFetch).toHaveBeenCalledTimes(1));
    expect(apiFetch).toHaveBeenCalledWith("/api/admin/invoices", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        client_id: 3,
        period_start: "2026-08-01",
        period_end: "2026-08-31",
      }),
    });
    await waitFor(() => expect(onCreated).toHaveBeenCalledWith(DRAFT));
  });

  it("shows the server's message when drafting conflicts", async () => {
    vi.mocked(apiFetch).mockRejectedValue(new Error("invoice INV-2026-0001 already covers 2026-08-01 to 2026-08-31"));
    render(<InvoiceForm clients={CLIENTS} onCreated={vi.fn()} />);

    fireEvent.change(screen.getByLabelText("Period start"), { target: { value: "2026-08-01" } });
    fireEvent.change(screen.getByLabelText("Period end"), { target: { value: "2026-08-31" } });
    fireEvent.click(screen.getByRole("button", { name: "Draft invoice" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("already covers");
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd frontend && npx vitest run src/components/admin/InvoiceForm.test.tsx`
Expected: FAIL with `Failed to resolve import "./InvoiceForm"`

- [ ] **Step 3: Write `InvoiceForm`**

`frontend/src/components/admin/InvoiceForm.tsx`:
```tsx
"use client";

import { useState } from "react";

import { apiFetch } from "@/lib/api";
import type { AdminClient, AdminInvoice } from "@/lib/admin-types";

export default function InvoiceForm({
  clients,
  onCreated,
}: {
  clients: AdminClient[];
  onCreated: (invoice: AdminInvoice) => void;
}) {
  const [clientId, setClientId] = useState(String(clients[0]?.id ?? ""));
  const [periodStart, setPeriodStart] = useState("");
  const [periodEnd, setPeriodEnd] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      const invoice = await apiFetch<AdminInvoice>("/api/admin/invoices", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          client_id: Number(clientId),
          period_start: periodStart,
          period_end: periodEnd,
        }),
      });
      onCreated(invoice);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Draft failed.");
    }
  }

  return (
    <form onSubmit={submit} className="flex flex-wrap items-end gap-2 text-sm">
      <label>
        <span className="block text-xs uppercase tracking-wide text-slate">Client</span>
        <select
          aria-label="Client"
          value={clientId}
          onChange={(e) => setClientId(e.target.value)}
          className="mt-1 border border-white/15 bg-surface px-2 py-1"
        >
          {clients.map((c) => (
            <option key={c.id} value={c.id}>
              {c.business_name}
            </option>
          ))}
        </select>
      </label>
      <label>
        <span className="block text-xs uppercase tracking-wide text-slate">Period start</span>
        <input
          aria-label="Period start"
          type="date"
          value={periodStart}
          onChange={(e) => setPeriodStart(e.target.value)}
          className="mt-1 border border-white/15 bg-surface px-2 py-1"
        />
      </label>
      <label>
        <span className="block text-xs uppercase tracking-wide text-slate">Period end</span>
        <input
          aria-label="Period end"
          type="date"
          value={periodEnd}
          onChange={(e) => setPeriodEnd(e.target.value)}
          className="mt-1 border border-white/15 bg-surface px-2 py-1"
        />
      </label>
      <button type="submit" className="border border-teal px-3 py-1 text-teal">
        Draft invoice
      </button>
      {error && (
        <p role="alert" className="w-full text-coral">
          {error}
        </p>
      )}
    </form>
  );
}
```

- [ ] **Step 4: Write the invoices page**

`frontend/src/app/admin/invoices/page.tsx`:
```tsx
"use client";

import { useCallback, useEffect, useState } from "react";

import InvoiceForm from "@/components/admin/InvoiceForm";
import { Table, Td, Th } from "@/components/admin/Table";
import { apiFetch } from "@/lib/api";
import { formatPKR } from "@/lib/format";
import type { AdminClient, AdminInvoice } from "@/lib/admin-types";

export default function InvoicesPage() {
  const [clients, setClients] = useState<AdminClient[]>([]);
  const [invoices, setInvoices] = useState<AdminInvoice[]>([]);
  const [amounts, setAmounts] = useState<Record<number, string>>({});
  const [dueDates, setDueDates] = useState<Record<number, string>>({});
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    apiFetch<AdminInvoice[]>("/api/admin/invoices")
      .then(setInvoices)
      .catch((e: Error) => setError(e.message));
  }, []);

  useEffect(() => {
    apiFetch<AdminClient[]>("/api/admin/clients")
      .then(setClients)
      .catch((e: Error) => setError(e.message));
    load();
  }, [load]);

  async function act(invoice: AdminInvoice, action: "confirm" | "issue" | "void") {
    setError(null);
    const body =
      action === "confirm"
        ? { confirmed_recovered_waste: amounts[invoice.id] ?? invoice.suggested_recovered_waste }
        : action === "issue"
          ? { due_date: dueDates[invoice.id] ?? invoice.due_date }
          : { note: "voided from the admin panel" };
    try {
      await apiFetch<AdminInvoice>(`/api/admin/invoices/${invoice.id}/${action}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : `${action} failed.`);
    }
  }

  return (
    <div className="space-y-4">
      <InvoiceForm clients={clients} onCreated={load} />
      {error && <p className="text-coral">{error}</p>}
      <Table>
        <thead>
          <tr>
            <Th>Number</Th>
            <Th>Period</Th>
            <Th align="right">Base</Th>
            <Th align="right">Suggested</Th>
            <Th align="right">Confirmed</Th>
            <Th align="right">Fee</Th>
            <Th align="right">Total</Th>
            <Th>Status</Th>
            <Th>Actions</Th>
          </tr>
        </thead>
        <tbody>
          {invoices.map((invoice) => (
            <tr key={invoice.id}>
              <Td>{invoice.invoice_number}</Td>
              <Td>
                {invoice.period_start} → {invoice.period_end}
              </Td>
              <Td align="right">{formatPKR(Number(invoice.base_fee))}</Td>
              <Td align="right">{formatPKR(Number(invoice.suggested_recovered_waste))}</Td>
              <Td align="right">{formatPKR(Number(invoice.confirmed_recovered_waste))}</Td>
              <Td align="right">{formatPKR(Number(invoice.performance_fee))}</Td>
              <Td align="right">{formatPKR(Number(invoice.total))}</Td>
              <Td>{invoice.status}</Td>
              <Td>
                {invoice.status === "draft" && (
                  <div className="flex flex-wrap items-center gap-1">
                    <input
                      aria-label={`Confirmed recovered waste for ${invoice.invoice_number}`}
                      value={amounts[invoice.id] ?? invoice.suggested_recovered_waste}
                      onChange={(e) =>
                        setAmounts({ ...amounts, [invoice.id]: e.target.value })
                      }
                      className="w-28 border border-white/15 bg-surface px-1 py-0.5 tabular-nums"
                    />
                    <button
                      type="button"
                      onClick={() => act(invoice, "confirm")}
                      className="border border-white/25 px-2 py-0.5"
                    >
                      Confirm
                    </button>
                    <input
                      aria-label={`Due date for ${invoice.invoice_number}`}
                      type="date"
                      value={dueDates[invoice.id] ?? invoice.due_date}
                      onChange={(e) =>
                        setDueDates({ ...dueDates, [invoice.id]: e.target.value })
                      }
                      className="border border-white/15 bg-surface px-1 py-0.5"
                    />
                    <button
                      type="button"
                      onClick={() => act(invoice, "issue")}
                      className="border border-teal px-2 py-0.5 text-teal"
                    >
                      Issue
                    </button>
                  </div>
                )}
                {invoice.status !== "void" && invoice.status !== "paid" && (
                  <button
                    type="button"
                    onClick={() => act(invoice, "void")}
                    className="mt-1 border border-coral px-2 py-0.5 text-coral"
                  >
                    Void
                  </button>
                )}
              </Td>
            </tr>
          ))}
        </tbody>
      </Table>
    </div>
  );
}
```

- [ ] **Step 5: Write the audit log page**

`frontend/src/app/admin/audit/page.tsx`:
```tsx
"use client";

import { useEffect, useState } from "react";

import { Table, Td, Th } from "@/components/admin/Table";
import { apiFetch } from "@/lib/api";
import type { AuditEntry } from "@/lib/admin-types";

export default function AuditPage() {
  const [entries, setEntries] = useState<AuditEntry[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<AuditEntry[]>("/api/admin/audit-log?limit=200")
      .then(setEntries)
      .catch((e: Error) => setError(e.message));
  }, []);

  if (error) return <p className="text-coral">{error}</p>;
  if (!entries) return <p className="text-slate">Loading…</p>;

  return (
    <Table>
      <thead>
        <tr>
          <Th>When</Th>
          <Th>Actor</Th>
          <Th>Action</Th>
          <Th>Entity</Th>
          <Th>Before</Th>
          <Th>After</Th>
        </tr>
      </thead>
      <tbody>
        {entries.map((entry) => (
          <tr key={entry.id}>
            <Td>{entry.created_at.replace("T", " ").slice(0, 19)}</Td>
            <Td>{entry.actor_user_id ?? "—"}</Td>
            <Td>{entry.action}</Td>
            <Td>
              {entry.entity_type} #{entry.entity_id}
            </Td>
            <Td>
              <pre className="max-w-xs overflow-x-auto font-mono text-xs text-slate">
                {entry.before ? JSON.stringify(entry.before) : "—"}
              </pre>
            </Td>
            <Td>
              <pre className="max-w-xs overflow-x-auto font-mono text-xs">
                {entry.after ? JSON.stringify(entry.after) : "—"}
              </pre>
            </Td>
          </tr>
        ))}
      </tbody>
    </Table>
  );
}
```

- [ ] **Step 6: Run the frontend tests**

Run: `cd frontend && npx vitest run src/components/admin`
Expected: `Test Files 2 passed`, `Tests 7 passed`

- [ ] **Step 7: Typecheck, lint, build and commit**

Run: `cd frontend && npx tsc --noEmit && npm run lint && npm run build`
Expected: clean; the route list includes `/admin`, `/admin/audit`, `/admin/clients`, `/admin/clients/[id]`, `/admin/invoices`, `/admin/runs`.
```bash
git add frontend/src/components/admin/InvoiceForm.tsx frontend/src/components/admin/InvoiceForm.test.tsx frontend/src/app/admin/invoices frontend/src/app/admin/audit
git commit -m "feat(admin-ui): invoice drafting/confirm/issue/void and the audit log table" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 11: Stage 6 wrap-up — no migration, green suites, docs

**Files:**
- Modify: `README.md`
- Modify: `.github/workflows/ci.yml` (only if the frontend job does not already run `vitest`)

**Interfaces:** none new.

- [ ] **Step 1: Prove there is no schema change**

Run:
```bash
cd backend && .venv/Scripts/python -m alembic upgrade head && .venv/Scripts/python -m alembic check
```
Expected: `No new upgrade operations detected.`
Stage 6 adds no column and no table — `audit_log` and `invoices` came from Stage 0's `55eb15843c97_initial_schema`. If `alembic check` reports operations, a model was edited by mistake: revert that edit rather than generating a revision.

- [ ] **Step 2: Run both suites end to end**

Run: `cd backend && .venv/Scripts/ruff check . && .venv/Scripts/ruff format --check . && .venv/Scripts/python -m pytest -q`
Expected: `All checks passed!`, formatter clean, all tests pass.

Run: `cd frontend && npx vitest run && npx tsc --noEmit && npm run lint && npm run build`
Expected: all green.

- [ ] **Step 3: Make CI run the frontend unit tests**

If `.github/workflows/ci.yml`'s frontend job has no vitest step, add it after `npm ci`:
```yaml
      - run: npx vitest run
```

- [ ] **Step 4: Document the admin panel in the README**

Append to `README.md` under "Tests":
````markdown
### Admin panel (Stage 6)

Create an operator account, then sign in at `/login` and open `/admin`:

```bash
cd backend
python scripts/create_admin.py --email you@example.com --password "a-long-password"
```

- `/admin/runs` — approval queue. A client cannot see a report until its run is approved here.
- `/admin/clients/<id>` — base fee, performance fee %, and per-client `PipelineConfig` overrides
  (unknown keys are refused with 422).
- `/admin/invoices` — draft for a client and period, confirm the recovered-waste figure, then
  issue or void. The suggestion is the before/after comparison from `docs/PLAN.md` §1 #5; the
  admin always confirms it.
- `/admin/audit` — every approve, reject, client update and invoice action, with before/after JSON.
````

- [ ] **Step 5: Commit**

```bash
git add README.md .github/workflows/ci.yml
git commit -m "docs(admin): document the admin panel and run vitest in CI" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

## Stage 6 exit checklist (from `docs/PLAN.md` §6)

- [ ] Clients list and detail with fees and per-client threshold overrides — Tasks 2, 8.
- [ ] Approval queue showing run numbers, flagged segments and the config snapshot, with approve/reject plus a note — Tasks 3, 6, 9.
- [ ] Invoice drafting with a suggested recovered-waste figure the admin can edit and confirm — Tasks 4, 5, 10.
- [ ] Audit log view — Tasks 1, 6, 10.
- [ ] No animation, dense tables — Tasks 8–10 (hairline dividers, no Framer Motion, no hero).
- [ ] **Approve/reject and fee confirmation each write an audit entry** — `tests/services/test_admin_runs.py`, `tests/services/test_billing_invoices.py`, `tests/api/test_admin_api.py`.
- [ ] **Clients see a run only after approval** — `test_approving_a_run_is_what_lets_the_client_see_the_report` and `test_a_rejected_run_stays_invisible_to_the_client`.
- [ ] Every `/api/admin` route is 403 for a client, 401 for an anonymous caller — `tests/api/test_admin_permissions.py`.
- [ ] No Alembic migration — Task 11 Step 1.

## Decisions

1. **Invoice-number year is `period_end.year`**, not the drafting date's year, so a December period drafted in January stays in the right series and tests are deterministic.
2. **The number is `max(existing for that year) + 1`.** Suffixes are zero-padded to 4 digits so a text `MAX()` equals the numeric maximum. The race between two simultaneous drafters is documented in a comment in `_next_invoice_number` and is left to the `UNIQUE` constraint on `invoices.invoice_number`; SQLite has no `SELECT ... FOR UPDATE` and the MVP has one operator.
3. **A draft sets `confirmed_recovered_waste = 0` and computes `performance_fee`/`total` from the *suggested* amount** so the admin sees the proposed bill immediately, while "confirmed" stays literally true until a human confirms. `confirm_invoice` recomputes both from the amount the admin submits.
4. **`issue_invoice` refuses an unconfirmed invoice** (409 "confirm the performance fee before issuing") — `docs/PLAN.md` §1 #5 requires admin confirmation before a fee reaches a client, and §7 step 2 has the admin review the draft before issuing.
5. **`draft_invoice` sets `due_date = period_end + 14 days`** because the column is `NOT NULL`; `issue_invoice(due_date)` overwrites it with the real one.
6. **`approve_run` requires `status == "done"`; `reject_run` does not.** Approving is what exposes a report, and a `failed` or `running` run has none; rejecting a failed run is a legitimate way to clear the queue.
7. **A run can be reviewed once.** A second approve/reject is 409, so the audit trail has exactly one decision per run.
8. **Drafting a second non-void invoice for the same client and period is 409**, which stops accidental double-billing; voiding the first one frees the period.
9. **Schema class names are `AdminClientOut` and `AdminInvoiceOut`**, not `ClientOut`/`InvoiceOut`, to avoid colliding with Stage 2's `schemas/auth.ClientOut` and Stage 7's `InvoiceOut`. `ClientPatch` keeps its `INTERFACES.md` name exactly.
10. **`GET /api/admin/invoices`, `audit.list_entries`, `audit.snapshot` and `billing.list_invoices` are additions to `INTERFACES.md`**, declared in this plan's header; nothing in the contract is renamed.
11. **The void reason lives in the audit row's `after["note"]`** because `audit_log` has no note column and `invoices` has no note column either (`docs/PLAN.md` §4).
12. **Services own the transaction** (mutate → flush → audit → single commit) rather than the router, so the "audit entry in the same transaction" rule cannot be forgotten at a call site.
13. **Admin pages are client components over `apiFetch`, with only `layout.tsx` server-side.** The layout is the security boundary (it re-checks `role === "admin"` against `/api/auth/me` before anything renders); the pages are plain fetch-and-render tables, and `RunQueueRow`/`InvoiceForm` stay pure so Vitest can test them without a network.

## Self-review notes

- **Spec coverage** (`docs/PLAN.md` §6): clients list/detail with fees and overrides ✔ (Tasks 2, 8); approval queue with run numbers, flagged segments, config snapshot, approve/reject + note ✔ (Tasks 3, 6, 9); invoice drafting with an editable, confirmable suggestion ✔ (Tasks 4, 5, 10); audit log view ✔ (Tasks 1, 6, 10); "no animation, dense tables" ✔ (Tasks 8–10); both "Done when" clauses have named tests. §5 admin routes: all ten non-payment paths exist and Task 6 Step 8 asserts the exact set. §1 #5 recovered-waste definition ✔ (Task 4, hand-computed 22,000 + 1,000 = 23,000). §1 #6 Decimal ✔. §4 `audit_log`/`invoices` columns are used as defined; no new column. §7 #2 admin-confirmed ✔ (Decisions 3, 4). Payments, payment methods and client-facing invoice views are deliberately out of scope (Stage 7).
- **Placeholder scan:** no TBD/TODO; every code step carries full code; the two "if Stage 3/4 already did this" steps name exactly what to check and what to write if it did not.
- **Type consistency:** `ClientPatch` is defined in Task 2 and used in Tasks 2 and 6; `RunAdminOut`/`FlaggedSegmentOut`/`RunDimensionOut` are defined in Task 6 Step 3 and consumed by `serialize_run` (Step 4), the router (Step 5), `admin-types.ts` (Task 8) and `RunQueueRow` (Task 9) with the same field names; `AdminInvoiceOut`'s fields match `AdminInvoice` in `admin-types.ts` and the assertions in Tasks 5, 7 and 10; `audit.record`'s parameter order is identical in all four call sites; `calculate_fee` is used with the `FeeBreakdown` fields Stage 1 defines (`base_fee`, `performance_fee`, `total`, `recovered_waste`).
- **Known cross-stage assumption:** every test fixture and row builder this stage uses already exists, per `INTERFACES.md` §"Test-fixture contract": `api`, `db`, `admin_client` and `admin_row` in `tests/api/conftest.py`, and `login_as`, `user_for`, `make_client`, `make_admin`, `make_upload`, `make_run`, `make_approved_run` in `tests/api/helpers.py` (Stages 2, 3 and 5). This stage creates no test-helper module of its own, defines no second `api` fixture, and changes no builder signature — `make_client`'s `base_fee` / `performance_fee_pct` / `config_overrides` and `make_run`'s `created_at` / `headline_waste` / `segments` keyword arguments are already there. Step 5 verifies that with one grep before any test is written.
