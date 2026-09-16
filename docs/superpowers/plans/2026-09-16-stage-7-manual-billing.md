# Stage 7 — Billing with Manual Payments Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A client can see an issued invoice, download its PDF with the accounts to pay into, report the transaction ID of a payment they made from their own wallet or bank app, and an admin can confirm or reject that payment — with partial payments tracked, reused transaction IDs refused, and every decision audited.

**Architecture:** Money never moves inside our code; we record *claims* and an admin *confirms* them. All of that sits behind `PaymentProvider` (`app/payments/base.py`), of which `ManualProvider` is the only implementation today — adding a gateway later (`docs/PLAN.md` §9) is a new class plus a `Settings.payment_provider` value, with no change to services, routers or the frontend. Invoice arithmetic lives in `app/services/payments.py` and works in `Decimal` only; the DB constraint `uq_payments_method_ref` is the single source of truth for "this transaction ID was already used", surfaced as a 409.

**Tech Stack:** FastAPI 0.141, SQLAlchemy 2.0, Pydantic v2, ReportLab (invoice PDF), pypdf (PDF text assertions in tests), pytest 9; Next.js 16 App Router + Tailwind v4 + Vitest + Testing Library on the frontend.

**Spec:** `docs/PLAN.md` §6 "Stage 7 — Billing with manual payments" (authoritative for every rule and every *Done when* bullet), §5 "API surface" (Billing + Admin routes), §4 (`invoices`, `payment_methods`, `payments`, `audit_log`, tenant isolation), §9 (the future gateway this interface must accommodate); and `docs/superpowers/plans/INTERFACES.md` (Stage 7 block — names used **verbatim**; plus Stage 2 `CurrentClient`/`CurrentAdmin`, Stage 3 `get_storage()`, Stage 5 ReportLab conventions, Stage 6 `services/billing.py` + `audit.record`).

**Depends on (must already be merged):** Stage 2 (`app/core/deps.py`, `app/services/auth.py`, `POST /api/auth/login`), Stage 3 (`app/services/storage.py` with `get_storage()`), Stage 5 (ReportLab + pypdf pinned in requirements), Stage 6 (`app/routers/admin.py`, `app/services/audit.py`, `app/services/billing.py`).

**Interface additions** (declared per the rule in `INTERFACES.md`: "A plan may add to this list … but never rename what is here"). Nothing existing is renamed; this stage adds:
- `Settings.payment_provider: str = "manual"`, `Settings.max_proof_mb: int = 5`
- `app/payments/__init__.py` hosts `get_payment_provider()`
- `app/schemas/billing.py` also defines `MethodType`, `PaymentMethodPatch`, `ReviewRequest`, `RejectRequest`, `AdminPaymentOut`, and the builders `invoice_out()` / `admin_payment_out()`
- `app/services/payments.py` also defines `validate_proof()`, `list_payments()`, `list_payment_methods()`, `create_payment_method()`, `update_payment_method()`, `PaymentQueueRow`, `CLIENT_VISIBLE_STATUSES`, `PAYABLE_STATUSES`, `METHOD_LABELS`
- `list_pending_payments(session, status_filter="pending")` returns `list[PaymentQueueRow]` (INTERFACES gives it no return type)
- route `GET /api/admin/payments/{payment_id}/proof` (the admin queue needs a link to the private proof file)
- frontend `src/lib/billing.ts` with `isOverdue()`, `amountDue()`, `METHOD_LABELS`, `STATUS_LABELS`, `STATUS_PILL`

## Global Constraints

Copied from `docs/PLAN.md` §6 "Stage 7 — Billing with manual payments", *Rules*. Every task's requirements implicitly include all of these.

- **Only the admin can mark money as received.** A client submission never marks an invoice paid on its own.
- A transaction ID can't be used twice (unique per method). The DB constraint `uq_payments_method_ref` on `(method_type, transaction_ref)` enforces it; the API turns the resulting `IntegrityError` into **409**, never a 500.
- Screenshots go to private storage, limited to images or PDF and a size cap — **PNG / JPEG / PDF only, ≤ 5 MB**, written through `get_storage()` under `proofs/{client_id}/{payment_id}.{ext}`, never served from a public URL.
- Amounts use `Decimal`. No `float` touches an invoice, a payment, or a PDF.
- Every confirm, reject and void writes to `audit_log` — `audit.record(...)` with the actions `payment.confirm`, `payment.reject`, `invoice.void` (Stage 6's `void_invoice`), `payment_method.create`, `payment_method.update`.
- Overdue invoices (past the due date) are flagged in the admin panel. Nothing is suspended automatically in the MVP. Overdue = `due_date < today` **and** status not in `("paid", "void")`.
- Payment logic sits behind a `PaymentProvider` interface. `ManualProvider` is built now, so adding an automatic gateway later (see §9) is a new provider class, not a rewrite.
- Partial payments are allowed and tracked (§6 step 6: "The invoice becomes **paid** once confirmed payments cover the total. Partial payments are allowed and tracked.").
- Tenant isolation (§4): client endpoints never accept a `client_id` from the request — it comes from `CurrentClient`; another client's record returns **404**, not 403.
- Clients never see `draft` invoices. Client-visible statuses are exactly `issued`, `payment_submitted`, `paid`, `void`.
- Python style: ruff line-length 100, `select = ["E","F","I","B","UP"]`. Run `.venv/Scripts/ruff check . && .venv/Scripts/ruff format .` before every commit.
- Windows Git Bash: backend commands run as `cd backend && .venv/Scripts/python -m ...`, never a bare `python`.
- Every commit carries the project trailer as a **second** `-m`: `-m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"`.
- Billing pages are **working views**: no hero, no decorative animation. Framer Motion only for a user-triggered expand, and this stage needs none.

---

## File Structure

```
backend/
├── app/
│   ├── core/settings.py              # MODIFY: payment_provider, max_proof_mb
│   ├── main.py                       # MODIFY: include_router(billing.router)
│   ├── payments/
│   │   ├── __init__.py               # NEW: get_payment_provider()
│   │   ├── base.py                   # NEW: PaymentInstruction, PaymentProvider Protocol
│   │   └── manual.py                 # NEW: ManualProvider
│   ├── schemas/billing.py            # NEW: every request/response shape for billing
│   ├── services/payments.py          # NEW: invoice + payment lifecycle, proof validation, invoice PDF
│   └── routers/
│       ├── billing.py                # NEW: /api/billing/* (client)
│       └── admin.py                  # MODIFY: /api/admin/payments*, /api/admin/payment-methods
└── tests/
    └── api/
        ├── helpers.py                    # MODIFY (Stages 2-3-5 built it): + make_invoice,
        │                                 #   make_method, PNG_BYTES/JPEG_BYTES/PDF_BYTES
        ├── test_payments_provider.py     # NEW: Task 1 + Task 2
        ├── test_payments_service.py      # NEW: Task 3
        ├── test_invoice_pdf.py           # NEW: Task 4
        ├── test_billing_routes.py        # NEW: Task 5
        ├── test_admin_payments_routes.py # NEW: Task 6
        └── test_billing_e2e.py           # NEW: Task 7

frontend/
├── vitest.config.ts / vitest.setup.ts   # only if Stage 4 did not add them
├── src/lib/billing.ts                   # NEW: isOverdue, amountDue, labels
├── src/lib/billing.test.ts              # NEW
├── src/lib/types.ts                     # MODIFY: Invoice, Payment, PaymentMethod, PaymentInstruction
├── src/lib/api.ts                       # MODIFY: don't force a JSON Content-Type on FormData
├── src/components/billing/
│   ├── StatusPill.tsx  InvoiceTable.tsx  PaymentInstructions.tsx
│   ├── PaymentHistory.tsx  PaymentForm.tsx  PaymentForm.test.tsx  InvoiceDetail.tsx
├── src/components/admin/PaymentQueue.tsx  PaymentMethodTable.tsx
└── src/app/
    ├── dashboard/billing/page.tsx
    ├── admin/payments/page.tsx
    └── admin/payment-methods/page.tsx
```

**No Alembic migration is needed.** Every column this stage writes — `invoices.amount_paid`, `invoices.status`, all of `payment_methods`, all of `payments` including `proof_file_path` and the `uq_payments_method_ref` unique constraint — already exists from Stage 0's initial revision (see `backend/app/models/billing.py`). Task 11 *proves* it with `alembic check` instead of assuming it.

---

### Task 1: Settings, `PaymentInstruction`, the `PaymentProvider` Protocol and the billing schemas

**Files:**
- Modify: `backend/app/core/settings.py`
- Create: `backend/app/payments/__init__.py`, `backend/app/payments/base.py`
- Create: `backend/app/schemas/billing.py`
- Modify: `backend/tests/api/helpers.py` (Stage 2 created it; Stages 3 and 5 appended to it)
- Test: `backend/tests/api/test_payments_provider.py` (schemas + settings; the provider half lands in Task 2)

**Interfaces:**
- Consumes: `Settings` / `get_settings()` (`app/core/settings.py`), `Invoice`, `Client`, `Payment`, `PaymentMethod`, `User` (`app.models`), `signup_client(session, email, password, business_name)` and `create_admin(session, email, password)` (`app/services/auth.py`, Stage 2).
- Produces:
  ```python
  # app/core/settings.py
  Settings.payment_provider: str = "manual"
  Settings.max_proof_mb: int = 5

  # app/payments/base.py
  class PaymentInstruction(BaseModel):
      method_type: str; account_title: str; account_identifier: str; instructions: str | None
  @runtime_checkable
  class PaymentProvider(Protocol):
      name: str
      def instructions_for(self, session, invoice) -> list[PaymentInstruction]: ...
      def submit(self, session, client, invoice, submission, proof, proof_ext) -> Payment: ...

  # app/schemas/billing.py
  MethodType = Literal["jazzcash","easypaisa","nayapay","raast","bank_iban"]
  CLIENT_VISIBLE_STATUSES = ("issued","payment_submitted","paid","void") ; PAYABLE_STATUSES = ("issued","payment_submitted")
  PaymentSubmission(method_type: MethodType, transaction_ref: str(1..80), amount: Decimal > 0, paid_at: date)
  PaymentOut(id, method_type, transaction_ref, amount, paid_at, status, review_note, reviewed_at, created_at, has_proof)
  InvoiceOut(id, invoice_number, period_start, period_end, due_date, base_fee, confirmed_recovered_waste,
             performance_fee, total, amount_paid, status, issued_at, created_at,
             payments: list[PaymentOut], instructions: list[PaymentInstruction], amount_due, is_overdue)
  AdminPaymentOut(PaymentOut + client_id, business_name, invoice_id, invoice_number, invoice_total,
                  invoice_due_date, invoice_status, invoice_is_overdue)
  PaymentMethodIn / PaymentMethodOut / PaymentMethodPatch / ReviewRequest / RejectRequest
  invoice_out(invoice, payments=(), instructions=()) -> InvoiceOut
  admin_payment_out(payment, invoice, client, today=None) -> AdminPaymentOut

  # tests/api/helpers.py  (appended; nothing existing is renamed or redefined)
  PNG_BYTES ; JPEG_BYTES ; PDF_BYTES
  make_invoice(db, client, *, status="issued", total=Decimal("19600.00"), number="INV-2026-0001",
               base_fee, recovered, pct, due_date, amount_paid) -> Invoice
  make_method(db, type="jazzcash", identifier="03001234567", *, account_title, instructions,
              is_active, sort_order) -> PaymentMethod
  ```
  Everything else this stage's tests need is already in place per `INTERFACES.md`
  §"Test-fixture contract": the fixtures `db`, `api`, `client_a`, `client_b`, `client_a_row`,
  `client_b_row`, `admin_client`, `admin_row` and the builders `login_as`, `user_for`,
  `make_client`, `make_admin`. This stage creates **no** test module of its own and no
  second app factory or login helper: it appends two builders and reuses everything else.
  `api_env` (autouse, `tests/api/conftest.py`) already points `STORAGE_ROOT` at each test's own
  `tmp_path / "storage"` and clears the `get_settings` cache before and after every test, so no
  test here touches storage settings by hand.

- [ ] **Step 1: Confirm ReportLab and pypdf are installed (Stage 5 pinned them)**

Run: `cd backend && .venv/Scripts/python -m pip show reportlab pypdf | grep -E "^(Name|Version)"`
Expected: four lines — `Name: reportlab`, `Version: 4.x.x`, `Name: pypdf`, `Version: 6.x.x`.

If either prints `WARNING: Package(s) not found`, install and pin it (ReportLab is a runtime dependency, pypdf a test-only one):
```bash
cd backend && .venv/Scripts/python -m pip install reportlab pypdf
.venv/Scripts/python -m pip show reportlab | sed -n 's/^Version: /reportlab==/p' >> requirements.txt
.venv/Scripts/python -m pip show pypdf | sed -n 's/^Version: /pypdf==/p' >> requirements-dev.txt
```

- [ ] **Step 2: Write the failing test**

`backend/tests/api/__init__.py`: an empty file (create only if it does not already exist — Stage 3 may have added it).

`backend/tests/api/test_payments_provider.py`:
```python
import subprocess
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.settings import get_settings
from app.payments.base import PaymentInstruction, PaymentProvider
from app.schemas.billing import PaymentSubmission


def test_payment_provider_defaults_to_manual():
    assert get_settings().payment_provider == "manual"
    assert get_settings().max_proof_mb == 5


def test_payment_instruction_carries_the_account_a_client_pays_into():
    inst = PaymentInstruction(
        method_type="jazzcash",
        account_title="Ali Raza",
        account_identifier="0300-1234567",
        instructions="Send from your JazzCash app.",
    )
    assert inst.model_dump() == {
        "method_type": "jazzcash",
        "account_title": "Ali Raza",
        "account_identifier": "0300-1234567",
        "instructions": "Send from your JazzCash app.",
    }


def test_protocol_accepts_any_class_with_the_two_methods():
    class FakeGateway:
        name = "fake"

        def instructions_for(self, session, invoice):
            return []

        def submit(self, session, client, invoice, submission, proof, proof_ext):
            raise NotImplementedError

    assert isinstance(FakeGateway(), PaymentProvider)
    assert not isinstance(object(), PaymentProvider)


def test_submission_requires_a_positive_decimal_amount_and_a_known_method():
    ok = PaymentSubmission(
        method_type="easypaisa",
        transaction_ref="EP-77001",
        amount=Decimal("10000.00"),
        paid_at=date(2026, 10, 2),
    )
    assert ok.amount == Decimal("10000.00")
    for bad in (
        {"method_type": "easypaisa", "transaction_ref": "x", "amount": Decimal("0"), "paid_at": date(2026, 10, 2)},
        {"method_type": "easypaisa", "transaction_ref": "", "amount": Decimal("1"), "paid_at": date(2026, 10, 2)},
        {"method_type": "paypal", "transaction_ref": "x", "amount": Decimal("1"), "paid_at": date(2026, 10, 2)},
    ):
        with pytest.raises(ValidationError):
            PaymentSubmission(**bad)


def test_schemas_can_be_imported_before_the_payments_package():
    """app.schemas.billing imports app.payments.base, whose package imports app.schemas.billing back.

    Both sides use `from __future__ import annotations` + TYPE_CHECKING, so the cycle never runs at
    import time. This test fails loudly if someone converts either import into a runtime one.
    """
    backend = Path(__file__).resolve().parents[2]
    for first in ("app.schemas.billing", "app.payments"):
        result = subprocess.run(
            [sys.executable, "-c", f"import {first}"], cwd=backend, capture_output=True, text=True
        )
        assert result.returncode == 0, result.stderr
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `cd backend && .venv/Scripts/python -m pytest tests/api/test_payments_provider.py -v`
Expected: a collection error — `ModuleNotFoundError: No module named 'app.payments'`.

- [ ] **Step 4: Add the settings**

In `backend/app/core/settings.py`, add two fields directly after `secret_key`. Keep `payment_provider` a plain `str`, not a `Literal`, so an unknown value produces the readable `ValueError` from `get_payment_provider()` instead of a settings crash at import time:
```python
    # --- payments (docs/PLAN.md section 6, Stage 7) ---
    payment_provider: str = "manual"
    max_proof_mb: int = 5
```

- [ ] **Step 5: Write `app/payments/base.py`**

`backend/app/payments/base.py`:
```python
"""The seam between billing and however the money actually arrives.

`ManualProvider` (this stage) records a transaction ID the client typed in after paying from
their own wallet or bank app. An automatic gateway later (docs/PLAN.md section 9) is a NEW class
implementing this Protocol — nothing in app/services or app/routers changes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from pydantic import BaseModel

if TYPE_CHECKING:  # import-cycle guard: app.schemas.billing imports PaymentInstruction from here
    from sqlalchemy.orm import Session

    from app.models import Client, Invoice, Payment
    from app.schemas.billing import PaymentSubmission


class PaymentInstruction(BaseModel):
    """One account a client can pay into. Rendered on the billing page and in the invoice PDF."""

    method_type: str
    account_title: str
    account_identifier: str
    instructions: str | None = None


@runtime_checkable
class PaymentProvider(Protocol):
    """Everything billing needs to know about a way of taking money."""

    name: str

    def instructions_for(self, session: Session, invoice: Invoice) -> list[PaymentInstruction]:
        """The accounts to show on this invoice, in display order."""
        ...

    def submit(
        self,
        session: Session,
        client: Client,
        invoice: Invoice,
        submission: PaymentSubmission,
        proof: bytes | None,
        proof_ext: str | None,
    ) -> Payment:
        """Record a client's claim that they paid. NEVER marks the invoice paid — only an admin does."""
        ...
```

`backend/app/payments/__init__.py`: create it empty for now. Task 2 puts `get_payment_provider()` in it.

- [ ] **Step 6: Write `app/schemas/billing.py`**

`backend/app/schemas/billing.py`:
```python
"""Request/response shapes for billing. Money is Decimal everywhere (docs/PLAN.md section 1 #6)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.payments.base import PaymentInstruction

MethodType = Literal["jazzcash", "easypaisa", "nayapay", "raast", "bank_iban"]

# Clients never see drafts (docs/PLAN.md section 6, Stage 7, step 3).
CLIENT_VISIBLE_STATUSES: tuple[str, ...] = ("issued", "payment_submitted", "paid", "void")
# A client may only report a payment against these.
PAYABLE_STATUSES: tuple[str, ...] = ("issued", "payment_submitted")


def _overdue(status: str, due_date: date, today: date) -> bool:
    return status not in ("paid", "void") and due_date < today


class PaymentSubmission(BaseModel):
    """What the client types in after paying from their own app."""

    method_type: MethodType
    transaction_ref: str = Field(min_length=1, max_length=80)
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    paid_at: date


class PaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    method_type: str
    transaction_ref: str
    amount: Decimal
    paid_at: date
    status: str
    review_note: str | None = None
    reviewed_at: datetime | None = None
    created_at: datetime
    # Read from the model but never serialised: the proof path is private (docs/PLAN.md section 6).
    proof_file_path: str | None = Field(default=None, exclude=True)

    @computed_field
    @property
    def has_proof(self) -> bool:
        return self.proof_file_path is not None


class InvoiceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    invoice_number: str
    period_start: date
    period_end: date
    due_date: date
    base_fee: Decimal
    confirmed_recovered_waste: Decimal
    performance_fee: Decimal
    total: Decimal
    amount_paid: Decimal
    status: str
    issued_at: datetime | None = None
    created_at: datetime
    payments: list[PaymentOut] = []
    instructions: list[PaymentInstruction] = []

    @computed_field
    @property
    def amount_due(self) -> Decimal:
        return self.total - self.amount_paid

    @computed_field
    @property
    def is_overdue(self) -> bool:
        return _overdue(self.status, self.due_date, date.today())


class AdminPaymentOut(PaymentOut):
    client_id: int
    business_name: str
    invoice_id: int
    invoice_number: str
    invoice_total: Decimal
    invoice_due_date: date
    invoice_status: str
    invoice_is_overdue: bool


class PaymentMethodIn(BaseModel):
    type: MethodType
    account_title: str = Field(min_length=1, max_length=120)
    account_identifier: str = Field(min_length=1, max_length=60)
    instructions: str | None = Field(default=None, max_length=1000)
    is_active: bool = True
    sort_order: int = 0


class PaymentMethodPatch(BaseModel):
    """Only the fields actually sent are applied — see model_dump(exclude_unset=True) in the service."""

    account_title: str | None = Field(default=None, min_length=1, max_length=120)
    account_identifier: str | None = Field(default=None, min_length=1, max_length=60)
    instructions: str | None = Field(default=None, max_length=1000)
    is_active: bool | None = None
    sort_order: int | None = None


class PaymentMethodOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: str
    account_title: str
    account_identifier: str
    instructions: str | None = None
    is_active: bool
    sort_order: int


class ReviewRequest(BaseModel):
    note: str | None = Field(default=None, max_length=1000)


class RejectRequest(BaseModel):
    """A rejection must say why — the client reads this note and submits again."""

    note: str = Field(min_length=1, max_length=1000)


def invoice_out(invoice, payments=(), instructions=()) -> InvoiceOut:
    """Build an InvoiceOut. The Invoice model has no relationships, so both lists are passed in."""
    base = InvoiceOut.model_validate(invoice)
    return base.model_copy(
        update={
            "payments": [PaymentOut.model_validate(p) for p in payments],
            "instructions": list(instructions),
        }
    )


def admin_payment_out(payment, invoice, client, today: date | None = None) -> AdminPaymentOut:
    today = today or date.today()
    base = PaymentOut.model_validate(payment).model_dump(exclude={"has_proof"})
    return AdminPaymentOut(
        **base,
        proof_file_path=payment.proof_file_path,
        client_id=client.id,
        business_name=client.business_name,
        invoice_id=invoice.id,
        invoice_number=invoice.invoice_number,
        invoice_total=invoice.total,
        invoice_due_date=invoice.due_date,
        invoice_status=invoice.status,
        invoice_is_overdue=_overdue(invoice.status, invoice.due_date, today),
    )
```

- [ ] **Step 7: Add the two billing builders to the shared helpers**

Append to `backend/tests/api/helpers.py`. Stage 2 created it (`TEST_PASSWORD`, `login_as`,
`user_for`, `make_client`, `make_admin`), Stage 3 appended `make_upload` / `make_run` /
`CONFIG_SNAPSHOT` and Stage 5 appended `make_approved_run`; **keep every one of those and
redefine none of them.** `ruff format` folds the new imports into the file's single import block.
```python
from app.models import Invoice, PaymentMethod
from app.models._types import utcnow

# Smallest byte strings that still start with the real magic numbers.
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"0" * 64
JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"0" * 64
PDF_BYTES = b"%PDF-1.7\n" + b"0" * 64


def make_invoice(
    db: Session,
    client: Client,
    *,
    status: str = "issued",
    total: Decimal = Decimal("19600.00"),
    number: str = "INV-2026-0001",
    base_fee: Decimal = Decimal("15000.00"),
    recovered: Decimal = Decimal("23000.00"),
    pct: Decimal = Decimal("20.00"),
    due_date: date = date(2026, 10, 7),
    amount_paid: Decimal = Decimal("0.00"),
) -> Invoice:
    """A committed invoice for `client`, September 2026 by default.

    The defaults agree with each other: base 15,000 + 20% of 23,000 recovered waste = a 4,600
    performance fee, so `total` is 19,600. If you override `base_fee`, `recovered` or `pct`,
    pass a matching `total` so the row stays internally consistent.
    """
    performance_fee = (recovered * pct / Decimal("100")).quantize(Decimal("0.01"))
    invoice = Invoice(
        invoice_number=number,
        client_id=client.id,
        period_start=date(2026, 9, 1),
        period_end=date(2026, 9, 30),
        due_date=due_date,
        base_fee=base_fee,
        suggested_recovered_waste=recovered,
        confirmed_recovered_waste=recovered,
        performance_fee=performance_fee,
        total=total,
        amount_paid=amount_paid,
        status=status,
        issued_at=None if status == "draft" else utcnow(),
    )
    db.add(invoice)
    db.commit()
    db.refresh(invoice)
    return invoice


def make_method(
    db: Session,
    type: str = "jazzcash",
    identifier: str = "03001234567",
    *,
    account_title: str = "Ali Raza",
    instructions: str | None = "Send from your JazzCash app to this wallet.",
    is_active: bool = True,
    sort_order: int = 0,
) -> PaymentMethod:
    """A committed PaymentMethod row. `type` shadows the builtin only inside this function."""
    method = PaymentMethod(
        type=type,
        account_title=account_title,
        account_identifier=identifier,
        instructions=instructions,
        is_active=is_active,
        sort_order=sort_order,
    )
    db.add(method)
    db.commit()
    db.refresh(method)
    return method
```

No settings-cache fixture is needed: `api_env` in `backend/tests/api/conftest.py` is autouse for
everything under `tests/api/` and already calls `get_settings.cache_clear()` before and after
each test, which is what the `PAYMENT_PROVIDER` monkeypatching in this stage relies on.

- [ ] **Step 8: Run the tests to verify they pass**

Run: `cd backend && .venv/Scripts/python -m pytest tests/api/test_payments_provider.py -v`
Expected: `5 passed`.

- [ ] **Step 9: Lint and commit**

Run: `cd backend && .venv/Scripts/ruff check . && .venv/Scripts/ruff format .`
```bash
git add backend/app/core/settings.py backend/app/payments backend/app/schemas/billing.py backend/tests/api
git commit -m "feat(billing): PaymentProvider protocol and billing schemas" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 2: `ManualProvider` and `get_payment_provider()`

**Files:**
- Create: `backend/app/payments/manual.py`
- Modify: `backend/app/payments/__init__.py`
- Test: `backend/tests/api/test_payments_provider.py` (append)

**Interfaces:**
- Consumes: `PaymentInstruction`, `PaymentProvider`, `PaymentSubmission` (Task 1); `get_storage()` with `save(key, data) -> str` / `read(key) -> bytes` (Stage 3); models `PaymentMethod`, `Payment`, `Invoice`, `Client`.
- Produces:
  ```python
  # app/payments/manual.py
  class ManualProvider:
      name = "manual"
      def instructions_for(self, session, invoice) -> list[PaymentInstruction]   # active rows, sort_order then id
      def submit(self, session, client, invoice, submission, proof=None, proof_ext=None) -> Payment
      #   creates Payment(status="pending", provider="manual"); sets invoice.status = "payment_submitted";
      #   raises HTTPException(409) on a duplicate (method_type, transaction_ref);
      #   writes proof to "proofs/{client_id}/{payment_id}.{ext}" via get_storage()
  # app/payments/__init__.py
  get_payment_provider() -> PaymentProvider     # ValueError("unknown payment provider: X") otherwise
  ```

- [ ] **Step 1: Write the failing tests**

Add these imports to the top of `backend/tests/api/test_payments_provider.py` (alongside the Task 1 imports):
```python
from fastapi import HTTPException
from sqlalchemy import select

from app.models import Invoice, Payment
from app.payments import get_payment_provider
from app.payments.manual import ManualProvider
from app.services.storage import get_storage
from tests.api.helpers import PNG_BYTES, make_client, make_invoice, make_method
```

Append to `backend/tests/api/test_payments_provider.py`:
```python
def _submission(ref="JC-90001", amount="10000.00", method="jazzcash"):
    return PaymentSubmission(
        method_type=method, transaction_ref=ref, amount=Decimal(amount), paid_at=date(2026, 10, 2)
    )


def test_manual_provider_satisfies_the_protocol():
    assert isinstance(ManualProvider(), PaymentProvider)
    assert ManualProvider().name == "manual"


def test_get_payment_provider_returns_the_manual_one_by_default():
    assert isinstance(get_payment_provider(), ManualProvider)


def test_get_payment_provider_rejects_an_unknown_name(monkeypatch):
    monkeypatch.setenv("PAYMENT_PROVIDER", "stripe")
    get_settings.cache_clear()
    with pytest.raises(ValueError, match="unknown payment provider: stripe"):
        get_payment_provider()


def test_instructions_are_the_active_methods_in_sort_order(db):
    client = make_client(db, "owner-a@example.com", "Karachi Kicks")
    invoice = make_invoice(db, client)
    make_method(db, "jazzcash", "0300-1234567", sort_order=2)
    make_method(db, "raast", "PK36SCBL0000001123456702", sort_order=1)
    make_method(db, "nayapay", "0333-9999999", sort_order=0, is_active=False)

    instructions = ManualProvider().instructions_for(db, invoice)

    assert [i.method_type for i in instructions] == ["raast", "jazzcash"]
    assert instructions[0].account_identifier == "PK36SCBL0000001123456702"


def test_submit_records_a_pending_payment_and_moves_the_invoice_to_payment_submitted(db):
    client = make_client(db, "owner-a@example.com", "Karachi Kicks")
    invoice = make_invoice(db, client)

    payment = ManualProvider().submit(db, client, invoice, _submission(), None, None)

    assert payment.status == "pending"
    assert payment.provider == "manual"
    assert payment.amount == Decimal("10000.00")
    assert payment.client_id == client.id
    assert payment.proof_file_path is None
    reloaded = db.get(Invoice, invoice.id)
    assert reloaded.status == "payment_submitted"
    # The rule that matters: a client submission never marks an invoice paid.
    assert reloaded.amount_paid == Decimal("0.00")


def test_the_same_transaction_ref_cannot_be_used_twice_for_one_method(db):
    client = make_client(db, "owner-a@example.com", "Karachi Kicks")
    invoice = make_invoice(db, client)
    provider = ManualProvider()
    provider.submit(db, client, invoice, _submission("JC-90001"), None, None)

    with pytest.raises(HTTPException) as exc:
        provider.submit(db, client, invoice, _submission("JC-90001"), None, None)

    assert exc.value.status_code == 409
    assert "transaction id" in exc.value.detail.lower()
    assert len(db.scalars(select(Payment)).all()) == 1


def test_the_same_ref_on_a_different_method_is_allowed(db):
    client = make_client(db, "owner-a@example.com", "Karachi Kicks")
    invoice = make_invoice(db, client)
    provider = ManualProvider()
    provider.submit(db, client, invoice, _submission("REF-1", method="jazzcash"), None, None)
    second = provider.submit(db, client, invoice, _submission("REF-1", method="easypaisa"), None, None)
    assert second.id is not None
    assert len(db.scalars(select(Payment)).all()) == 2


def test_proof_bytes_land_in_private_storage_under_the_client_id(db):
    # api_env already points STORAGE_ROOT at this test's own tmp_path.
    client = make_client(db, "owner-a@example.com", "Karachi Kicks")
    invoice = make_invoice(db, client)

    payment = ManualProvider().submit(db, client, invoice, _submission(), PNG_BYTES, "png")

    key = f"proofs/{client.id}/{payment.id}.png"
    assert payment.proof_file_path is not None
    assert key in payment.proof_file_path.replace("\\", "/")
    assert get_storage().read(key) == PNG_BYTES
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && .venv/Scripts/python -m pytest tests/api/test_payments_provider.py -v`
Expected: a collection error — `ModuleNotFoundError: No module named 'app.payments.manual'`.

- [ ] **Step 3: Write `app/payments/manual.py`**

`backend/app/payments/manual.py`:
```python
"""Manual payments: the client pays from their own wallet/bank app and reports the transaction ID.

Nothing here moves money or marks an invoice paid — see app/services/payments.py for the
admin-only confirmation step (docs/PLAN.md section 6, Stage 7, Rules).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models import Invoice, Payment, PaymentMethod
from app.payments.base import PaymentInstruction
from app.services.storage import get_storage

if TYPE_CHECKING:  # import-cycle guard, see app/payments/base.py
    from sqlalchemy.orm import Session

    from app.models import Client
    from app.schemas.billing import PaymentSubmission


class ManualProvider:
    name = "manual"

    def instructions_for(self, session: Session, invoice: Invoice) -> list[PaymentInstruction]:
        methods = session.scalars(
            select(PaymentMethod)
            .where(PaymentMethod.is_active.is_(True))
            .order_by(PaymentMethod.sort_order, PaymentMethod.id)
        ).all()
        return [
            PaymentInstruction(
                method_type=method.type,
                account_title=method.account_title,
                account_identifier=method.account_identifier,
                instructions=method.instructions,
            )
            for method in methods
        ]

    def submit(
        self,
        session: Session,
        client: Client,
        invoice: Invoice,
        submission: PaymentSubmission,
        proof: bytes | None = None,
        proof_ext: str | None = None,
    ) -> Payment:
        payment = Payment(
            invoice_id=invoice.id,
            client_id=client.id,
            method_type=submission.method_type,
            transaction_ref=submission.transaction_ref.strip(),
            amount=submission.amount,
            paid_at=submission.paid_at,
            status="pending",
            provider=self.name,
        )
        session.add(payment)
        try:
            # uq_payments_method_ref is the single source of truth for "already used".
            session.flush()
        except IntegrityError:
            session.rollback()
            raise HTTPException(
                status_code=409,
                detail="this transaction id has already been submitted for this payment method",
            ) from None

        if proof is not None and proof_ext is not None:
            payment.proof_file_path = get_storage().save(
                f"proofs/{client.id}/{payment.id}.{proof_ext}", proof
            )

        invoice.status = "payment_submitted"
        session.commit()
        session.refresh(payment)
        return payment
```

- [ ] **Step 4: Write `get_payment_provider()`**

`backend/app/payments/__init__.py`:
```python
"""Provider registry. Adding a gateway later (docs/PLAN.md section 9) means one new entry here."""

from app.core.settings import get_settings
from app.payments.base import PaymentInstruction, PaymentProvider
from app.payments.manual import ManualProvider

_PROVIDERS: dict[str, type] = {"manual": ManualProvider}

__all__ = ["ManualProvider", "PaymentInstruction", "PaymentProvider", "get_payment_provider"]


def get_payment_provider() -> PaymentProvider:
    name = get_settings().payment_provider
    provider_cls = _PROVIDERS.get(name)
    if provider_cls is None:
        raise ValueError(f"unknown payment provider: {name}")
    return provider_cls()
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd backend && .venv/Scripts/python -m pytest tests/api/test_payments_provider.py -v`
Expected: `13 passed`.

- [ ] **Step 6: Lint and commit**

Run: `cd backend && .venv/Scripts/ruff check . && .venv/Scripts/ruff format .`
```bash
git add backend/app/payments backend/tests/api/test_payments_provider.py
git commit -m "feat(billing): ManualProvider records transaction IDs, 409 on reuse" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 3: `services/payments.py` — invoice reads, confirm/reject arithmetic, proof validation, method CRUD

**Files:**
- Create: `backend/app/services/payments.py`
- Create (only if missing): `backend/app/services/__init__.py` (empty)
- Test: `backend/tests/api/test_payments_service.py`

**Interfaces:**
- Consumes: models `Invoice`, `Payment`, `PaymentMethod`, `Client`, `User`; `audit.record(session, actor_user_id, action, entity_type, entity_id, before, after)` (Stage 6); `PaymentMethodIn`, `PaymentMethodPatch`, `CLIENT_VISIBLE_STATUSES`, `PAYABLE_STATUSES` (Task 1).
- Produces:
  ```python
  CLIENT_VISIBLE_STATUSES ; PAYABLE_STATUSES ; METHOD_LABELS: dict[str, str]
  PROOF_TYPES: dict[str, tuple[str, bytes]]         # content-type -> (extension, magic bytes)
  class PaymentQueueRow(NamedTuple): payment: Payment; invoice: Invoice; client: Client

  list_invoices(session, client_id) -> list[Invoice]                     # never drafts, newest period first
  get_invoice(session, client_id, invoice_id) -> Invoice                 # 404 for another tenant or a draft
  list_payments(session, invoice_id) -> list[Payment]                    # oldest first
  list_pending_payments(session, status_filter="pending") -> list[PaymentQueueRow]
  confirm_payment(session, actor, payment_id, note=None) -> Payment
  reject_payment(session, actor, payment_id, note) -> Payment
  validate_proof(content_type, data, max_mb) -> str                      # "png"|"jpg"|"pdf"; 413 / 415
  list_payment_methods(session, active_only=True) -> list[PaymentMethod]
  create_payment_method(session, actor, data: PaymentMethodIn) -> PaymentMethod
  update_payment_method(session, actor, method_id, patch: PaymentMethodPatch) -> PaymentMethod
  ```

- [ ] **Step 1: Write the failing test**

`backend/tests/api/test_payments_service.py`:
```python
from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models import AuditLog, Invoice, Payment
from app.payments.manual import ManualProvider
from app.schemas.billing import PaymentMethodIn, PaymentMethodPatch, PaymentSubmission
from app.services import payments as payments_service
from tests.api.helpers import (
    JPEG_BYTES,
    PDF_BYTES,
    PNG_BYTES,
    make_admin,
    make_client,
    make_invoice,
    make_method,
)


def _submit(db, client, invoice, ref="JC-90001", amount="10000.00", method="jazzcash"):
    submission = PaymentSubmission(
        method_type=method, transaction_ref=ref, amount=Decimal(amount), paid_at=date(2026, 10, 2)
    )
    return ManualProvider().submit(db, client, invoice, submission, None, None)


def test_the_invoice_total_is_the_base_fee_plus_the_performance_fee(db):
    client = make_client(db, "owner-a@example.com", "Karachi Kicks")
    invoice = make_invoice(db, client)
    # 20% of 23,000 recovered waste = 4,600; 15,000 + 4,600 = 19,600.
    assert invoice.base_fee == Decimal("15000.00")
    assert invoice.confirmed_recovered_waste == Decimal("23000.00")
    assert invoice.performance_fee == Decimal("4600.00")
    assert invoice.total == Decimal("19600.00")


def test_a_partial_confirmation_records_the_money_but_leaves_the_invoice_unpaid(db):
    admin = make_admin(db)
    client = make_client(db, "owner-a@example.com", "Karachi Kicks")
    invoice = make_invoice(db, client)
    payment = _submit(db, client, invoice, "JC-90001", "10000.00")

    confirmed = payments_service.confirm_payment(db, admin, payment.id, "seen in JazzCash app")

    assert confirmed.status == "confirmed"
    assert confirmed.reviewed_by == admin.id
    assert confirmed.reviewed_at is not None
    assert confirmed.review_note == "seen in JazzCash app"
    reloaded = db.get(Invoice, invoice.id)
    assert reloaded.amount_paid == Decimal("10000.00")
    assert reloaded.status == "issued"  # 10,000 < 19,600 -> still owed


def test_confirming_the_remaining_9600_marks_the_invoice_paid(db):
    admin = make_admin(db)
    client = make_client(db, "owner-a@example.com", "Karachi Kicks")
    invoice = make_invoice(db, client)
    first = _submit(db, client, invoice, "JC-90001", "10000.00")
    payments_service.confirm_payment(db, admin, first.id, None)
    second = _submit(db, client, invoice, "JC-90002", "9600.00")

    payments_service.confirm_payment(db, admin, second.id, None)

    reloaded = db.get(Invoice, invoice.id)
    assert reloaded.amount_paid == Decimal("19600.00")
    assert reloaded.status == "paid"


def test_rejecting_the_only_pending_payment_puts_the_invoice_back_to_issued(db):
    admin = make_admin(db)
    client = make_client(db, "owner-a@example.com", "Karachi Kicks")
    invoice = make_invoice(db, client)
    payment = _submit(db, client, invoice)
    assert db.get(Invoice, invoice.id).status == "payment_submitted"

    rejected = payments_service.reject_payment(db, admin, payment.id, "no such TID in my app")

    assert rejected.status == "rejected"
    assert rejected.review_note == "no such TID in my app"
    reloaded = db.get(Invoice, invoice.id)
    assert reloaded.status == "issued"
    assert reloaded.amount_paid == Decimal("0.00")


def test_rejecting_one_of_two_pending_payments_keeps_the_invoice_awaiting_review(db):
    admin = make_admin(db)
    client = make_client(db, "owner-a@example.com", "Karachi Kicks")
    invoice = make_invoice(db, client)
    first = _submit(db, client, invoice, "JC-90001")
    _submit(db, client, invoice, "JC-90002")

    payments_service.reject_payment(db, admin, first.id, "wrong amount")

    assert db.get(Invoice, invoice.id).status == "payment_submitted"


def test_confirm_and_reject_each_write_one_audit_entry(db):
    admin = make_admin(db)
    client = make_client(db, "owner-a@example.com", "Karachi Kicks")
    invoice = make_invoice(db, client)
    good = _submit(db, client, invoice, "JC-90001")
    bad = _submit(db, client, invoice, "JC-90002")

    payments_service.confirm_payment(db, admin, good.id, None)
    payments_service.reject_payment(db, admin, bad.id, "duplicate screenshot")

    actions = [row.action for row in db.scalars(select(AuditLog).order_by(AuditLog.id))]
    assert actions == ["payment.confirm", "payment.reject"]
    entry = db.scalars(select(AuditLog).where(AuditLog.action == "payment.confirm")).one()
    assert entry.actor_user_id == admin.id
    assert entry.entity_type == "payment"
    assert entry.entity_id == good.id
    assert entry.before["invoice_amount_paid"] == "0.00"
    assert entry.after["invoice_amount_paid"] == "10000.00"


def test_a_payment_can_only_be_reviewed_once(db):
    admin = make_admin(db)
    client = make_client(db, "owner-a@example.com", "Karachi Kicks")
    invoice = make_invoice(db, client)
    payment = _submit(db, client, invoice)
    payments_service.confirm_payment(db, admin, payment.id, None)

    with pytest.raises(HTTPException) as exc:
        payments_service.confirm_payment(db, admin, payment.id, None)
    assert exc.value.status_code == 409

    with pytest.raises(HTTPException) as exc:
        payments_service.reject_payment(db, admin, payment.id, "changed my mind")
    assert exc.value.status_code == 409


def test_reviewing_a_payment_that_does_not_exist_is_404(db):
    admin = make_admin(db)
    with pytest.raises(HTTPException) as exc:
        payments_service.confirm_payment(db, admin, 4242, None)
    assert exc.value.status_code == 404


def test_clients_never_see_drafts_and_never_see_another_clients_invoice(db):
    client_a = make_client(db, "a@example.com", "Karachi Kicks")
    client_b = make_client(db, "b@example.com", "Lahore Leather")
    issued = make_invoice(db, client_a, number="INV-2026-0001", status="issued")
    draft = make_invoice(db, client_a, number="INV-2026-0002", status="draft")

    assert [i.id for i in payments_service.list_invoices(db, client_a.id)] == [issued.id]
    assert payments_service.list_invoices(db, client_b.id) == []
    assert payments_service.get_invoice(db, client_a.id, issued.id).id == issued.id

    for client_id, invoice_id in ((client_b.id, issued.id), (client_a.id, draft.id)):
        with pytest.raises(HTTPException) as exc:
            payments_service.get_invoice(db, client_id, invoice_id)
        assert exc.value.status_code == 404


def test_the_payment_queue_carries_the_invoice_and_the_business_name(db):
    admin = make_admin(db)
    client = make_client(db, "owner-a@example.com", "Karachi Kicks")
    invoice = make_invoice(db, client)
    payment = _submit(db, client, invoice)

    rows = payments_service.list_pending_payments(db)

    assert len(rows) == 1
    assert rows[0].payment.id == payment.id
    assert rows[0].invoice.invoice_number == "INV-2026-0001"
    assert rows[0].client.business_name == "Karachi Kicks"

    payments_service.confirm_payment(db, admin, payment.id, None)
    assert payments_service.list_pending_payments(db) == []
    assert len(payments_service.list_pending_payments(db, status_filter=None)) == 1


@pytest.mark.parametrize(
    ("content_type", "data", "expected"),
    [
        ("image/png", PNG_BYTES, "png"),
        ("image/jpeg", JPEG_BYTES, "jpg"),
        ("application/pdf", PDF_BYTES, "pdf"),
        ("image/png; charset=binary", PNG_BYTES, "png"),
    ],
)
def test_validate_proof_accepts_png_jpeg_and_pdf(content_type, data, expected):
    assert payments_service.validate_proof(content_type, data, 5) == expected


def test_validate_proof_rejects_other_types_and_lying_content_types():
    with pytest.raises(HTTPException) as exc:
        payments_service.validate_proof("image/svg+xml", b"<svg/>", 5)
    assert exc.value.status_code == 415

    with pytest.raises(HTTPException) as exc:  # says PNG, is really a zip
        payments_service.validate_proof("image/png", b"PK\x03\x04payload", 5)
    assert exc.value.status_code == 415

    with pytest.raises(HTTPException) as exc:
        payments_service.validate_proof(None, PNG_BYTES, 5)
    assert exc.value.status_code == 415


def test_validate_proof_enforces_the_five_megabyte_cap():
    too_big = b"\x89PNG\r\n\x1a\n" + b"0" * (5 * 1024 * 1024)
    with pytest.raises(HTTPException) as exc:
        payments_service.validate_proof("image/png", too_big, 5)
    assert exc.value.status_code == 413
    assert "5 MB" in exc.value.detail


def test_payment_method_crud_is_audited_and_patches_only_what_is_sent(db):
    admin = make_admin(db)
    created = payments_service.create_payment_method(
        db,
        admin,
        PaymentMethodIn(
            type="easypaisa",
            account_title="Ali Raza",
            account_identifier="0345-7654321",
            instructions="Easypaisa app -> Send Money.",
            sort_order=3,
        ),
    )
    assert created.is_active is True

    patched = payments_service.update_payment_method(
        db, admin, created.id, PaymentMethodPatch(is_active=False)
    )
    assert patched.is_active is False
    assert patched.account_title == "Ali Raza"  # untouched
    assert patched.sort_order == 3

    make_method(db, "jazzcash", sort_order=1)
    assert [m.type for m in payments_service.list_payment_methods(db)] == ["jazzcash"]
    assert len(payments_service.list_payment_methods(db, active_only=False)) == 2

    actions = [row.action for row in db.scalars(select(AuditLog).order_by(AuditLog.id))]
    assert actions == ["payment_method.create", "payment_method.update"]


def test_updating_a_missing_payment_method_is_404(db):
    admin = make_admin(db)
    with pytest.raises(HTTPException) as exc:
        payments_service.update_payment_method(db, admin, 999, PaymentMethodPatch(sort_order=1))
    assert exc.value.status_code == 404


def test_list_payments_returns_the_history_oldest_first(db):
    client = make_client(db, "owner-a@example.com", "Karachi Kicks")
    invoice = make_invoice(db, client)
    first = _submit(db, client, invoice, "JC-90001")
    second = _submit(db, client, invoice, "JC-90002")
    assert [p.id for p in payments_service.list_payments(db, invoice.id)] == [first.id, second.id]
    assert len(db.scalars(select(Payment)).all()) == 2
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd backend && .venv/Scripts/python -m pytest tests/api/test_payments_service.py -v`
Expected: a collection error — `ModuleNotFoundError: No module named 'app.services.payments'`.

- [ ] **Step 3: Write `app/services/payments.py` (everything except the PDF, which is Task 4)**

`backend/app/services/payments.py`:
```python
"""Invoice reads and the payment lifecycle.

Only an admin calls confirm_payment/reject_payment — they are the only functions that change
invoices.amount_paid or move an invoice to "paid" (docs/PLAN.md section 6, Stage 7, Rules).
"""

from __future__ import annotations

from decimal import Decimal
from typing import NamedTuple

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Client, Invoice, Payment, PaymentMethod, User
from app.models._types import utcnow
from app.schemas.billing import (
    CLIENT_VISIBLE_STATUSES,
    PAYABLE_STATUSES,
    PaymentMethodIn,
    PaymentMethodPatch,
)
from app.services import audit

__all__ = [
    "CLIENT_VISIBLE_STATUSES",
    "METHOD_LABELS",
    "PAYABLE_STATUSES",
    "PROOF_TYPES",
    "PaymentQueueRow",
    "confirm_payment",
    "create_payment_method",
    "get_invoice",
    "list_invoices",
    "list_payment_methods",
    "list_payments",
    "list_pending_payments",
    "reject_payment",
    "update_payment_method",
    "validate_proof",
]

# Human labels for the five methods in docs/PLAN.md section 4.
METHOD_LABELS: dict[str, str] = {
    "jazzcash": "JazzCash",
    "easypaisa": "Easypaisa",
    "nayapay": "NayaPay",
    "raast": "Raast",
    "bank_iban": "Bank transfer (IBAN)",
}

# content-type -> (file extension, magic bytes the file must actually start with).
PROOF_TYPES: dict[str, tuple[str, bytes]] = {
    "image/png": ("png", b"\x89PNG\r\n\x1a\n"),
    "image/jpeg": ("jpg", b"\xff\xd8\xff"),
    "application/pdf": ("pdf", b"%PDF-"),
}


class PaymentQueueRow(NamedTuple):
    payment: Payment
    invoice: Invoice
    client: Client


# --------------------------------------------------------------------------- client reads


def list_invoices(session: Session, client_id: int) -> list[Invoice]:
    return list(
        session.scalars(
            select(Invoice)
            .where(Invoice.client_id == client_id, Invoice.status.in_(CLIENT_VISIBLE_STATUSES))
            .order_by(Invoice.period_start.desc(), Invoice.id.desc())
        )
    )


def get_invoice(session: Session, client_id: int, invoice_id: int) -> Invoice:
    """404 — not 403 — for another tenant's invoice, so ids can't be probed (docs/PLAN.md section 4)."""
    invoice = session.scalars(
        select(Invoice).where(
            Invoice.id == invoice_id,
            Invoice.client_id == client_id,
            Invoice.status.in_(CLIENT_VISIBLE_STATUSES),
        )
    ).first()
    if invoice is None:
        raise HTTPException(status_code=404, detail="invoice not found")
    return invoice


def list_payments(session: Session, invoice_id: int) -> list[Payment]:
    return list(
        session.scalars(select(Payment).where(Payment.invoice_id == invoice_id).order_by(Payment.id))
    )


# --------------------------------------------------------------------------- admin queue


def list_pending_payments(
    session: Session, status_filter: str | None = "pending"
) -> list[PaymentQueueRow]:
    stmt = (
        select(Payment, Invoice, Client)
        .join(Invoice, Payment.invoice_id == Invoice.id)
        .join(Client, Payment.client_id == Client.id)
        .order_by(Payment.created_at.desc(), Payment.id.desc())
    )
    if status_filter is not None:
        stmt = stmt.where(Payment.status == status_filter)
    return [
        PaymentQueueRow(payment, invoice, client)
        for payment, invoice, client in session.execute(stmt).all()
    ]


# --------------------------------------------------------------------------- admin decisions


def _get_payment(session: Session, payment_id: int) -> Payment:
    payment = session.get(Payment, payment_id)
    if payment is None:
        raise HTTPException(status_code=404, detail="payment not found")
    if payment.status != "pending":
        raise HTTPException(status_code=409, detail=f"payment was already {payment.status}")
    return payment


def _snapshot(payment: Payment, invoice: Invoice) -> dict[str, str]:
    """JSON-safe before/after for audit_log. Decimals become strings, never floats."""
    return {
        "payment_status": payment.status,
        "payment_amount": str(payment.amount),
        "invoice_status": invoice.status,
        "invoice_amount_paid": str(invoice.amount_paid),
    }


def confirm_payment(
    session: Session, actor: User, payment_id: int, note: str | None = None
) -> Payment:
    payment = _get_payment(session, payment_id)
    invoice = session.get(Invoice, payment.invoice_id)
    before = _snapshot(payment, invoice)

    payment.status = "confirmed"
    payment.reviewed_by = actor.id
    payment.reviewed_at = utcnow()
    payment.review_note = note
    invoice.amount_paid = Decimal(invoice.amount_paid) + Decimal(payment.amount)
    invoice.status = "paid" if invoice.amount_paid >= invoice.total else "issued"

    audit.record(
        session, actor.id, "payment.confirm", "payment", payment.id, before, _snapshot(payment, invoice)
    )
    session.commit()
    session.refresh(payment)
    return payment


def reject_payment(session: Session, actor: User, payment_id: int, note: str) -> Payment:
    payment = _get_payment(session, payment_id)
    invoice = session.get(Invoice, payment.invoice_id)
    before = _snapshot(payment, invoice)

    payment.status = "rejected"
    payment.reviewed_by = actor.id
    payment.reviewed_at = utcnow()
    payment.review_note = note
    session.flush()

    still_pending = session.scalar(
        select(func.count())
        .select_from(Payment)
        .where(Payment.invoice_id == invoice.id, Payment.status == "pending")
    )
    if invoice.status == "payment_submitted" and not still_pending:
        invoice.status = "issued"

    audit.record(
        session, actor.id, "payment.reject", "payment", payment.id, before, _snapshot(payment, invoice)
    )
    session.commit()
    session.refresh(payment)
    return payment


# --------------------------------------------------------------------------- proof files


def validate_proof(content_type: str | None, data: bytes, max_mb: int) -> str:
    """Return the file extension for a proof upload, or raise 413 (too big) / 415 (wrong kind)."""
    if len(data) > max_mb * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"proof file must be {max_mb} MB or smaller")
    entry = PROOF_TYPES.get((content_type or "").split(";")[0].strip().lower())
    if entry is None:
        raise HTTPException(status_code=415, detail="proof must be a PNG, JPEG or PDF file")
    extension, magic = entry
    if not data.startswith(magic):
        raise HTTPException(status_code=415, detail="proof file contents do not match its file type")
    return extension


# --------------------------------------------------------------------------- payment methods


def list_payment_methods(session: Session, active_only: bool = True) -> list[PaymentMethod]:
    stmt = select(PaymentMethod).order_by(PaymentMethod.sort_order, PaymentMethod.id)
    if active_only:
        stmt = stmt.where(PaymentMethod.is_active.is_(True))
    return list(session.scalars(stmt))


def _method_snapshot(method: PaymentMethod) -> dict[str, str | bool | int]:
    return {
        "type": method.type,
        "account_title": method.account_title,
        "account_identifier": method.account_identifier,
        "is_active": method.is_active,
        "sort_order": method.sort_order,
    }


def create_payment_method(session: Session, actor: User, data: PaymentMethodIn) -> PaymentMethod:
    method = PaymentMethod(**data.model_dump())
    session.add(method)
    session.flush()
    audit.record(
        session,
        actor.id,
        "payment_method.create",
        "payment_method",
        method.id,
        None,
        _method_snapshot(method),
    )
    session.commit()
    session.refresh(method)
    return method


def update_payment_method(
    session: Session, actor: User, method_id: int, patch: PaymentMethodPatch
) -> PaymentMethod:
    method = session.get(PaymentMethod, method_id)
    if method is None:
        raise HTTPException(status_code=404, detail="payment method not found")
    before = _method_snapshot(method)
    for field, value in patch.model_dump(exclude_unset=True).items():
        setattr(method, field, value)
    audit.record(
        session,
        actor.id,
        "payment_method.update",
        "payment_method",
        method.id,
        before,
        _method_snapshot(method),
    )
    session.commit()
    session.refresh(method)
    return method
```

Create `backend/app/services/__init__.py` as an empty file if it does not already exist.

`CLIENT_VISIBLE_STATUSES` and `PAYABLE_STATUSES` are re-exported here on purpose — the routers in Tasks 5 and 6 read them off this module, and `__all__` keeps ruff's `F401` quiet.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && .venv/Scripts/python -m pytest tests/api/test_payments_service.py -v`
Expected: `17 passed` (the `validate_proof` parametrize contributes 4 of them).

- [ ] **Step 5: Lint and commit**

Run: `cd backend && .venv/Scripts/ruff check . && .venv/Scripts/ruff format .`
```bash
git add backend/app/services/payments.py backend/app/services/__init__.py backend/tests/api/test_payments_service.py
git commit -m "feat(billing): confirm/reject payments with partial-payment arithmetic and audit" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 4: `build_invoice_pdf` — the invoice a client downloads

**Files:**
- Modify: `backend/app/services/payments.py` (append)
- Test: `backend/tests/api/test_invoice_pdf.py`

**Interfaces:**
- Consumes: `PaymentInstruction` (Task 1), `METHOD_LABELS` (Task 3), `Invoice`, `Client`; ReportLab, following Stage 5's conventions in `app/services/pdf.py` (A4 `SimpleDocTemplate`, mm margins, `Table` + `TableStyle`, no matplotlib).
- Produces:
  ```python
  build_invoice_pdf(invoice: Invoice, client: Client, instructions: list[PaymentInstruction]) -> bytes
  ```
  The first page always contains: the invoice number, the billing period, a base-fee line, a performance-fee line naming the **confirmed recovered waste**, the total, the due date, one row per active payment account with its account number, and the sentence asking the client to reply with their transaction ID on the billing page.

- [ ] **Step 1: Write the failing test**

`backend/tests/api/test_invoice_pdf.py`:
```python
from decimal import Decimal
from io import BytesIO

from pypdf import PdfReader

from app.payments.base import PaymentInstruction
from app.services.payments import build_invoice_pdf
from tests.api.helpers import make_client, make_invoice

INSTRUCTIONS = [
    PaymentInstruction(
        method_type="jazzcash",
        account_title="Ali Raza",
        account_identifier="0300-1234567",
        instructions="JazzCash app -> Send Money -> Mobile Account.",
    ),
    PaymentInstruction(
        method_type="bank_iban",
        account_title="Ali Raza",
        account_identifier="PK36SCBL0000001123456702",
        instructions=None,
    ),
]


def _text(pdf: bytes) -> str:
    """Flatten page 1 to one whitespace-normalised line so line wrapping can't break an assert."""
    return " ".join(PdfReader(BytesIO(pdf)).pages[0].extract_text().split())


def test_the_pdf_shows_the_numbers_the_client_is_being_charged(db):
    client = make_client(db, "owner-a@example.com", "Karachi Kicks")
    invoice = make_invoice(db, client)

    pdf = build_invoice_pdf(invoice, client, INSTRUCTIONS)

    assert pdf.startswith(b"%PDF-")
    text = _text(pdf)
    assert "INV-2026-0001" in text
    assert "Karachi Kicks" in text
    assert "01 Sep 2026" in text and "30 Sep 2026" in text  # the billing period
    assert "07 Oct 2026" in text  # the due date
    assert "Rs. 15,000.00" in text  # base fee
    assert "Rs. 23,000.00" in text  # confirmed recovered waste, shown on the fee line
    assert "Rs. 4,600.00" in text  # performance fee
    assert "Rs. 19,600.00" in text  # total


def test_the_pdf_lists_every_account_and_asks_for_the_transaction_id(db):
    client = make_client(db, "owner-a@example.com", "Karachi Kicks")
    invoice = make_invoice(db, client)

    text = _text(build_invoice_pdf(invoice, client, INSTRUCTIONS))

    assert "JazzCash" in text
    assert "0300-1234567" in text
    assert "Bank transfer (IBAN)" in text
    assert "PK36SCBL0000001123456702" in text
    assert "JazzCash app -> Send Money -> Mobile Account." in text
    assert "reply with your transaction ID on the billing page" in text


def test_a_partly_paid_invoice_shows_the_balance(db):
    client = make_client(db, "owner-a@example.com", "Karachi Kicks")
    invoice = make_invoice(db, client, amount_paid=Decimal("10000.00"))

    text = _text(build_invoice_pdf(invoice, client, INSTRUCTIONS))

    assert "Already paid" in text
    assert "Rs. 10,000.00" in text
    assert "Rs. 9,600.00" in text  # 19,600 - 10,000


def test_the_pdf_still_renders_when_no_accounts_are_configured(db):
    client = make_client(db, "owner-a@example.com", "Karachi Kicks")
    invoice = make_invoice(db, client)

    text = _text(build_invoice_pdf(invoice, client, []))

    assert "No payment accounts are set up yet" in text
    assert "Rs. 19,600.00" in text
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd backend && .venv/Scripts/python -m pytest tests/api/test_invoice_pdf.py -v`
Expected: `ImportError: cannot import name 'build_invoice_pdf' from 'app.services.payments'`.

- [ ] **Step 3: Append the PDF builder to `app/services/payments.py`**

Add these imports at the top of `backend/app/services/payments.py`:
```python
from datetime import date
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.payments.base import PaymentInstruction
```
and add `"build_invoice_pdf"` to `__all__`.

Append to `backend/app/services/payments.py`:
```python
# --------------------------------------------------------------------------- invoice PDF

INK = colors.HexColor("#0b1220")
SLATE = colors.HexColor("#8891a5")
HAIRLINE = colors.HexColor("#d8dde5")

_TABLE_STYLE = TableStyle(
    [
        ("LINEBELOW", (0, 0), (-1, 0), 0.7, INK),
        ("LINEBELOW", (0, 1), (-1, -2), 0.3, HAIRLINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
)


def _money(value: Decimal) -> str:
    """Rs. 19,600.00 — always two decimals, always from a Decimal."""
    return f"Rs. {Decimal(value):,.2f}"


def _day(value: date) -> str:
    return f"{value.day:02d} {value:%b %Y}"


def build_invoice_pdf(
    invoice: Invoice, client: Client, instructions: list[PaymentInstruction]
) -> bytes:
    """One page: what is owed, why, and exactly where to send it."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=f"Invoice {invoice.invoice_number}",
        author="Ad Spend Optimization",
    )
    sheet = getSampleStyleSheet()
    title = ParagraphStyle(
        "InvoiceTitle", parent=sheet["Title"], fontSize=20, alignment=TA_LEFT, spaceAfter=2
    )
    heading = ParagraphStyle(
        "InvoiceHeading", parent=sheet["Heading2"], fontSize=12, spaceBefore=6, spaceAfter=4
    )
    body = ParagraphStyle("InvoiceBody", parent=sheet["BodyText"], fontSize=9.5, leading=13)
    muted = ParagraphStyle("InvoiceMuted", parent=body, textColor=SLATE)

    flow = [
        Paragraph(f"Invoice {invoice.invoice_number}", title),
        Paragraph(client.business_name, body),
        Paragraph(f"Billing period: {_day(invoice.period_start)} to {_day(invoice.period_end)}", body),
        Paragraph(f"Due date: {_day(invoice.due_date)}", body),
        Spacer(1, 7 * mm),
    ]

    rows = [
        [Paragraph("<b>Item</b>", body), Paragraph("<b>Amount</b>", body)],
        [Paragraph("Monthly base fee", body), Paragraph(_money(invoice.base_fee), body)],
        [
            Paragraph(
                "Performance fee on confirmed recovered waste of "
                f"{_money(invoice.confirmed_recovered_waste)}",
                body,
            ),
            Paragraph(_money(invoice.performance_fee), body),
        ],
        [Paragraph("<b>Total due</b>", body), Paragraph(f"<b>{_money(invoice.total)}</b>", body)],
    ]
    if Decimal(invoice.amount_paid) > 0:
        balance = Decimal(invoice.total) - Decimal(invoice.amount_paid)
        rows.append([Paragraph("Already paid", body), Paragraph(_money(invoice.amount_paid), body)])
        rows.append([Paragraph("<b>Balance</b>", body), Paragraph(f"<b>{_money(balance)}</b>", body)])

    amounts = Table(rows, colWidths=[115 * mm, 45 * mm], hAlign="LEFT")
    amounts.setStyle(_TABLE_STYLE)
    flow += [amounts, Spacer(1, 8 * mm), Paragraph("How to pay", heading)]

    if instructions:
        account_rows = [
            [
                Paragraph("<b>Method</b>", body),
                Paragraph("<b>Account title</b>", body),
                Paragraph("<b>Account number / IBAN</b>", body),
            ]
        ]
        for instruction in instructions:
            account_rows.append(
                [
                    Paragraph(METHOD_LABELS.get(instruction.method_type, instruction.method_type), body),
                    Paragraph(instruction.account_title, body),
                    Paragraph(instruction.account_identifier, body),
                ]
            )
        accounts = Table(account_rows, colWidths=[40 * mm, 50 * mm, 70 * mm], hAlign="LEFT")
        accounts.setStyle(_TABLE_STYLE)
        flow.append(accounts)
        for instruction in instructions:
            if instruction.instructions:
                label = METHOD_LABELS.get(instruction.method_type, instruction.method_type)
                flow.append(Paragraph(f"{label}: {instruction.instructions}", muted))
    else:
        flow.append(Paragraph("No payment accounts are set up yet — contact us before paying.", muted))

    flow += [
        Spacer(1, 6 * mm),
        Paragraph(
            "Pay from your own wallet or bank app, then reply with your transaction ID on the billing "
            "page. We confirm every payment by hand, so the invoice stays open until we have checked it.",
            body,
        ),
    ]

    doc.build(flow)
    return buffer.getvalue()
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && .venv/Scripts/python -m pytest tests/api/test_invoice_pdf.py -v`
Expected: `4 passed`.

If an assertion fails on a string that clearly *is* in the PDF, print the extracted text and fix the template, never the assertion:
```bash
cd backend && .venv/Scripts/python -c "from pypdf import PdfReader; import sys; print(PdfReader(sys.argv[1]).pages[0].extract_text())" out.pdf
```

- [ ] **Step 5: Lint and commit**

Run: `cd backend && .venv/Scripts/ruff check . && .venv/Scripts/ruff format .`
```bash
git add backend/app/services/payments.py backend/tests/api/test_invoice_pdf.py
git commit -m "feat(billing): ReportLab invoice PDF with payment instructions" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 5: Client billing routes — `/api/billing/*`

**Files:**
- Create: `backend/app/routers/billing.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/api/test_billing_routes.py`

**Interfaces:**
- Consumes: `CurrentClient` (Stage 2, `app/core/deps.py`), `get_session` (Stage 0), `get_payment_provider()` (Task 2), `app.services.payments` (Tasks 3–4), the schemas from Task 1, `Settings.max_proof_mb` (Task 1).
- Produces (exactly `docs/PLAN.md` §5, *Billing*):
  ```
  GET  /api/billing/invoices                       -> 200 list[InvoiceOut]   (never drafts)
  GET  /api/billing/invoices/{invoice_id}          -> 200 InvoiceOut  (+ payments, + instructions)
  GET  /api/billing/invoices/{invoice_id}/pdf      -> 200 application/pdf, attachment
  GET  /api/billing/payment-methods                -> 200 list[PaymentMethodOut]  (active only)
  POST /api/billing/invoices/{invoice_id}/payments -> 201 PaymentOut
       multipart: method_type, transaction_ref, amount, paid_at, optional proof (<= 5 MB, PNG/JPEG/PDF)
       409 reused transaction id · 409 invoice not payable · 413 proof too big · 415 wrong file kind
       404 another client's invoice, or a draft
  # module attribute: router = APIRouter(prefix="/api/billing", tags=["billing"])
  ```

- [ ] **Step 1: Write the failing test**

`backend/tests/api/test_billing_routes.py`:
```python
"""Client-facing billing over HTTP (docs/PLAN.md section 5, "Billing").

`db` and the request handler run on two Sessions over the one shared connection, so call
`db.expire_all()` before reading back a row a request has just changed.
"""

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Client, Invoice, Payment
from tests.api.helpers import PDF_BYTES, PNG_BYTES, make_invoice, make_method

FORM = {
    "method_type": "jazzcash",
    "transaction_ref": "JC-90001",
    "amount": "10000.00",
    "paid_at": "2026-10-02",
}


def test_invoice_list_hides_drafts_and_shows_the_money(
    client_a: TestClient, db: Session, client_a_row: Client
):
    make_invoice(db, client_a_row, number="INV-2026-0001", status="issued")
    make_invoice(db, client_a_row, number="INV-2026-0002", status="draft")

    response = client_a.get("/api/billing/invoices")

    assert response.status_code == 200
    body = response.json()
    assert [row["invoice_number"] for row in body] == ["INV-2026-0001"]
    assert body[0]["total"] == "19600.00"
    assert body[0]["amount_due"] == "19600.00"
    assert body[0]["is_overdue"] is False
    assert body[0]["payments"] == []


def test_invoice_detail_carries_payment_history_and_instructions(
    client_a: TestClient, db: Session, client_a_row: Client
):
    invoice = make_invoice(db, client_a_row)
    make_method(db, "jazzcash", sort_order=0)
    make_method(db, "raast", "PK36SCBL0000001123456702", sort_order=1)
    make_method(db, "nayapay", is_active=False, sort_order=2)

    body = client_a.get(f"/api/billing/invoices/{invoice.id}").json()

    assert body["invoice_number"] == "INV-2026-0001"
    assert [i["method_type"] for i in body["instructions"]] == ["jazzcash", "raast"]
    assert body["instructions"][0]["account_identifier"] == "03001234567"


def test_payment_methods_endpoint_returns_only_active_ones(client_a: TestClient, db: Session):
    make_method(db, "jazzcash")
    make_method(db, "nayapay", is_active=False)

    body = client_a.get("/api/billing/payment-methods").json()

    assert [m["type"] for m in body] == ["jazzcash"]
    assert body[0]["account_title"] == "Ali Raza"


def test_invoice_pdf_downloads_as_an_attachment(
    client_a: TestClient, db: Session, client_a_row: Client
):
    invoice = make_invoice(db, client_a_row)
    make_method(db)

    response = client_a.get(f"/api/billing/invoices/{invoice.id}/pdf")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert "INV-2026-0001.pdf" in response.headers["content-disposition"]
    assert response.content.startswith(b"%PDF-")


def test_submitting_a_payment_moves_the_invoice_to_payment_submitted(
    client_a: TestClient, db: Session, client_a_row: Client
):
    invoice = make_invoice(db, client_a_row)

    response = client_a.post(f"/api/billing/invoices/{invoice.id}/payments", data=FORM)

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "pending"
    assert body["transaction_ref"] == "JC-90001"
    assert body["amount"] == "10000.00"
    assert body["has_proof"] is False
    assert "proof_file_path" not in body  # the private path never leaves the server
    db.expire_all()
    reloaded = db.get(Invoice, invoice.id)
    assert reloaded.status == "payment_submitted"
    assert reloaded.amount_paid == Decimal("0.00")


def test_a_proof_screenshot_is_stored_privately(
    client_a: TestClient, db: Session, client_a_row: Client, tmp_path
):
    # api_env already points STORAGE_ROOT at tmp_path / "storage".
    invoice = make_invoice(db, client_a_row)

    response = client_a.post(
        f"/api/billing/invoices/{invoice.id}/payments",
        data=FORM,
        files={"proof": ("screenshot.png", PNG_BYTES, "image/png")},
    )

    assert response.status_code == 201, response.text
    assert response.json()["has_proof"] is True
    db.expire_all()
    payment = db.get(Payment, response.json()["id"])
    assert payment.proof_file_path.endswith(".png")
    stored = tmp_path / "storage" / "proofs" / str(client_a_row.id) / f"{payment.id}.png"
    assert stored.exists()


def test_a_pdf_receipt_is_also_accepted_as_proof(
    client_a: TestClient, db: Session, client_a_row: Client
):
    invoice = make_invoice(db, client_a_row)

    response = client_a.post(
        f"/api/billing/invoices/{invoice.id}/payments",
        data=FORM,
        files={"proof": ("receipt.pdf", PDF_BYTES, "application/pdf")},
    )

    assert response.status_code == 201, response.text


def test_a_reused_transaction_id_is_refused_with_409(
    client_a: TestClient, db: Session, client_a_row: Client
):
    invoice = make_invoice(db, client_a_row)
    assert client_a.post(f"/api/billing/invoices/{invoice.id}/payments", data=FORM).status_code == 201

    response = client_a.post(f"/api/billing/invoices/{invoice.id}/payments", data=FORM)

    assert response.status_code == 409
    assert "transaction id" in response.json()["detail"].lower()


def test_an_oversized_proof_is_413_and_a_wrong_file_type_is_415(
    client_a: TestClient, db: Session, client_a_row: Client
):
    invoice = make_invoice(db, client_a_row)

    too_big = b"\x89PNG\r\n\x1a\n" + b"0" * (5 * 1024 * 1024)
    big = client_a.post(
        f"/api/billing/invoices/{invoice.id}/payments",
        data=FORM,
        files={"proof": ("huge.png", too_big, "image/png")},
    )
    assert big.status_code == 413

    wrong = client_a.post(
        f"/api/billing/invoices/{invoice.id}/payments",
        data={**FORM, "transaction_ref": "JC-90002"},
        files={"proof": ("notes.txt", b"hello", "text/plain")},
    )
    assert wrong.status_code == 415
    # A refused upload must not leave a half-made payment behind.
    db.expire_all()
    assert db.scalars(select(Payment)).all() == []


def test_a_bad_form_is_422_not_500(client_a: TestClient, db: Session, client_a_row: Client):
    invoice = make_invoice(db, client_a_row)
    url = f"/api/billing/invoices/{invoice.id}/payments"

    assert client_a.post(url, data={**FORM, "amount": "0"}).status_code == 422
    assert client_a.post(url, data={**FORM, "method_type": "paypal"}).status_code == 422
    assert client_a.post(url, data={**FORM, "paid_at": "yesterday"}).status_code == 422
    assert client_a.post(url, data={**FORM, "transaction_ref": ""}).status_code == 422


def test_a_paid_invoice_does_not_take_more_payments(
    client_a: TestClient, db: Session, client_a_row: Client
):
    invoice = make_invoice(db, client_a_row, status="paid", amount_paid=Decimal("19600.00"))

    response = client_a.post(f"/api/billing/invoices/{invoice.id}/payments", data=FORM)

    assert response.status_code == 409
    assert "paid" in response.json()["detail"]


def test_client_b_can_neither_see_nor_pay_client_as_invoice(
    client_b: TestClient, db: Session, client_a_row: Client
):
    invoice = make_invoice(db, client_a_row)

    assert client_b.get("/api/billing/invoices").json() == []
    assert client_b.get(f"/api/billing/invoices/{invoice.id}").status_code == 404
    assert client_b.get(f"/api/billing/invoices/{invoice.id}/pdf").status_code == 404
    assert client_b.post(f"/api/billing/invoices/{invoice.id}/payments", data=FORM).status_code == 404
    db.expire_all()
    assert db.scalars(select(Payment)).all() == []


def test_billing_requires_a_logged_in_client(api: TestClient, db: Session, client_a_row: Client):
    invoice = make_invoice(db, client_a_row)

    assert api.get("/api/billing/invoices").status_code == 401
    assert api.post(f"/api/billing/invoices/{invoice.id}/payments", data=FORM).status_code == 401
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd backend && .venv/Scripts/python -m pytest tests/api/test_billing_routes.py -v`
Expected: every test fails with `assert 404 == 200` (or similar) — the routes do not exist yet.

- [ ] **Step 3: Write the router**

`backend/app/routers/billing.py`:
```python
"""Client-facing billing. docs/PLAN.md section 5, "Billing".

Never accepts a client_id from the request — it always comes from CurrentClient.
"""

from datetime import date
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from sqlalchemy.orm import Session

from app.core.db import get_session
from app.core.deps import CurrentClient
from app.core.settings import get_settings
from app.payments import get_payment_provider
from app.schemas.billing import (
    InvoiceOut,
    MethodType,
    PaymentMethodOut,
    PaymentOut,
    PaymentSubmission,
    invoice_out,
)
from app.services import payments as payments_service

router = APIRouter(prefix="/api/billing", tags=["billing"])

SessionDep = Annotated[Session, Depends(get_session)]


@router.get("/invoices", response_model=list[InvoiceOut])
def list_invoices(client: CurrentClient, session: SessionDep) -> list[InvoiceOut]:
    return [invoice_out(invoice) for invoice in payments_service.list_invoices(session, client.id)]


@router.get("/payment-methods", response_model=list[PaymentMethodOut])
def list_payment_methods(client: CurrentClient, session: SessionDep):
    return payments_service.list_payment_methods(session, active_only=True)


@router.get("/invoices/{invoice_id}", response_model=InvoiceOut)
def get_invoice(invoice_id: int, client: CurrentClient, session: SessionDep) -> InvoiceOut:
    invoice = payments_service.get_invoice(session, client.id, invoice_id)
    return invoice_out(
        invoice,
        payments_service.list_payments(session, invoice.id),
        get_payment_provider().instructions_for(session, invoice),
    )


@router.get("/invoices/{invoice_id}/pdf")
def get_invoice_pdf(invoice_id: int, client: CurrentClient, session: SessionDep) -> Response:
    invoice = payments_service.get_invoice(session, client.id, invoice_id)
    pdf = payments_service.build_invoice_pdf(
        invoice, client, get_payment_provider().instructions_for(session, invoice)
    )
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{invoice.invoice_number}.pdf"'},
    )


@router.post("/invoices/{invoice_id}/payments", response_model=PaymentOut, status_code=201)
async def submit_payment(
    invoice_id: int,
    client: CurrentClient,
    session: SessionDep,
    method_type: Annotated[MethodType, Form()],
    transaction_ref: Annotated[str, Form(min_length=1, max_length=80)],
    amount: Annotated[Decimal, Form(gt=0)],
    paid_at: Annotated[date, Form()],
    proof: Annotated[UploadFile | None, File()] = None,
):
    """The client reports a payment they already made. This NEVER marks the invoice paid."""
    invoice = payments_service.get_invoice(session, client.id, invoice_id)
    if invoice.status not in payments_service.PAYABLE_STATUSES:
        raise HTTPException(
            status_code=409,
            detail=f"invoice {invoice.invoice_number} is {invoice.status} and cannot take payments",
        )

    # Every field is already validated by the Form() annotations above, so this never raises.
    submission = PaymentSubmission(
        method_type=method_type, transaction_ref=transaction_ref, amount=amount, paid_at=paid_at
    )

    data: bytes | None = None
    extension: str | None = None
    if proof is not None and proof.filename:
        data = await proof.read()
        extension = payments_service.validate_proof(
            proof.content_type, data, get_settings().max_proof_mb
        )

    return get_payment_provider().submit(session, client, invoice, submission, data, extension)
```

- [ ] **Step 4: Register the router**

In `backend/app/main.py`, inside `create_app()`, add the import and the include alongside the routers Stages 2–6 already register:
```python
    from app.routers import billing

    application.include_router(billing.router)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd backend && .venv/Scripts/python -m pytest tests/api/test_billing_routes.py -v`
Expected: `13 passed`.

- [ ] **Step 6: Lint and commit**

Run: `cd backend && .venv/Scripts/ruff check . && .venv/Scripts/ruff format .`
```bash
git add backend/app/routers/billing.py backend/app/main.py backend/tests/api/test_billing_routes.py
git commit -m "feat(billing): client invoice, PDF and payment-submission routes" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 6: Admin payment routes on Stage 6's admin router

**Files:**
- Modify: `backend/app/routers/admin.py` (the router Stage 6 created: `router = APIRouter(prefix="/api/admin", ...)`)
- Test: `backend/tests/api/test_admin_payments_routes.py`

**Interfaces:**
- Consumes: `CurrentAdmin` (Stage 2), Stage 6's session dependency alias in `admin.py`, `app.services.payments` (Tasks 3–4), `admin_payment_out`, `PaymentMethodIn`, `PaymentMethodOut`, `PaymentMethodPatch`, `ReviewRequest`, `RejectRequest` (Task 1), `get_storage()` (Stage 3).
- Produces (exactly `docs/PLAN.md` §5, *Admin*, plus the proof download declared in this plan's header):
  ```
  GET   /api/admin/payments?status=pending          -> 200 list[AdminPaymentOut]  (status=all for every row)
  POST  /api/admin/payments/{payment_id}/confirm    -> 200 AdminPaymentOut   body ReviewRequest
  POST  /api/admin/payments/{payment_id}/reject     -> 200 AdminPaymentOut   body RejectRequest (note required)
  GET   /api/admin/payments/{payment_id}/proof      -> 200 image/png|image/jpeg|application/pdf, inline
  GET   /api/admin/payment-methods                  -> 200 list[PaymentMethodOut]  (including inactive)
  POST  /api/admin/payment-methods                  -> 201 PaymentMethodOut
  PATCH /api/admin/payment-methods/{method_id}      -> 200 PaymentMethodOut
  ```

- [ ] **Step 1: Write the failing test**

`backend/tests/api/test_admin_payments_routes.py`:
```python
"""Admin review of manual payments, over HTTP.

`client_a` and `admin_client` are two logged-in TestClients from tests/api/conftest.py, so no
test here logs anybody in by hand. `db.expire_all()` precedes every read-back of a row a
request has changed.
"""

from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditLog, Client, Invoice, PaymentMethod
from tests.api.helpers import PNG_BYTES, make_invoice, make_method

FORM = {
    "method_type": "jazzcash",
    "transaction_ref": "JC-90001",
    "amount": "10000.00",
    "paid_at": "2026-10-02",
}


def _client_submits(
    db: Session, client_a: TestClient, client_a_row: Client, *, due_date=date(2026, 10, 7)
):
    """One issued invoice for client_a plus one pending payment on it."""
    invoice = make_invoice(db, client_a_row, due_date=due_date)
    response = client_a.post(f"/api/billing/invoices/{invoice.id}/payments", data=FORM)
    assert response.status_code == 201, response.text
    return invoice, response.json()["id"]


def test_the_queue_shows_pending_payments_with_their_invoice_and_client(
    db: Session, client_a: TestClient, client_a_row: Client, admin_client: TestClient
):
    _, payment_id = _client_submits(db, client_a, client_a_row)

    body = admin_client.get("/api/admin/payments?status=pending").json()

    assert len(body) == 1
    row = body[0]
    assert row["id"] == payment_id
    assert row["transaction_ref"] == "JC-90001"
    assert row["business_name"] == "Alpha Traders"  # client_a's business name
    assert row["invoice_number"] == "INV-2026-0001"
    assert row["invoice_total"] == "19600.00"
    assert row["invoice_is_overdue"] is False
    assert row["has_proof"] is False


def test_an_invoice_past_its_due_date_is_flagged_overdue(
    db: Session, client_a: TestClient, client_a_row: Client, admin_client: TestClient
):
    _client_submits(db, client_a, client_a_row, due_date=date(2020, 1, 7))

    row = admin_client.get("/api/admin/payments?status=pending").json()[0]

    assert row["invoice_due_date"] == "2020-01-07"
    assert row["invoice_is_overdue"] is True


def test_confirming_a_partial_payment_leaves_the_invoice_unpaid_then_a_second_one_pays_it(
    db: Session, client_a: TestClient, client_a_row: Client, admin_client: TestClient
):
    invoice, payment_id = _client_submits(db, client_a, client_a_row)

    first = admin_client.post(
        f"/api/admin/payments/{payment_id}/confirm", json={"note": "seen in app"}
    )

    assert first.status_code == 200
    assert first.json()["status"] == "confirmed"
    assert first.json()["invoice_status"] == "issued"
    db.expire_all()
    assert db.get(Invoice, invoice.id).amount_paid == Decimal("10000.00")

    second = client_a.post(
        f"/api/billing/invoices/{invoice.id}/payments",
        data={**FORM, "transaction_ref": "JC-90002", "amount": "9600.00"},
    )
    admin_client.post(f"/api/admin/payments/{second.json()['id']}/confirm", json={})

    db.expire_all()
    reloaded = db.get(Invoice, invoice.id)
    assert reloaded.amount_paid == Decimal("19600.00")
    assert reloaded.status == "paid"
    assert admin_client.get("/api/admin/payments?status=pending").json() == []


def test_rejecting_needs_a_reason_and_the_client_can_read_it(
    db: Session, client_a: TestClient, client_a_row: Client, admin_client: TestClient
):
    invoice, payment_id = _client_submits(db, client_a, client_a_row)

    assert admin_client.post(f"/api/admin/payments/{payment_id}/reject", json={}).status_code == 422
    assert (
        admin_client.post(f"/api/admin/payments/{payment_id}/reject", json={"note": ""}).status_code
        == 422
    )

    rejected = admin_client.post(
        f"/api/admin/payments/{payment_id}/reject", json={"note": "no such TID in my JazzCash app"}
    )

    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"
    detail = client_a.get(f"/api/billing/invoices/{invoice.id}").json()
    assert detail["status"] == "issued"
    assert detail["payments"][0]["review_note"] == "no such TID in my JazzCash app"
    assert detail["amount_paid"] == "0.00"


def test_confirming_twice_is_409_and_an_unknown_payment_is_404(
    db: Session, client_a: TestClient, client_a_row: Client, admin_client: TestClient
):
    _, payment_id = _client_submits(db, client_a, client_a_row)
    admin_client.post(f"/api/admin/payments/{payment_id}/confirm", json={})

    assert admin_client.post(f"/api/admin/payments/{payment_id}/confirm", json={}).status_code == 409
    assert admin_client.post("/api/admin/payments/999/confirm", json={}).status_code == 404


def test_the_admin_can_download_the_private_proof_file(
    db: Session, client_a: TestClient, client_a_row: Client, admin_client: TestClient
):
    # api_env already points STORAGE_ROOT at this test's own tmp_path.
    invoice = make_invoice(db, client_a_row)
    payment_id = client_a.post(
        f"/api/billing/invoices/{invoice.id}/payments",
        data=FORM,
        files={"proof": ("screenshot.png", PNG_BYTES, "image/png")},
    ).json()["id"]

    response = admin_client.get(f"/api/admin/payments/{payment_id}/proof")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content == PNG_BYTES


def test_asking_for_a_proof_that_was_never_uploaded_is_404(
    db: Session, client_a: TestClient, client_a_row: Client, admin_client: TestClient
):
    _, payment_id = _client_submits(db, client_a, client_a_row)
    assert admin_client.get(f"/api/admin/payments/{payment_id}/proof").status_code == 404


def test_payment_method_crud_over_http(db: Session, admin_client: TestClient):
    make_method(db, "nayapay", is_active=False, sort_order=5)

    created = admin_client.post(
        "/api/admin/payment-methods",
        json={
            "type": "raast",
            "account_title": "Ali Raza",
            "account_identifier": "PK36SCBL0000001123456702",
            "instructions": "Any bank app -> Raast -> IBAN.",
            "sort_order": 1,
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["is_active"] is True

    listed = admin_client.get("/api/admin/payment-methods").json()
    assert [m["type"] for m in listed] == ["raast", "nayapay"]  # sort_order 1 then 5, inactive included

    patched = admin_client.patch(
        f"/api/admin/payment-methods/{created.json()['id']}",
        json={"is_active": False, "sort_order": 9},
    )
    assert patched.status_code == 200
    assert patched.json()["is_active"] is False
    assert patched.json()["sort_order"] == 9
    assert patched.json()["account_title"] == "Ali Raza"  # untouched by the patch
    db.expire_all()
    assert db.get(PaymentMethod, created.json()["id"]).is_active is False

    assert (
        admin_client.patch("/api/admin/payment-methods/999", json={"sort_order": 1}).status_code
        == 404
    )
    bad = admin_client.post(
        "/api/admin/payment-methods",
        json={"type": "paypal", "account_title": "x", "account_identifier": "y"},
    )
    assert bad.status_code == 422


def test_every_admin_decision_is_audited(
    db: Session, client_a: TestClient, client_a_row: Client, admin_client: TestClient
):
    _, payment_id = _client_submits(db, client_a, client_a_row)
    admin_client.post(f"/api/admin/payments/{payment_id}/confirm", json={"note": "ok"})
    admin_client.post(
        "/api/admin/payment-methods",
        json={
            "type": "raast",
            "account_title": "Ali Raza",
            "account_identifier": "PK36SCBL0000001123456702",
        },
    )

    db.expire_all()
    actions = [row.action for row in db.scalars(select(AuditLog).order_by(AuditLog.id))]
    assert actions == ["payment.confirm", "payment_method.create"]


def test_a_client_cannot_touch_the_admin_payment_routes(
    db: Session, client_a: TestClient, client_a_row: Client
):
    _, payment_id = _client_submits(db, client_a, client_a_row)

    assert client_a.get("/api/admin/payments?status=pending").status_code == 403
    assert client_a.post(f"/api/admin/payments/{payment_id}/confirm", json={}).status_code == 403
    assert client_a.get("/api/admin/payment-methods").status_code == 403
    assert (
        client_a.post(
            "/api/admin/payment-methods",
            json={"type": "raast", "account_title": "x", "account_identifier": "y"},
        ).status_code
        == 403
    )
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd backend && .venv/Scripts/python -m pytest tests/api/test_admin_payments_routes.py -v`
Expected: failures on `assert 404 == 200` for every `/api/admin/payments*` call.

- [ ] **Step 3: Add the routes to the admin router**

Add these imports to the top of `backend/app/routers/admin.py`, next to Stage 6's existing ones (and make sure `Client`, `Invoice` **and `Payment`** are all imported from `app.models` — Stage 6 already imports the first two):
```python
from fastapi import HTTPException, Response

from app.models import Client, Invoice, Payment
from app.schemas.billing import (
    AdminPaymentOut,
    PaymentMethodIn,
    PaymentMethodOut,
    PaymentMethodPatch,
    RejectRequest,
    ReviewRequest,
    admin_payment_out,
)
from app.services import payments as payments_service
from app.services.storage import get_storage
```

Append to `backend/app/routers/admin.py`, reusing Stage 6's existing `router` object and its `CurrentAdmin` / session-dependency style. If Stage 6 named the session alias something other than `SessionDep`, use that name — do not introduce a second alias:
```python
# --------------------------------------------------------------------------- manual payments

# Reverse of payments_service.PROOF_TYPES: extension -> content type.
_PROOF_MEDIA = {
    extension: content_type
    for content_type, (extension, _magic) in payments_service.PROOF_TYPES.items()
}


def _payment_row(session, payment: Payment) -> AdminPaymentOut:
    invoice = session.get(Invoice, payment.invoice_id)
    client = session.get(Client, payment.client_id)
    return admin_payment_out(payment, invoice, client)


@router.get("/payments", response_model=list[AdminPaymentOut])
def list_payments(admin: CurrentAdmin, session: SessionDep, status: str = "pending"):
    """?status=pending (the review queue, default) or ?status=all for the whole history."""
    rows = payments_service.list_pending_payments(session, None if status == "all" else status)
    return [admin_payment_out(row.payment, row.invoice, row.client) for row in rows]


@router.post("/payments/{payment_id}/confirm", response_model=AdminPaymentOut)
def confirm_payment(payment_id: int, body: ReviewRequest, admin: CurrentAdmin, session: SessionDep):
    """The ONLY way money is marked as received (docs/PLAN.md section 6, Stage 7, Rules)."""
    payment = payments_service.confirm_payment(session, admin, payment_id, body.note)
    return _payment_row(session, payment)


@router.post("/payments/{payment_id}/reject", response_model=AdminPaymentOut)
def reject_payment(payment_id: int, body: RejectRequest, admin: CurrentAdmin, session: SessionDep):
    payment = payments_service.reject_payment(session, admin, payment_id, body.note)
    return _payment_row(session, payment)


@router.get("/payments/{payment_id}/proof")
def get_payment_proof(payment_id: int, admin: CurrentAdmin, session: SessionDep) -> Response:
    payment = session.get(Payment, payment_id)
    if payment is None or not payment.proof_file_path:
        raise HTTPException(status_code=404, detail="no proof file for this payment")
    extension = payment.proof_file_path.rsplit(".", 1)[-1].lower()
    key = f"proofs/{payment.client_id}/{payment.id}.{extension}"
    return Response(
        content=get_storage().read(key),
        media_type=_PROOF_MEDIA.get(extension, "application/octet-stream"),
        headers={"Content-Disposition": f'inline; filename="proof-{payment.id}.{extension}"'},
    )


# --------------------------------------------------------------------------- payment methods


@router.get("/payment-methods", response_model=list[PaymentMethodOut])
def list_payment_methods(admin: CurrentAdmin, session: SessionDep):
    """Admins see inactive accounts too, so they can switch one back on."""
    return payments_service.list_payment_methods(session, active_only=False)


@router.post("/payment-methods", response_model=PaymentMethodOut, status_code=201)
def create_payment_method(body: PaymentMethodIn, admin: CurrentAdmin, session: SessionDep):
    return payments_service.create_payment_method(session, admin, body)


@router.patch("/payment-methods/{method_id}", response_model=PaymentMethodOut)
def update_payment_method(
    method_id: int, body: PaymentMethodPatch, admin: CurrentAdmin, session: SessionDep
):
    return payments_service.update_payment_method(session, admin, method_id, body)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && .venv/Scripts/python -m pytest tests/api/test_admin_payments_routes.py -v`
Expected: `10 passed`.

- [ ] **Step 5: Run the whole backend suite so Stage 6's tests still pass**

Run: `cd backend && .venv/Scripts/python -m pytest -q`
Expected: every test passes; no import or route-name errors from the edited `admin.py`.

- [ ] **Step 6: Lint and commit**

Run: `cd backend && .venv/Scripts/ruff check . && .venv/Scripts/ruff format .`
```bash
git add backend/app/routers/admin.py backend/tests/api/test_admin_payments_routes.py
git commit -m "feat(admin): payment review queue, proof download and payment-method CRUD" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 7: The whole billing month, end to end

**Files:**
- Test: `backend/tests/api/test_billing_e2e.py`

**Interfaces:**
- Consumes: Stage 6's `app/services/billing.py` — `draft_invoice(session, actor, client_id, period_start, period_end)`, `confirm_invoice(session, actor, invoice_id, confirmed_recovered_waste)`, `issue_invoice(session, actor, invoice_id, due_date)` — for the admin half of the month, and Stage 7's HTTP API for everything else. Driving Stage 6 through its *service* functions rather than its HTTP shapes keeps this test on the contract documented in `INTERFACES.md`.
- Produces: no new source. This is the executable form of `docs/PLAN.md` §6 Stage 7 *Done when*.

- [ ] **Step 1: Write the test**

`backend/tests/api/test_billing_e2e.py`:
```python
"""docs/PLAN.md section 6, Stage 7, "Done when" — every bullet, in one month-long flow."""

from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditLog, Client, Invoice, User
from app.services.billing import confirm_invoice, draft_invoice, issue_invoice
from tests.api.helpers import make_invoice, make_method


def _issued_invoice(db: Session, admin: User, client: Client) -> Invoice:
    """Admin drafts September, confirms 23,000 of recovered waste, then issues.

    Commits at the end, because the HTTP calls that follow run on their own Session.
    """
    invoice = draft_invoice(db, admin, client.id, date(2026, 9, 1), date(2026, 9, 30))
    assert invoice.status == "draft"
    invoice = confirm_invoice(db, admin, invoice.id, Decimal("23000.00"))
    assert invoice.performance_fee == Decimal("4600.00")  # 20% of 23,000
    assert invoice.total == Decimal("19600.00")  # + the 15,000 base fee
    assert invoice.status == "draft"  # confirming a fee does not issue the invoice
    invoice = issue_invoice(db, admin, invoice.id, date(2026, 10, 7))
    assert invoice.status == "issued"
    db.commit()
    return invoice


def test_a_full_month_runs_generate_issue_submit_confirm_paid(
    db: Session,
    client_a: TestClient,
    client_a_row: Client,
    admin_client: TestClient,
    admin_row: User,
):
    make_method(db, "jazzcash", sort_order=0)
    invoice = _issued_invoice(db, admin_row, client_a_row)

    # 1. The client sees the invoice and where to pay.
    listed = client_a.get("/api/billing/invoices").json()
    assert [row["invoice_number"] for row in listed] == [invoice.invoice_number]
    detail = client_a.get(f"/api/billing/invoices/{invoice.id}").json()
    assert detail["total"] == "19600.00"
    assert detail["instructions"][0]["account_identifier"] == "03001234567"
    assert client_a.get(f"/api/billing/invoices/{invoice.id}/pdf").content.startswith(b"%PDF-")

    # 2. The client pays 10,000 and reports the transaction ID.
    first = client_a.post(
        f"/api/billing/invoices/{invoice.id}/payments",
        data={
            "method_type": "jazzcash",
            "transaction_ref": "JC-90001",
            "amount": "10000.00",
            "paid_at": "2026-10-02",
        },
    )
    assert first.status_code == 201
    db.expire_all()
    submitted = db.get(Invoice, invoice.id)
    assert submitted.status == "payment_submitted"
    assert submitted.amount_paid == Decimal("0.00")  # a claim never marks money as received

    # 3. A partial payment leaves the invoice unpaid.
    admin_client.post(
        f"/api/admin/payments/{first.json()['id']}/confirm", json={"note": "JazzCash app"}
    )
    db.expire_all()
    after_partial = db.get(Invoice, invoice.id)
    assert after_partial.amount_paid == Decimal("10000.00")
    assert after_partial.status == "issued"
    assert client_a.get(f"/api/billing/invoices/{invoice.id}").json()["amount_due"] == "9600.00"

    # 4. The same transaction ID cannot be reused.
    reused = client_a.post(
        f"/api/billing/invoices/{invoice.id}/payments",
        data={
            "method_type": "jazzcash",
            "transaction_ref": "JC-90001",
            "amount": "9600.00",
            "paid_at": "2026-10-05",
        },
    )
    assert reused.status_code == 409

    # 5. The rest is paid and confirmed -> the invoice is paid.
    second = client_a.post(
        f"/api/billing/invoices/{invoice.id}/payments",
        data={
            "method_type": "jazzcash",
            "transaction_ref": "JC-90002",
            "amount": "9600.00",
            "paid_at": "2026-10-05",
        },
    )
    admin_client.post(f"/api/admin/payments/{second.json()['id']}/confirm", json={})

    db.expire_all()
    final = db.get(Invoice, invoice.id)
    assert final.amount_paid == Decimal("19600.00")
    assert final.status == "paid"
    assert client_a.get(f"/api/billing/invoices/{invoice.id}").json()["is_overdue"] is False

    # 6. Every decision is on the record.
    actions = [row.action for row in db.scalars(select(AuditLog).order_by(AuditLog.id))]
    assert actions.count("payment.confirm") == 2
    assert "invoice.issue" in actions


def test_another_client_cannot_see_or_pay_this_invoice(
    db: Session, client_b: TestClient, client_a_row: Client, admin_row: User
):
    make_method(db)
    invoice = _issued_invoice(db, admin_row, client_a_row)

    assert client_b.get("/api/billing/invoices").json() == []
    assert client_b.get(f"/api/billing/invoices/{invoice.id}").status_code == 404
    assert (
        client_b.post(
            f"/api/billing/invoices/{invoice.id}/payments",
            data={
                "method_type": "jazzcash",
                "transaction_ref": "JC-99999",
                "amount": "100.00",
                "paid_at": "2026-10-02",
            },
        ).status_code
        == 404
    )
```

- [ ] **Step 2: Run it**

Run: `cd backend && .venv/Scripts/python -m pytest tests/api/test_billing_e2e.py -v`
Expected: `2 passed`.

If `draft_invoice` raises because the client has no approved analysis runs, that is a Stage 6 bug, not a Stage 7 one: `suggest_recovered_waste` is specified to return `0` when either run is missing (`INTERFACES.md`, Stage 6). Fix Stage 6 rather than working around it here.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/api/test_billing_e2e.py
git commit -m "test(billing): end-to-end month from draft invoice to paid" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 8: Frontend billing helpers — `src/lib/billing.ts`, types, and the FormData fix in `apiFetch`

**Files:**
- Create: `frontend/src/lib/billing.ts`, `frontend/src/lib/billing.test.ts`
- Modify: `frontend/src/lib/types.ts`, `frontend/src/lib/api.ts`
- Create (only if Stage 4 did not): `frontend/vitest.config.ts`, `frontend/vitest.setup.ts`, the `test` script in `frontend/package.json`

**Interfaces:**
- Consumes: `apiFetch<T>(path, init?)` and `formatPKR(n: number)` from Stage 4 (`src/lib/api.ts`, `src/lib/format.ts`).
- Produces:
  ```ts
  // src/lib/types.ts
  type InvoiceStatus = "draft" | "issued" | "payment_submitted" | "paid" | "void";
  type MethodType = "jazzcash" | "easypaisa" | "nayapay" | "raast" | "bank_iban";
  interface PaymentInstruction { method_type: MethodType; account_title: string; account_identifier: string; instructions: string | null }
  interface PaymentMethod { id: number; type: MethodType; account_title: string; account_identifier: string; instructions: string | null; is_active: boolean; sort_order: number }
  interface Payment { id: number; method_type: MethodType; transaction_ref: string; amount: string; paid_at: string;
                      status: "pending" | "confirmed" | "rejected"; review_note: string | null; reviewed_at: string | null;
                      created_at: string; has_proof: boolean }
  interface Invoice { id: number; invoice_number: string; period_start: string; period_end: string; due_date: string;
                      base_fee: string; confirmed_recovered_waste: string; performance_fee: string; total: string;
                      amount_paid: string; amount_due: string; status: InvoiceStatus; issued_at: string | null;
                      created_at: string; is_overdue: boolean; payments: Payment[]; instructions: PaymentInstruction[] }
  interface AdminPayment extends Payment { client_id: number; business_name: string; invoice_id: number;
                      invoice_number: string; invoice_total: string; invoice_due_date: string;
                      invoice_status: InvoiceStatus; invoice_is_overdue: boolean }

  // src/lib/billing.ts
  METHOD_LABELS: Record<MethodType, string>
  STATUS_LABELS: Record<InvoiceStatus, string>
  STATUS_PILL: Record<InvoiceStatus, string>          // Tailwind classes
  toISODate(d: Date): string                           // local calendar date, "YYYY-MM-DD"
  isOverdue(invoice: Pick<Invoice, "due_date" | "status">, today: Date): boolean
  amountDue(invoice: Pick<Invoice, "total" | "amount_paid">): number
  ```

Every money field arrives from FastAPI as a **string** (Pydantic serialises `Decimal` as a string so no rupee is lost to a float). Convert with `Number(...)` only at the moment of formatting.

- [ ] **Step 1: Make sure Vitest is available**

Run: `cd frontend && test -f vitest.config.ts && echo HAVE_VITEST || echo NEED_VITEST`
Expected: `HAVE_VITEST` if Stage 4 set it up — in that case skip the rest of this step.

If it printed `NEED_VITEST`:
```bash
cd frontend && npm install -D vitest @vitejs/plugin-react jsdom @testing-library/react @testing-library/user-event @testing-library/jest-dom
```
Create `frontend/vitest.config.ts`:
```ts
import path from "node:path";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { "@": path.resolve(__dirname, "src") } },
  test: {
    environment: "jsdom",
    globals: false,
    setupFiles: ["./vitest.setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
  },
});
```
Create `frontend/vitest.setup.ts`:
```ts
import "@testing-library/jest-dom/vitest";
```
Add to `"scripts"` in `frontend/package.json`:
```json
    "test": "vitest run",
```

- [ ] **Step 2: Write the failing test**

`frontend/src/lib/billing.test.ts`:
```ts
import { describe, expect, it } from "vitest";

import { amountDue, isOverdue, METHOD_LABELS, STATUS_LABELS, toISODate } from "@/lib/billing";

const unpaid = { due_date: "2026-10-07", status: "issued" } as const;

describe("isOverdue", () => {
  it("is false before the due date", () => {
    expect(isOverdue(unpaid, new Date(2026, 9, 6))).toBe(false);
  });

  it("is false on the due date itself — the client still has that day", () => {
    expect(isOverdue(unpaid, new Date(2026, 9, 7))).toBe(false);
  });

  it("is true the day after the due date", () => {
    expect(isOverdue(unpaid, new Date(2026, 9, 8))).toBe(true);
  });

  it("is true while a submitted payment is still awaiting confirmation", () => {
    expect(isOverdue({ due_date: "2026-10-07", status: "payment_submitted" }, new Date(2026, 9, 8))).toBe(true);
  });

  it("is false once the invoice is paid or void, however old it is", () => {
    expect(isOverdue({ due_date: "2020-01-01", status: "paid" }, new Date(2026, 9, 8))).toBe(false);
    expect(isOverdue({ due_date: "2020-01-01", status: "void" }, new Date(2026, 9, 8))).toBe(false);
  });

  it("uses the viewer's local calendar date, not UTC", () => {
    // 23:30 local on the due date is still the due date, whatever the timezone offset.
    expect(isOverdue(unpaid, new Date(2026, 9, 7, 23, 30))).toBe(false);
    expect(toISODate(new Date(2026, 9, 7, 23, 30))).toBe("2026-10-07");
  });
});

describe("amountDue", () => {
  it("subtracts what has been confirmed from the total", () => {
    expect(amountDue({ total: "19600.00", amount_paid: "10000.00" })).toBe(9600);
    expect(amountDue({ total: "19600.00", amount_paid: "19600.00" })).toBe(0);
  });
});

describe("labels", () => {
  it("names every method and status a client can see", () => {
    expect(METHOD_LABELS.jazzcash).toBe("JazzCash");
    expect(METHOD_LABELS.bank_iban).toBe("Bank transfer (IBAN)");
    expect(STATUS_LABELS.payment_submitted).toBe("Awaiting confirmation");
    expect(STATUS_LABELS.issued).toBe("Unpaid");
  });
});
```

- [ ] **Step 3: Run it and watch it fail**

Run: `cd frontend && npx vitest run src/lib/billing.test.ts`
Expected: `Failed to resolve import "@/lib/billing"`.

- [ ] **Step 4: Write the helpers**

`frontend/src/lib/billing.ts`:
```ts
import type { Invoice, InvoiceStatus, MethodType } from "@/lib/types";

export const METHOD_LABELS: Record<MethodType, string> = {
  jazzcash: "JazzCash",
  easypaisa: "Easypaisa",
  nayapay: "NayaPay",
  raast: "Raast",
  bank_iban: "Bank transfer (IBAN)",
};

export const STATUS_LABELS: Record<InvoiceStatus, string> = {
  draft: "Draft",
  issued: "Unpaid",
  payment_submitted: "Awaiting confirmation",
  paid: "Paid",
  void: "Void",
};

export const STATUS_PILL: Record<InvoiceStatus, string> = {
  draft: "bg-slate/20 text-slate",
  issued: "bg-slate/20 text-paper",
  payment_submitted: "bg-teal/20 text-teal",
  paid: "bg-teal text-ink",
  void: "bg-slate/20 text-slate",
};

/** The viewer's local calendar date as YYYY-MM-DD. `toISOString()` would shift by the UTC offset. */
export function toISODate(date: Date): string {
  const month = `${date.getMonth() + 1}`.padStart(2, "0");
  const day = `${date.getDate()}`.padStart(2, "0");
  return `${date.getFullYear()}-${month}-${day}`;
}

/** Past the due date and still owed. Both sides are YYYY-MM-DD, so a string compare is a date compare. */
export function isOverdue(invoice: Pick<Invoice, "due_date" | "status">, today: Date): boolean {
  if (invoice.status === "paid" || invoice.status === "void") return false;
  return invoice.due_date < toISODate(today);
}

export function amountDue(invoice: Pick<Invoice, "total" | "amount_paid">): number {
  return Number(invoice.total) - Number(invoice.amount_paid);
}
```

- [ ] **Step 5: Add the types**

Append to `frontend/src/lib/types.ts` the eight declarations listed in this task's **Produces** block, verbatim.

- [ ] **Step 6: Let `apiFetch` send multipart bodies**

Open `frontend/src/lib/api.ts`. If it sets a `Content-Type` header unconditionally, the browser cannot add the multipart boundary and every proof upload fails. The body must decide:
```ts
export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const isForm = init.body instanceof FormData;
  const response = await fetch(path, {
    ...init,
    credentials: "include",
    headers: isForm
      ? init.headers
      : { "Content-Type": "application/json", ...(init.headers ?? {}) },
  });
  if (!response.ok) {
    const detail = await response.json().catch(() => ({}));
    throw new ApiError(response.status, detail?.detail ?? response.statusText);
  }
  return response.status === 204 ? (undefined as T) : ((await response.json()) as T);
}
```
Keep Stage 4's `ApiError` class and its exported shape exactly as they are — only the header logic changes.

- [ ] **Step 7: Run the tests to verify they pass**

Run: `cd frontend && npx vitest run src/lib/billing.test.ts`
Expected: `Test Files 1 passed`, `Tests 9 passed`.

- [ ] **Step 8: Typecheck, lint and commit**

Run: `cd frontend && npx tsc --noEmit && npm run lint`
Expected: no output from `tsc`, `No ESLint warnings or errors`.
```bash
git add frontend/src/lib frontend/package.json frontend/vitest.config.ts frontend/vitest.setup.ts
git commit -m "feat(billing): frontend billing helpers and multipart-safe apiFetch" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 9: `/dashboard/billing` — invoice list, detail, and the submit-payment form

**Files:**
- Create: `frontend/src/components/billing/StatusPill.tsx`, `InvoiceTable.tsx`, `PaymentInstructions.tsx`, `PaymentHistory.tsx`, `PaymentForm.tsx`, `InvoiceDetail.tsx`
- Create: `frontend/src/components/billing/PaymentForm.test.tsx`
- Create: `frontend/src/app/dashboard/billing/page.tsx`

**Interfaces:**
- Consumes: `apiFetch`, `formatPKR`, `isOverdue`, `amountDue`, `METHOD_LABELS`, `STATUS_LABELS`, `STATUS_PILL`, the types from Task 8, and the routes from Task 5.
- Produces:
  ```tsx
  <StatusPill status={InvoiceStatus} />
  <InvoiceTable invoices={Invoice[]} selectedId={number | null} onSelect={(id: number) => void} />
  <PaymentInstructions instructions={PaymentInstruction[]} />
  <PaymentHistory payments={Payment[]} />
  <PaymentForm invoiceId={number} methods={PaymentMethod[]} defaultAmount={number} onSubmitted={() => void} />
  <InvoiceDetail invoice={Invoice} methods={PaymentMethod[]} onSubmitted={() => void} />
  export default function BillingPage()   // route /dashboard/billing
  ```

A working view: a plain table, hairline dividers, no hero and no animation (`docs/PLAN.md` §6, Stage 6 "No animation, dense tables" — the same discipline applies to billing).

- [ ] **Step 1: Write the failing test**

`frontend/src/components/billing/PaymentForm.test.tsx`:
```tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api", () => ({
  apiFetch: vi.fn().mockResolvedValue({ id: 11, status: "pending" }),
  ApiError: class ApiError extends Error {
    constructor(public status: number, message: string) {
      super(message);
    }
  },
}));

import { apiFetch } from "@/lib/api";
import PaymentForm from "@/components/billing/PaymentForm";
import type { PaymentMethod } from "@/lib/types";

const METHODS: PaymentMethod[] = [
  {
    id: 1,
    type: "jazzcash",
    account_title: "Ali Raza",
    account_identifier: "0300-1234567",
    instructions: null,
    is_active: true,
    sort_order: 0,
  },
  {
    id: 2,
    type: "raast",
    account_title: "Ali Raza",
    account_identifier: "PK36SCBL0000001123456702",
    instructions: null,
    is_active: true,
    sort_order: 1,
  },
];

function lastCall() {
  const mock = vi.mocked(apiFetch);
  return mock.mock.calls[mock.mock.calls.length - 1];
}

describe("PaymentForm", () => {
  beforeEach(() => {
    vi.mocked(apiFetch).mockClear();
  });

  it("posts the transaction ID as multipart FormData to the invoice's payments route", async () => {
    const user = userEvent.setup();
    const onSubmitted = vi.fn();
    render(<PaymentForm invoiceId={7} methods={METHODS} defaultAmount={9600} onSubmitted={onSubmitted} />);

    await user.selectOptions(screen.getByLabelText(/payment method/i), "raast");
    await user.clear(screen.getByLabelText(/transaction id/i));
    await user.type(screen.getByLabelText(/transaction id/i), "JC-90002");
    await user.clear(screen.getByLabelText(/amount/i));
    await user.type(screen.getByLabelText(/amount/i), "9600");
    await user.clear(screen.getByLabelText(/payment date/i));
    await user.type(screen.getByLabelText(/payment date/i), "2026-10-05");
    await user.click(screen.getByRole("button", { name: /submit payment/i }));

    const [path, init] = lastCall();
    expect(path).toBe("/api/billing/invoices/7/payments");
    expect(init?.method).toBe("POST");
    const body = init?.body as FormData;
    expect(body).toBeInstanceOf(FormData);
    expect(body.get("method_type")).toBe("raast");
    expect(body.get("transaction_ref")).toBe("JC-90002");
    expect(body.get("amount")).toBe("9600");
    expect(body.get("paid_at")).toBe("2026-10-05");
    expect(body.get("proof")).toBeNull();
    expect(onSubmitted).toHaveBeenCalledOnce();
  });

  it("attaches the screenshot when one is chosen", async () => {
    const user = userEvent.setup();
    render(<PaymentForm invoiceId={7} methods={METHODS} defaultAmount={9600} onSubmitted={vi.fn()} />);
    const file = new File([new Uint8Array([0x89, 0x50, 0x4e, 0x47])], "proof.png", { type: "image/png" });

    await user.type(screen.getByLabelText(/transaction id/i), "JC-90003");
    await user.upload(screen.getByLabelText(/screenshot/i), file);
    await user.click(screen.getByRole("button", { name: /submit payment/i }));

    const body = lastCall()[1]?.body as FormData;
    expect((body.get("proof") as File).name).toBe("proof.png");
  });

  it("defaults the amount to what is still owed and refuses an empty transaction id", async () => {
    const user = userEvent.setup();
    render(<PaymentForm invoiceId={7} methods={METHODS} defaultAmount={9600} onSubmitted={vi.fn()} />);

    expect(screen.getByLabelText(/amount/i)).toHaveValue(9600);

    await user.click(screen.getByRole("button", { name: /submit payment/i }));
    expect(apiFetch).not.toHaveBeenCalled();
    expect(screen.getByRole("alert")).toHaveTextContent(/transaction id/i);
  });

  it("shows the server's reason when the transaction id was already used", async () => {
    const user = userEvent.setup();
    vi.mocked(apiFetch).mockRejectedValueOnce(
      Object.assign(new Error("this transaction id has already been submitted for this payment method"), {
        status: 409,
      }),
    );
    render(<PaymentForm invoiceId={7} methods={METHODS} defaultAmount={9600} onSubmitted={vi.fn()} />);

    await user.type(screen.getByLabelText(/transaction id/i), "JC-90001");
    await user.click(screen.getByRole("button", { name: /submit payment/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/already been submitted/i);
  });
});
```

- [ ] **Step 2: Run it and watch it fail**

Run: `cd frontend && npx vitest run src/components/billing/PaymentForm.test.tsx`
Expected: `Failed to resolve import "@/components/billing/PaymentForm"`.

- [ ] **Step 3: Write `PaymentForm`**

`frontend/src/components/billing/PaymentForm.tsx`:
```tsx
"use client";

import { useState } from "react";

import { apiFetch } from "@/lib/api";
import { METHOD_LABELS } from "@/lib/billing";
import type { Payment, PaymentMethod } from "@/lib/types";

type Props = {
  invoiceId: number;
  methods: PaymentMethod[];
  defaultAmount: number;
  onSubmitted: () => void;
};

const FIELD =
  "w-full rounded border border-slate/40 bg-ink px-3 py-2 text-paper focus:border-teal focus:outline-none";

export default function PaymentForm({ invoiceId, methods, defaultAmount, onSubmitted }: Props) {
  const [methodType, setMethodType] = useState(methods[0]?.type ?? "jazzcash");
  const [transactionRef, setTransactionRef] = useState("");
  const [amount, setAmount] = useState(String(defaultAmount));
  const [paidAt, setPaidAt] = useState("");
  const [proof, setProof] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!transactionRef.trim()) {
      setError("Enter the transaction ID from your payment app.");
      return;
    }
    const form = new FormData();
    form.set("method_type", methodType);
    form.set("transaction_ref", transactionRef.trim());
    form.set("amount", amount);
    form.set("paid_at", paidAt);
    if (proof) form.set("proof", proof);

    setBusy(true);
    setError(null);
    try {
      await apiFetch<Payment>(`/api/billing/invoices/${invoiceId}/payments`, {
        method: "POST",
        body: form,
      });
      setTransactionRef("");
      setProof(null);
      onSubmitted();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not submit this payment.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="grid gap-3" noValidate>
      <h3 className="font-display text-lg">I have paid — record my transaction ID</h3>

      <label className="grid gap-1 text-sm">
        <span className="text-slate">Payment method</span>
        <select
          className={FIELD}
          value={methodType}
          onChange={(event) => setMethodType(event.target.value as PaymentMethod["type"])}
        >
          {methods.map((method) => (
            <option key={method.id} value={method.type}>
              {METHOD_LABELS[method.type]} — {method.account_identifier}
            </option>
          ))}
        </select>
      </label>

      <label className="grid gap-1 text-sm">
        <span className="text-slate">Transaction ID</span>
        <input
          className={FIELD}
          value={transactionRef}
          onChange={(event) => setTransactionRef(event.target.value)}
          maxLength={80}
        />
      </label>

      <div className="grid gap-3 sm:grid-cols-2">
        <label className="grid gap-1 text-sm">
          <span className="text-slate">Amount (PKR)</span>
          <input
            className={FIELD}
            type="number"
            min="0.01"
            step="0.01"
            value={amount}
            onChange={(event) => setAmount(event.target.value)}
          />
        </label>
        <label className="grid gap-1 text-sm">
          <span className="text-slate">Payment date</span>
          <input
            className={FIELD}
            type="date"
            value={paidAt}
            onChange={(event) => setPaidAt(event.target.value)}
          />
        </label>
      </div>

      <label className="grid gap-1 text-sm">
        <span className="text-slate">Screenshot or receipt (optional, PNG/JPEG/PDF, max 5 MB)</span>
        <input
          className={FIELD}
          type="file"
          accept="image/png,image/jpeg,application/pdf"
          onChange={(event) => setProof(event.target.files?.[0] ?? null)}
        />
      </label>

      {error ? (
        <p role="alert" className="text-sm text-coral">
          {error}
        </p>
      ) : null}

      <button
        type="submit"
        disabled={busy}
        className="justify-self-start rounded bg-teal px-4 py-2 font-medium text-ink disabled:opacity-50"
      >
        {busy ? "Submitting…" : "Submit payment"}
      </button>
      <p className="text-xs text-slate">
        We confirm every payment by hand. The invoice stays open until we have checked it.
      </p>
    </form>
  );
}
```

- [ ] **Step 4: Run the form tests to verify they pass**

Run: `cd frontend && npx vitest run src/components/billing/PaymentForm.test.tsx`
Expected: `Tests 4 passed`.

- [ ] **Step 5: Write the remaining billing components**

`frontend/src/components/billing/StatusPill.tsx`:
```tsx
import { STATUS_LABELS, STATUS_PILL } from "@/lib/billing";
import type { InvoiceStatus } from "@/lib/types";

export default function StatusPill({ status }: { status: InvoiceStatus }) {
  return (
    <span className={`inline-block rounded-full px-2 py-0.5 text-xs ${STATUS_PILL[status]}`}>
      {STATUS_LABELS[status]}
    </span>
  );
}
```

`frontend/src/components/billing/InvoiceTable.tsx`:
```tsx
"use client";

import StatusPill from "@/components/billing/StatusPill";
import { isOverdue } from "@/lib/billing";
import { formatPKR } from "@/lib/format";
import type { Invoice } from "@/lib/types";

type Props = {
  invoices: Invoice[];
  selectedId: number | null;
  onSelect: (id: number) => void;
};

export default function InvoiceTable({ invoices, selectedId, onSelect }: Props) {
  const today = new Date();
  if (invoices.length === 0) {
    return <p className="text-slate">No invoices yet. Your first one arrives after your first full month.</p>;
  }
  return (
    <table className="w-full text-left text-sm">
      <thead className="text-slate">
        <tr className="border-b border-slate/30">
          <th className="py-2 font-normal">Invoice</th>
          <th className="py-2 font-normal">Period</th>
          <th className="py-2 font-normal">Due</th>
          <th className="py-2 text-right font-normal">Total</th>
          <th className="py-2 text-right font-normal">Outstanding</th>
          <th className="py-2 font-normal">Status</th>
        </tr>
      </thead>
      <tbody>
        {invoices.map((invoice) => (
          <tr
            key={invoice.id}
            onClick={() => onSelect(invoice.id)}
            className={`cursor-pointer border-b border-slate/15 hover:bg-surface ${
              invoice.id === selectedId ? "bg-surface" : ""
            }`}
          >
            <td className="py-2 numeral">{invoice.invoice_number}</td>
            <td className="py-2">
              {invoice.period_start} → {invoice.period_end}
            </td>
            <td className="py-2">
              {invoice.due_date}
              {isOverdue(invoice, today) ? (
                <span className="ml-2 rounded-full bg-coral/20 px-2 py-0.5 text-xs text-coral">Overdue</span>
              ) : null}
            </td>
            <td className="py-2 text-right numeral">{formatPKR(Number(invoice.total))}</td>
            <td className="py-2 text-right numeral">{formatPKR(Number(invoice.amount_due))}</td>
            <td className="py-2">
              <StatusPill status={invoice.status} />
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
```

`frontend/src/components/billing/PaymentInstructions.tsx`:
```tsx
"use client";

import { useState } from "react";

import { METHOD_LABELS } from "@/lib/billing";
import type { PaymentInstruction } from "@/lib/types";

export default function PaymentInstructions({ instructions }: { instructions: PaymentInstruction[] }) {
  const [copied, setCopied] = useState<string | null>(null);

  async function copy(value: string) {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(value);
      window.setTimeout(() => setCopied(null), 2000);
    } catch {
      setCopied(null); // clipboard blocked (http, or permission denied) — the number is on screen anyway
    }
  }

  if (instructions.length === 0) {
    return <p className="text-slate">No payment accounts are set up yet — contact us before paying.</p>;
  }

  return (
    <ul className="grid gap-3">
      {instructions.map((instruction) => (
        <li key={`${instruction.method_type}-${instruction.account_identifier}`} className="border-b border-slate/15 pb-3">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-medium">{METHOD_LABELS[instruction.method_type]}</span>
            <span className="numeral">{instruction.account_identifier}</span>
            <button
              type="button"
              onClick={() => copy(instruction.account_identifier)}
              className="rounded border border-slate/40 px-2 py-0.5 text-xs text-slate hover:border-teal hover:text-teal"
            >
              {copied === instruction.account_identifier ? "Copied" : "Copy"}
            </button>
          </div>
          <p className="text-sm text-slate">{instruction.account_title}</p>
          {instruction.instructions ? <p className="text-sm text-slate">{instruction.instructions}</p> : null}
        </li>
      ))}
    </ul>
  );
}
```

`frontend/src/components/billing/PaymentHistory.tsx`:
```tsx
import { METHOD_LABELS } from "@/lib/billing";
import { formatPKR } from "@/lib/format";
import type { Payment } from "@/lib/types";

const PAYMENT_TONE: Record<Payment["status"], string> = {
  pending: "text-slate",
  confirmed: "text-teal",
  rejected: "text-coral",
};

export default function PaymentHistory({ payments }: { payments: Payment[] }) {
  if (payments.length === 0) {
    return <p className="text-slate">No payments reported yet.</p>;
  }
  return (
    <ul className="grid gap-2 text-sm">
      {payments.map((payment) => (
        <li key={payment.id} className="border-b border-slate/15 pb-2">
          <div className="flex flex-wrap justify-between gap-2">
            <span className="numeral">
              {METHOD_LABELS[payment.method_type]} · {payment.transaction_ref}
            </span>
            <span className="numeral">{formatPKR(Number(payment.amount))}</span>
          </div>
          <div className="flex flex-wrap justify-between gap-2 text-xs">
            <span className="text-slate">
              Paid {payment.paid_at}
              {payment.has_proof ? " · proof attached" : ""}
            </span>
            <span className={PAYMENT_TONE[payment.status]}>{payment.status}</span>
          </div>
          {payment.status === "rejected" && payment.review_note ? (
            <p className="text-xs text-coral">Rejected: {payment.review_note}</p>
          ) : null}
        </li>
      ))}
    </ul>
  );
}
```

`frontend/src/components/billing/InvoiceDetail.tsx`:
```tsx
"use client";

import PaymentForm from "@/components/billing/PaymentForm";
import PaymentHistory from "@/components/billing/PaymentHistory";
import PaymentInstructions from "@/components/billing/PaymentInstructions";
import StatusPill from "@/components/billing/StatusPill";
import { isOverdue } from "@/lib/billing";
import { formatPKR } from "@/lib/format";
import type { Invoice, PaymentMethod } from "@/lib/types";

type Props = {
  invoice: Invoice;
  methods: PaymentMethod[];
  onSubmitted: () => void;
};

export default function InvoiceDetail({ invoice, methods, onSubmitted }: Props) {
  const payable = invoice.status === "issued" || invoice.status === "payment_submitted";
  return (
    <section className="grid gap-6 rounded border border-slate/25 bg-surface p-5">
      <header className="grid gap-1">
        <div className="flex flex-wrap items-center gap-3">
          <h2 className="font-display text-xl numeral">{invoice.invoice_number}</h2>
          <StatusPill status={invoice.status} />
          {isOverdue(invoice, new Date()) ? (
            <span className="rounded-full bg-coral/20 px-2 py-0.5 text-xs text-coral">Overdue</span>
          ) : null}
        </div>
        <p className="text-sm text-slate">
          {invoice.period_start} → {invoice.period_end} · due {invoice.due_date}
        </p>
      </header>

      <dl className="grid gap-2 text-sm">
        <div className="flex justify-between border-b border-slate/15 pb-1">
          <dt>Monthly base fee</dt>
          <dd className="numeral">{formatPKR(Number(invoice.base_fee))}</dd>
        </div>
        <div className="flex justify-between border-b border-slate/15 pb-1">
          <dt>Performance fee on {formatPKR(Number(invoice.confirmed_recovered_waste))} recovered</dt>
          <dd className="numeral">{formatPKR(Number(invoice.performance_fee))}</dd>
        </div>
        <div className="flex justify-between border-b border-slate/15 pb-1">
          <dt>Total</dt>
          <dd className="numeral">{formatPKR(Number(invoice.total))}</dd>
        </div>
        <div className="flex justify-between border-b border-slate/15 pb-1">
          <dt>Confirmed payments</dt>
          <dd className="numeral">{formatPKR(Number(invoice.amount_paid))}</dd>
        </div>
        <div className="flex justify-between font-medium">
          <dt>Still owed</dt>
          <dd className="numeral">{formatPKR(Number(invoice.amount_due))}</dd>
        </div>
      </dl>

      <a
        href={`/api/billing/invoices/${invoice.id}/pdf`}
        className="justify-self-start rounded border border-slate/40 px-3 py-1.5 text-sm hover:border-teal hover:text-teal"
      >
        Download PDF
      </a>

      <div className="grid gap-3">
        <h3 className="font-display text-lg">Where to pay</h3>
        <PaymentInstructions instructions={invoice.instructions} />
      </div>

      <div className="grid gap-3">
        <h3 className="font-display text-lg">Payment history</h3>
        <PaymentHistory payments={invoice.payments} />
      </div>

      {payable ? (
        <PaymentForm
          invoiceId={invoice.id}
          methods={methods}
          defaultAmount={Number(invoice.amount_due)}
          onSubmitted={onSubmitted}
        />
      ) : null}
    </section>
  );
}
```

`frontend/src/app/dashboard/billing/page.tsx`:
```tsx
"use client";

import { useCallback, useEffect, useState } from "react";

import InvoiceDetail from "@/components/billing/InvoiceDetail";
import InvoiceTable from "@/components/billing/InvoiceTable";
import { apiFetch } from "@/lib/api";
import type { Invoice, PaymentMethod } from "@/lib/types";

export default function BillingPage() {
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [methods, setMethods] = useState<PaymentMethod[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [selected, setSelected] = useState<Invoice | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadList = useCallback(async () => {
    try {
      const [rows, paymentMethods] = await Promise.all([
        apiFetch<Invoice[]>("/api/billing/invoices"),
        apiFetch<PaymentMethod[]>("/api/billing/payment-methods"),
      ]);
      setInvoices(rows);
      setMethods(paymentMethods);
      setSelectedId((current) => current ?? rows[0]?.id ?? null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not load your invoices.");
    }
  }, []);

  const loadSelected = useCallback(async () => {
    if (selectedId === null) {
      setSelected(null);
      return;
    }
    const invoice = await apiFetch<Invoice>(`/api/billing/invoices/${selectedId}`);
    setSelected(invoice);
  }, [selectedId]);

  useEffect(() => {
    void loadList();
  }, [loadList]);

  useEffect(() => {
    void loadSelected();
  }, [loadSelected]);

  const refresh = useCallback(async () => {
    await loadList();
    await loadSelected();
  }, [loadList, loadSelected]);

  return (
    <main className="mx-auto grid max-w-5xl gap-8 px-4 py-8">
      <h1 className="font-display text-2xl">Billing</h1>
      {error ? <p role="alert" className="text-coral">{error}</p> : null}
      <InvoiceTable invoices={invoices} selectedId={selectedId} onSelect={setSelectedId} />
      {selected ? <InvoiceDetail invoice={selected} methods={methods} onSubmitted={refresh} /> : null}
    </main>
  );
}
```

- [ ] **Step 6: Run everything, typecheck, lint and commit**

Run: `cd frontend && npx vitest run && npx tsc --noEmit && npm run lint`
Expected: all Vitest files pass, no `tsc` output, `No ESLint warnings or errors`.
```bash
git add frontend/src/components/billing frontend/src/app/dashboard/billing
git commit -m "feat(billing): client billing page with instructions, history and payment form" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 10: `/admin/payments` and `/admin/payment-methods`

**Files:**
- Create: `frontend/src/components/admin/PaymentQueue.tsx`, `frontend/src/components/admin/PaymentMethodTable.tsx`
- Create: `frontend/src/app/admin/payments/page.tsx`, `frontend/src/app/admin/payment-methods/page.tsx`

**Interfaces:**
- Consumes: `apiFetch`, `formatPKR`, `METHOD_LABELS` (Task 8), the admin routes from Task 6, `AdminPayment` / `PaymentMethod` types (Task 8).
- Produces:
  ```tsx
  <PaymentQueue payments={AdminPayment[]} onReviewed={() => void} />
  <PaymentMethodTable methods={PaymentMethod[]} onChanged={() => void} />
  export default function AdminPaymentsPage()        // route /admin/payments
  export default function AdminPaymentMethodsPage()  // route /admin/payment-methods
  ```

Dense tables, no animation — same rule as the rest of the admin panel.

- [ ] **Step 1: Write the payment queue**

`frontend/src/components/admin/PaymentQueue.tsx`:
```tsx
"use client";

import { useState } from "react";

import { apiFetch } from "@/lib/api";
import { METHOD_LABELS } from "@/lib/billing";
import { formatPKR } from "@/lib/format";
import type { AdminPayment } from "@/lib/types";

type Props = {
  payments: AdminPayment[];
  onReviewed: () => void;
};

export default function PaymentQueue({ payments, onReviewed }: Props) {
  const [notes, setNotes] = useState<Record<number, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);

  async function review(payment: AdminPayment, decision: "confirm" | "reject") {
    const note = (notes[payment.id] ?? "").trim();
    if (decision === "reject" && !note) {
      setError(`Say why you are rejecting ${payment.transaction_ref} — the client reads this note.`);
      return;
    }
    setBusyId(payment.id);
    setError(null);
    try {
      await apiFetch(`/api/admin/payments/${payment.id}/${decision}`, {
        method: "POST",
        body: JSON.stringify({ note: note || null }),
      });
      setNotes((current) => ({ ...current, [payment.id]: "" }));
      onReviewed();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not record that decision.");
    } finally {
      setBusyId(null);
    }
  }

  if (payments.length === 0) {
    return <p className="text-slate">Nothing waiting. Every reported payment has been reviewed.</p>;
  }

  return (
    <div className="grid gap-4">
      {error ? <p role="alert" className="text-coral">{error}</p> : null}
      <table className="w-full text-left text-sm">
        <thead className="text-slate">
          <tr className="border-b border-slate/30">
            <th className="py-2 font-normal">Client</th>
            <th className="py-2 font-normal">Invoice</th>
            <th className="py-2 font-normal">Method / transaction ID</th>
            <th className="py-2 text-right font-normal">Amount</th>
            <th className="py-2 font-normal">Paid</th>
            <th className="py-2 font-normal">Proof</th>
            <th className="py-2 font-normal">Decision</th>
          </tr>
        </thead>
        <tbody>
          {payments.map((payment) => (
            <tr key={payment.id} className="border-b border-slate/15 align-top">
              <td className="py-2">{payment.business_name}</td>
              <td className="py-2">
                <span className="numeral">{payment.invoice_number}</span>
                <br />
                <span className="text-xs text-slate">
                  {formatPKR(Number(payment.invoice_total))} · due {payment.invoice_due_date}
                </span>
                {payment.invoice_is_overdue ? (
                  <span className="ml-2 rounded-full bg-coral/20 px-2 py-0.5 text-xs text-coral">Overdue</span>
                ) : null}
              </td>
              <td className="py-2">
                {METHOD_LABELS[payment.method_type]}
                <br />
                <span className="numeral">{payment.transaction_ref}</span>
              </td>
              <td className="py-2 text-right numeral">{formatPKR(Number(payment.amount))}</td>
              <td className="py-2">{payment.paid_at}</td>
              <td className="py-2">
                {payment.has_proof ? (
                  <a
                    href={`/api/admin/payments/${payment.id}/proof`}
                    target="_blank"
                    rel="noreferrer"
                    className="text-teal underline"
                  >
                    View
                  </a>
                ) : (
                  <span className="text-slate">—</span>
                )}
              </td>
              <td className="py-2">
                <div className="grid gap-2">
                  <input
                    aria-label={`Note for ${payment.transaction_ref}`}
                    placeholder="Note (required to reject)"
                    className="rounded border border-slate/40 bg-ink px-2 py-1 text-paper"
                    value={notes[payment.id] ?? ""}
                    onChange={(event) =>
                      setNotes((current) => ({ ...current, [payment.id]: event.target.value }))
                    }
                  />
                  <div className="flex gap-2">
                    <button
                      type="button"
                      disabled={busyId === payment.id}
                      onClick={() => review(payment, "confirm")}
                      className="rounded bg-teal px-3 py-1 text-ink disabled:opacity-50"
                    >
                      Confirm
                    </button>
                    <button
                      type="button"
                      disabled={busyId === payment.id}
                      onClick={() => review(payment, "reject")}
                      className="rounded border border-coral px-3 py-1 text-coral disabled:opacity-50"
                    >
                      Reject
                    </button>
                  </div>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

`frontend/src/app/admin/payments/page.tsx`:
```tsx
"use client";

import { useCallback, useEffect, useState } from "react";

import PaymentQueue from "@/components/admin/PaymentQueue";
import { apiFetch } from "@/lib/api";
import type { AdminPayment } from "@/lib/types";

export default function AdminPaymentsPage() {
  const [payments, setPayments] = useState<AdminPayment[]>([]);
  const [showAll, setShowAll] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setPayments(await apiFetch<AdminPayment[]>(`/api/admin/payments?status=${showAll ? "all" : "pending"}`));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not load the payment queue.");
    }
  }, [showAll]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <main className="mx-auto grid max-w-6xl gap-6 px-4 py-8">
      <div className="flex items-center justify-between">
        <h1 className="font-display text-2xl">Payments</h1>
        <label className="flex items-center gap-2 text-sm text-slate">
          <input type="checkbox" checked={showAll} onChange={(event) => setShowAll(event.target.checked)} />
          Show reviewed payments too
        </label>
      </div>
      {error ? <p role="alert" className="text-coral">{error}</p> : null}
      <PaymentQueue payments={payments} onReviewed={load} />
    </main>
  );
}
```

- [ ] **Step 2: Write the payment-method table**

`frontend/src/components/admin/PaymentMethodTable.tsx`:
```tsx
"use client";

import { useState } from "react";

import { apiFetch } from "@/lib/api";
import { METHOD_LABELS } from "@/lib/billing";
import type { MethodType, PaymentMethod } from "@/lib/types";

const EMPTY = {
  type: "jazzcash" as MethodType,
  account_title: "",
  account_identifier: "",
  instructions: "",
  sort_order: 0,
};

const FIELD = "rounded border border-slate/40 bg-ink px-2 py-1 text-paper";

export default function PaymentMethodTable({
  methods,
  onChanged,
}: {
  methods: PaymentMethod[];
  onChanged: () => void;
}) {
  const [draft, setDraft] = useState(EMPTY);
  const [error, setError] = useState<string | null>(null);

  async function patch(method: PaymentMethod, body: Record<string, unknown>) {
    setError(null);
    try {
      await apiFetch(`/api/admin/payment-methods/${method.id}`, {
        method: "PATCH",
        body: JSON.stringify(body),
      });
      onChanged();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not update that account.");
    }
  }

  async function create(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    try {
      await apiFetch("/api/admin/payment-methods", {
        method: "POST",
        body: JSON.stringify({ ...draft, instructions: draft.instructions || null }),
      });
      setDraft(EMPTY);
      onChanged();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not add that account.");
    }
  }

  return (
    <div className="grid gap-6">
      {error ? <p role="alert" className="text-coral">{error}</p> : null}

      <table className="w-full text-left text-sm">
        <thead className="text-slate">
          <tr className="border-b border-slate/30">
            <th className="py-2 font-normal">Method</th>
            <th className="py-2 font-normal">Account title</th>
            <th className="py-2 font-normal">Account number / IBAN</th>
            <th className="py-2 font-normal">Order</th>
            <th className="py-2 font-normal">Shown to clients</th>
          </tr>
        </thead>
        <tbody>
          {methods.map((method) => (
            <tr key={method.id} className="border-b border-slate/15">
              <td className="py-2">{METHOD_LABELS[method.type]}</td>
              <td className="py-2">{method.account_title}</td>
              <td className="py-2 numeral">{method.account_identifier}</td>
              <td className="py-2">
                <input
                  aria-label={`Sort order for ${method.account_identifier}`}
                  type="number"
                  className={`${FIELD} w-20`}
                  defaultValue={method.sort_order}
                  onBlur={(event) => {
                    const next = Number(event.target.value);
                    if (next !== method.sort_order) void patch(method, { sort_order: next });
                  }}
                />
              </td>
              <td className="py-2">
                <button
                  type="button"
                  onClick={() => patch(method, { is_active: !method.is_active })}
                  className={`rounded px-3 py-1 ${
                    method.is_active ? "bg-teal text-ink" : "border border-slate/40 text-slate"
                  }`}
                >
                  {method.is_active ? "Active" : "Hidden"}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <form onSubmit={create} className="grid gap-3 rounded border border-slate/25 bg-surface p-4">
        <h2 className="font-display text-lg">Add an account</h2>
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="grid gap-1 text-sm">
            <span className="text-slate">Method</span>
            <select
              className={FIELD}
              value={draft.type}
              onChange={(event) => setDraft({ ...draft, type: event.target.value as MethodType })}
            >
              {(Object.keys(METHOD_LABELS) as MethodType[]).map((type) => (
                <option key={type} value={type}>
                  {METHOD_LABELS[type]}
                </option>
              ))}
            </select>
          </label>
          <label className="grid gap-1 text-sm">
            <span className="text-slate">Account title</span>
            <input
              className={FIELD}
              value={draft.account_title}
              onChange={(event) => setDraft({ ...draft, account_title: event.target.value })}
              required
            />
          </label>
          <label className="grid gap-1 text-sm">
            <span className="text-slate">Account number / IBAN</span>
            <input
              className={FIELD}
              value={draft.account_identifier}
              onChange={(event) => setDraft({ ...draft, account_identifier: event.target.value })}
              required
            />
          </label>
          <label className="grid gap-1 text-sm">
            <span className="text-slate">Sort order</span>
            <input
              className={FIELD}
              type="number"
              value={draft.sort_order}
              onChange={(event) => setDraft({ ...draft, sort_order: Number(event.target.value) })}
            />
          </label>
        </div>
        <label className="grid gap-1 text-sm">
          <span className="text-slate">Instructions shown on the invoice</span>
          <input
            className={FIELD}
            value={draft.instructions}
            onChange={(event) => setDraft({ ...draft, instructions: event.target.value })}
          />
        </label>
        <button type="submit" className="justify-self-start rounded bg-teal px-4 py-2 text-ink">
          Add account
        </button>
      </form>
    </div>
  );
}
```

`frontend/src/app/admin/payment-methods/page.tsx`:
```tsx
"use client";

import { useCallback, useEffect, useState } from "react";

import PaymentMethodTable from "@/components/admin/PaymentMethodTable";
import { apiFetch } from "@/lib/api";
import type { PaymentMethod } from "@/lib/types";

export default function AdminPaymentMethodsPage() {
  const [methods, setMethods] = useState<PaymentMethod[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setMethods(await apiFetch<PaymentMethod[]>("/api/admin/payment-methods"));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not load the payment accounts.");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <main className="mx-auto grid max-w-5xl gap-6 px-4 py-8">
      <h1 className="font-display text-2xl">Payment accounts</h1>
      <p className="text-slate">
        These appear on every invoice and on the client billing page, lowest sort order first. Hiding an
        account keeps its history intact.
      </p>
      {error ? <p role="alert" className="text-coral">{error}</p> : null}
      <PaymentMethodTable methods={methods} onChanged={load} />
    </main>
  );
}
```

- [ ] **Step 3: Add both pages to the admin navigation**

Open the admin shell Stage 6 created (`frontend/src/app/admin/layout.tsx`, or whichever component holds the admin nav links) and add two links next to the existing ones:
```tsx
        <Link href="/admin/payments">Payments</Link>
        <Link href="/admin/payment-methods">Payment accounts</Link>
```

- [ ] **Step 4: Typecheck, lint, run every frontend test and commit**

Run: `cd frontend && npx tsc --noEmit && npm run lint && npx vitest run`
Expected: no `tsc` output, `No ESLint warnings or errors`, all test files pass.
```bash
git add frontend/src/components/admin frontend/src/app/admin
git commit -m "feat(admin): payment review queue and payment-account pages" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 11: Prove there is no migration, document the flow, and green the whole build

**Files:**
- Modify: `README.md`
- Modify: `.github/workflows/ci.yml`

**Interfaces:** none new.

- [ ] **Step 1: Prove Stage 7 needs no schema change**

Stage 7 writes only columns that Stage 0's initial revision already created (`backend/app/models/billing.py`: `invoices.amount_paid`/`status`, all of `payment_methods`, all of `payments` including `proof_file_path` and `uq_payments_method_ref`). Verify rather than assume:

Run: `cd backend && .venv/Scripts/alembic upgrade head && .venv/Scripts/alembic check`
Expected: `No new upgrade operations detected.`

If it instead prints `New upgrade operations detected`, a model was changed by mistake during this stage. Find the diff with `.venv/Scripts/alembic revision --autogenerate -m "stage 7 check" --sql | head -40`, revert the accidental model edit, delete the throwaway revision file, and re-run `alembic check`. Only if the change is genuinely wanted should you keep a revision — and then say so in the commit message.

- [ ] **Step 2: Run the entire backend suite with coverage**

Run: `cd backend && .venv/Scripts/python -m pytest -q`
Expected: every test passes — Stages 0–6 plus the six Stage 7 test modules (`test_payments_provider.py` 13, `test_payments_service.py` 17, `test_invoice_pdf.py` 4, `test_billing_routes.py` 13, `test_admin_payments_routes.py` 10, `test_billing_e2e.py` 2).

- [ ] **Step 3: Document the billing month in the README**

Append to `README.md`, under the existing sections:
````markdown
## Billing (manual payments)

Money is never moved by this app. Clients pay from their own wallet or bank app and report the
transaction ID; **only an admin marks a payment as received**.

1. `/admin/payment-methods` — add the JazzCash / Easypaisa / NayaPay / Raast / bank accounts once.
   `sort_order` decides the order clients see; hiding an account keeps its history.
2. `/admin/invoices` (Stage 6) — draft the month, confirm the recovered waste, issue the invoice.
3. `/dashboard/billing` — the client sees the invoice and its PDF, pays, then submits the method,
   transaction ID, amount, date and an optional screenshot (PNG/JPEG/PDF, max 5 MB).
4. `/admin/payments` — the pending queue. Open the proof, then Confirm, or Reject with a reason the
   client will read. A transaction ID can never be reused for the same method.
5. Confirmed payments add up: the invoice becomes **paid** only once they cover the total. Partial
   payments are normal and the balance stays visible on both sides.

Invoices past their due date and not yet paid are flagged **Overdue** in the admin queue and on the
client's billing page. Nothing is suspended automatically.

Switching to an automatic gateway later (`docs/PLAN.md` §9) means writing one new class that
implements `PaymentProvider` in `backend/app/payments/`, registering it in
`backend/app/payments/__init__.py`, and setting `PAYMENT_PROVIDER` — no route or UI rewrite.
````

- [ ] **Step 4: Make CI run the frontend tests**

In `.github/workflows/ci.yml`, in the frontend job, add a step after the lint/typecheck steps:
```yaml
      - run: npm test
        working-directory: frontend
```

- [ ] **Step 5: Full green build, then commit**

Run:
```bash
cd backend && .venv/Scripts/ruff check . && .venv/Scripts/ruff format --check . && .venv/Scripts/python -m pytest -q
cd ../frontend && npm run lint && npx tsc --noEmit && npx vitest run && npm run build
```
Expected: `All checks passed!`, every pytest test passing, `No ESLint warnings or errors`, no `tsc` output, every Vitest file passing, and a successful `next build`.

```bash
git add README.md .github/workflows/ci.yml
git commit -m "docs(billing): document the manual payment month and run frontend tests in CI" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

## Stage 7 exit checklist (`docs/PLAN.md` §6, Stage 7, "Done when")

- [ ] **A full month runs end-to-end: generate → issue → client submits TID → admin confirms → invoice paid.** Task 7, `test_a_full_month_runs_generate_issue_submit_confirm_paid`.
- [ ] **A reused TID is refused.** Task 2 (`test_the_same_transaction_ref_cannot_be_used_twice_for_one_method`), Task 5 (`test_a_reused_transaction_id_is_refused_with_409`), Task 7 (step 4 of the month).
- [ ] **A client can't see or pay another client's invoice.** Task 3, Task 5 (`test_client_b_can_neither_see_nor_pay_client_as_invoice`), Task 7 (`test_another_client_cannot_see_or_pay_this_invoice`) — all 404, never 403.
- [ ] **A partial payment leaves the invoice unpaid.** Task 3 (`test_a_partial_confirmation_records_the_money_but_leaves_the_invoice_unpaid`), Task 6, Task 7 (step 3).
- [ ] Owner check, by hand: run the app, add a real payment account at `/admin/payment-methods`, issue an invoice to a test client, download the PDF, and confirm the wallet number on it is the one you would actually be paid into.

## Decisions

Recorded here so no one re-opens them mid-execution.

1. **`build_invoice_pdf` lives in `app/services/payments.py`, not `app/services/pdf.py`.** `INTERFACES.md` lists it under the `services/payments.py` heading, and the contract wins over the tidier grouping with `build_report_pdf`. It uses Stage 5's ReportLab conventions (A4 `SimpleDocTemplate`, mm margins, `Table`/`TableStyle`, no matplotlib) but shares no private helpers with `pdf.py`, so neither file can break the other.
2. **`PaymentSubmission` stays in `app/schemas/billing.py`** (where `INTERFACES.md` puts it) while `PaymentInstruction` stays in `app/payments/base.py`. The resulting import cycle is broken with `from __future__ import annotations` + `TYPE_CHECKING` on both sides, and a subprocess test (`test_schemas_can_be_imported_before_the_payments_package`) fails loudly if anyone converts either import to a runtime one.
3. **Errors are raised as `fastapi.HTTPException` straight from the services.** Stage 7 needs 404/409/413/415, and inventing a Stage-7 exception hierarchy on top of whatever Stage 3 chose would be a second, competing convention. The trade-off — services import FastAPI — is acceptable outside `app/pipeline/`, which is the only package `docs/PLAN.md` §2 requires to stay web-free.
4. **Duplicate transaction IDs are detected by the database, not by a pre-check `SELECT`.** `uq_payments_method_ref` already exists; catching `IntegrityError` and rolling back is race-free, whereas a check-then-insert is not.
5. **`confirm_payment` sets a not-yet-covered invoice back to `issued`, even if other payments are still pending** — this is `INTERFACES.md`'s wording ("paid when amount_paid >= total, else issued") taken literally. `reject_payment` keeps `payment_submitted` while other pending payments remain, which is also its documented wording. The asymmetry is deliberate and is pinned by tests in Task 3.
6. **Proof files are validated by content-type *and* magic bytes** (PNG `\x89PNG\r\n\x1a\n`, JPEG `\xff\xd8\xff`, PDF `%PDF-`). A browser's declared content-type is attacker-controlled; the first bytes are what the file actually is. Size is checked first, so a 40 MB upload is refused before anything sniffs it.
7. **Proof files are never public.** The only way to read one is `GET /api/admin/payments/{id}/proof` behind `CurrentAdmin`, and `proof_file_path` is excluded from every serialised response — clients get a boolean `has_proof` instead.
8. **The admin payment queue returns joined rows (`PaymentQueueRow`)** rather than bare `Payment` objects, so the queue can show the business name, invoice number and overdue flag without N+1 queries. `INTERFACES.md` specifies no return type for `list_pending_payments`, so this adds to the contract without breaking it.
9. **Overdue is computed, never stored.** `due_date < today and status not in ("paid", "void")` — in Python for `InvoiceOut.is_overdue` / `AdminPaymentOut.invoice_is_overdue`, and in TypeScript for `isOverdue()`. A stored flag would need a nightly job and would be wrong between runs.
10. **The end-to-end test drives Stage 6 through its *service* functions and Stage 7 through *HTTP*.** Stage 6's request/response bodies are not in `INTERFACES.md`; its service signatures are. This keeps Task 7 from breaking on a Stage 6 detail it does not own.
11. **`/dashboard/billing` is a client component** that fetches with `apiFetch`, unlike Stage 4's server-rendered summary. The page is interactive (select an invoice, submit a payment, refresh the list afterwards), so the state has to live in the browser; the route is still behind Stage 4's server-side auth guard in `dashboard/layout.tsx`.
12. **No Framer Motion on any billing page.** `docs/PLAN.md` reserves animation for the dashboard hero; these are working views.
13. **No Alembic migration.** Every column and constraint already exists. Task 11 proves it with `alembic check` rather than trusting the reading.
14. **No test module of this stage's own: two builders go into `tests/api/helpers.py`.** `INTERFACES.md` §"Test-fixture contract" makes that file the single home for row builders and `tests/api/conftest.py` the single home for fixtures, so this stage appends `make_invoice`, `make_method` and the three proof-byte constants and otherwise reuses `db`, `api`, `client_a`, `client_b`, `client_a_row`, `admin_client`, `admin_row`, `login_as`, `make_client` and `make_admin`. The HTTP tests therefore log nobody in by hand (`client_a` and `admin_client` arrive logged in), and no test sets `STORAGE_ROOT` (autouse `api_env` already points it at that test's `tmp_path / "storage"`).

## Self-review notes

- **Spec coverage — `docs/PLAN.md` §6, Stage 7.** Month steps 1–6: admin sets up accounts ✔ (Tasks 3, 6, 10); admin generates and issues ✔ (Stage 6 services, driven in Task 7); client sees the invoice and its PDF with amount, due date and accounts ✔ (Tasks 4, 5, 9); client submits method/TID/amount/date/optional screenshot and the invoice moves to `payment_submitted` ✔ (Tasks 2, 5, 9); admin confirms or rejects with a reason the client can read ✔ (Tasks 3, 6, 9, 10); invoice becomes paid once confirmed payments cover the total, partials tracked ✔ (Tasks 3, 6, 7). Rules: admin-only receipt ✔; TID unique per method ✔; private storage, images/PDF, size cap ✔; `Decimal` ✔; confirm/reject audited ✔ (void stays Stage 6's `void_invoice`, which `INTERFACES.md` already specifies as audited); overdue flagged, nothing suspended ✔; `PaymentProvider` seam ✔ (Task 1's protocol test builds a `FakeGateway` to prove a second provider needs no core change). §5 routes: all nine billing/admin-payment routes ✔. §4 tables: `invoices`, `payment_methods`, `payments`, `audit_log` all written, none altered ✔. §9: gateway add-on path stated in the README and Decision 13.
- **Placeholder scan.** No TBD/TODO, no "add validation", no "similar to Task N" — every test and every implementation is written out. The only conditional instructions are three explicit *verify-then-act* steps (pypdf/reportlab presence, Vitest presence, and the `apiFetch` header check), each with the exact command to run and the exact code to write if the check fails.
- **Type consistency.** `make_invoice(db, client, *, status, total, ...)` and `make_method(db, type, identifier, *, ...)` are spelled in Task 1's "Produces" block, written in Task 1 Step 7 and called with exactly those keywords in Tasks 2-7; `db`, `api`, `client_a`, `client_b`, `client_a_row`, `admin_client` and `admin_row` are used with the meanings `INTERFACES.md` gives them and are defined nowhere in this plan. `PaymentInstruction` fields match between Task 1 (definition), Task 2 (`instructions_for`), Task 4 (PDF), Task 5 (route) and Task 8 (TS mirror). `PaymentQueueRow(payment, invoice, client)` is built in Task 3 and destructured in Task 6. `admin_payment_out(payment, invoice, client, today=None)` is defined in Task 1 and called in Task 6 with three arguments. `validate_proof(content_type, data, max_mb) -> str` returns the extension Task 2's `submit(..., proof_ext)` expects, which becomes the `proofs/{client_id}/{payment_id}.{ext}` key that Task 6's proof route rebuilds. `has_proof` (not `proof_file_path`) is the field name used in every frontend component. `isOverdue(invoice, today)` has the same rule as the Python `_overdue(status, due_date, today)`.
- **Known gap, deliberate:** the client-facing billing page shows an `Overdue` badge computed in TypeScript while the API also returns `is_overdue`; both use the same rule, and the TS version exists because `docs/PLAN.md` puts the flag in the admin list, where rows come from the payments queue rather than an invoice endpoint.
