# Stage 3 — Upload & Analysis API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A logged-in client can upload an ad-export CSV, get row-level validation feedback, start an analysis that runs in the background, poll it to `done`, and read back a report whose numbers are exactly what the Stage 1 pipeline produces from the same file — with every endpoint scoped to the caller's own tenant.

**Architecture:** Three thin routers (`uploads`, `analysis`, `reports`) over three services (`storage`, `upload`, `analysis` — the report read model lives inside `analysis.py`). Services never import FastAPI; they raise `AppError` subclasses that `create_app()` maps to status codes. Bytes go through a `StorageBackend` Protocol (local disk now, S3-compatible in Stage 8), so `AdDataUpload.file_path` holds a portable storage **key**, not a filesystem path. The analysis itself is a FastAPI `BackgroundTasks` job that opens its own DB session, because the request's session is already closed by the time it runs.

**Tech Stack:** Python 3.11, FastAPI 0.141, SQLAlchemy 2.0 (`Mapped` style), Pydantic v2, pandas (via Stage 1), pytest 9, ruff (line-length 100). No new runtime dependencies: `python-multipart` is already in `backend/requirements.txt`.

**Spec:** `docs/PLAN.md` (§6 "Stage 3" is the deliverable; §5 the API surface; §4 the data model and tenant-isolation rules; §1 #3 partial dimensions and the template CSV; §1 #6 money as `Decimal`; §1 #9 the storage interface) and `docs/superpowers/plans/INTERFACES.md` (the Stage 3 block — every name and signature below is copied from it verbatim).

**Additions to `INTERFACES.md`** (permitted by that document's header; nothing is renamed):
- `app/core/db.py` gains `session_scope()` — the context-manager form of `get_session()`, used by the background task.
- `app/core/errors.py` (new): `AppError`, `NotFoundError`, `DuplicateUploadError`, `FileTooLargeError`, `InvalidUploadError`.
- `app/services/analysis.py` gains `to_money(value: float) -> Decimal` (the §1 #6 float→`Decimal` boundary) and `to_money_or_none`.
- `app/schemas/uploads.py` gains `UploadRejected` (the 422 body model).
- `LocalStorage.path_for(key) -> Path` (test/debug helper) and `app.services.upload.storage_key()`.
- Test fixtures follow `INTERFACES.md` §"Test-fixture contract", which Stage 2 already built: `bound_engine` (`backend/tests/conftest.py`), `api_env` / `db` / `api` / `rate_limited_client` (`backend/tests/api/conftest.py`) and `TEST_PASSWORD` / `login_as` / `user_for` / `make_client` / `make_admin` (`backend/tests/api/helpers.py`). **Stage 3 redefines none of them.** It only: extends `api_env` with a tmp storage root; adds `client_a`, `client_b`, `client_a_row`, `client_b_row`, `admin_row` and `admin_client` to `backend/tests/api/conftest.py` (`admin_row` is this stage's one addition beyond the contract's list, mirroring `client_a_row`, so a test can have the admin `User` and a logged-in admin client at once); and adds `make_upload` and `make_run` to `backend/tests/api/helpers.py`. `make_run` carries the keyword arguments later stages need (`created_at`, `headline_waste`, `segments`) so no stage has to re-edit it.

---

## Global Constraints

- **Stage 1 and Stage 2 are complete and merged.** This plan consumes `app.pipeline.*` and `app.core.deps` exactly as `INTERFACES.md` lists them, and changes neither.
- **Client-facing endpoints never take a `client_id` from the request.** It comes from `CurrentClient` (the JWT). Every service function takes `client_id` (or the `Client`) and filters by it in SQL (`docs/PLAN.md` §4 "Tenant isolation").
- **Another tenant's record returns 404, never 403**, so IDs can't be probed (`docs/PLAN.md` §4).
- **Clients only ever see runs with `review_status == "approved"`** (`docs/PLAN.md` §4). Admin approval arrives in Stage 6; in this stage's tests the row is set directly: `run.review_status = "approved"; db.commit()`.
- **Money crosses into the DB as `Decimal` quantized to 2 places, `ROUND_HALF_UP`** (`docs/PLAN.md` §1 #6). pandas floats are fine inside the pipeline; `to_money()` is the only boundary.
- **Headline waste is the largest single-dimension total, never a sum** (`docs/PLAN.md` §1 #1) — this stage stores exactly what `headline_waste()` returns.
- **Rows may have blank dimension values** (`docs/PLAN.md` §1 #3); the pipeline already handles it, so a `WasteReport` row is written for all three `DIMENSIONS` even when a dimension has no data.
- **Every run stores a config snapshot, and the analysis reads the snapshot, not the live client config** (`docs/PLAN.md` §3), so any report can be reproduced exactly.
- **Files go behind the storage interface** (`docs/PLAN.md` §1 #9). Nothing outside `app/services/storage.py` may touch `pathlib`/`open()` for uploaded data.
- Style: SQLAlchemy 2.0 `Mapped[...] = mapped_column(...)`; ruff `line-length = 100`, `select = ["E", "F", "I", "B", "UP"]`.
- Commands are Windows Git Bash from the repo root, using `backend/.venv/Scripts/...`.
- Every commit ends with a second `-m` carrying `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.
- Work on branch `stage-3-uploads-and-analysis`, branched from the Stage 2 branch.
- **No Alembic migration is needed** (verified in Task 8): every column this stage writes already exists in `55eb15843c97_initial_schema`.

---

## File Structure

```
backend/
├── app/
│   ├── core/
│   │   ├── db.py                  # MODIFY: + session_scope()
│   │   ├── errors.py              # NEW: AppError hierarchy (status_code per class)
│   │   └── settings.py            # MODIFY: + storage_backend, storage_root, max_upload_mb
│   ├── main.py                    # MODIFY: mount 3 routers + one AppError handler
│   ├── routers/
│   │   ├── uploads.py             # NEW: /api/uploads  (POST, GET, GET /{id}, GET /template.csv)
│   │   ├── analysis.py            # NEW: POST /api/analyze/{upload_id}, GET /api/runs/{id}
│   │   └── reports.py             # NEW: GET /api/reports/latest, GET /api/reports/{run_id}
│   ├── schemas/
│   │   ├── uploads.py             # NEW: UploadOut, UploadRejected
│   │   └── reports.py             # NEW: SegmentOut, DimensionOut, RecommendationOut,
│   │                              #      ReportOut, RunOut
│   └── services/
│       ├── storage.py             # NEW: StorageBackend Protocol, LocalStorage, get_storage()
│       ├── upload.py              # NEW: create_upload, list_uploads, get_upload, template_csv
│       └── analysis.py            # NEW: to_money, create_run, execute_run, get_run,
│                                  #      get_report, latest_report
└── tests/
    ├── conftest.py                # UNCHANGED: bound_engine / session / client came with Stage 2
    ├── services/
    │   ├── __init__.py
    │   ├── conftest.py            # NEW: tmp_path storage root + Client rows, no HTTP
    │   ├── test_storage.py
    │   ├── test_upload_service.py
    │   ├── test_analysis_service.py
    │   └── test_reports_service.py
    └── api/
        ├── __init__.py
        ├── conftest.py            # MODIFY (Stage 2 created it): api_env gains the storage
        │                          #   root; + client_a/client_b/*_row/admin_client
        ├── helpers.py             # MODIFY (Stage 2 created it): + make_upload, make_run
        ├── test_uploads.py
        └── test_analysis.py
```

Responsibility boundaries: `storage.py` knows bytes and keys and nothing about models; `upload.py` knows bytes → `AdDataUpload` and nothing about runs; `analysis.py` owns the whole run lifecycle and the report read model; routers own HTTP only (status codes, multipart, dependency wiring) and contain no business rules.

---

### Task 1: Storage interface and settings

**Files:**
- Create: `backend/app/services/__init__.py` (empty), `backend/app/services/storage.py`
- Modify: `backend/app/core/settings.py`
- Create: `backend/tests/services/__init__.py` (empty), `backend/tests/services/test_storage.py`

**Interfaces:**
- Consumes: `get_settings()` from `app.core.settings`.
- Produces:
  ```python
  class StorageBackend(Protocol):
      def save(self, key: str, data: bytes) -> str: ...   # returns the key, stored in file_path
      def read(self, key: str) -> bytes: ...
      def delete(self, key: str) -> None: ...
  class LocalStorage:                                     # LocalStorage(root: Path | str)
      root: Path
      def path_for(self, key: str) -> Path: ...
  def get_storage() -> StorageBackend                     # not cached: tests swap storage_root
  # Settings gains: storage_backend: str = "local", storage_root: str = "./storage",
  #                 max_upload_mb: int = 20
  ```

- [ ] **Step 1: Branch**

```bash
git checkout -b stage-3-uploads-and-analysis
```

- [ ] **Step 2: Write the failing test**

`backend/tests/services/__init__.py`: empty file.

`backend/tests/services/test_storage.py`:
```python
from pathlib import Path

import pytest

from app.core.settings import get_settings
from app.services.storage import LocalStorage, get_storage


def test_save_returns_the_key_and_writes_the_bytes(tmp_path: Path):
    storage = LocalStorage(tmp_path)

    key = storage.save("uploads/7/abc.csv", b"date,spend\n2026-08-01,10\n")

    assert key == "uploads/7/abc.csv"
    assert (tmp_path / "uploads" / "7" / "abc.csv").read_bytes().startswith(b"date,spend")


def test_read_round_trips_and_delete_removes(tmp_path: Path):
    storage = LocalStorage(tmp_path)
    storage.save("uploads/7/abc.csv", b"hello")

    assert storage.read("uploads/7/abc.csv") == b"hello"

    storage.delete("uploads/7/abc.csv")
    with pytest.raises(FileNotFoundError):
        storage.read("uploads/7/abc.csv")


def test_delete_is_idempotent(tmp_path: Path):
    LocalStorage(tmp_path).delete("uploads/7/never-existed.csv")  # must not raise


def test_save_overwrites_the_same_key(tmp_path: Path):
    storage = LocalStorage(tmp_path)
    storage.save("uploads/7/abc.csv", b"first")
    storage.save("uploads/7/abc.csv", b"second")

    assert storage.read("uploads/7/abc.csv") == b"second"


@pytest.mark.parametrize("key", ["", "/etc/passwd", "uploads/../../secrets.csv", "../x.csv"])
def test_keys_that_escape_the_root_are_rejected(tmp_path: Path, key: str):
    with pytest.raises(ValueError, match="invalid storage key"):
        LocalStorage(tmp_path).save(key, b"x")


def test_get_storage_builds_local_storage_from_settings(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path / "files"))
    get_settings.cache_clear()

    storage = get_storage()

    assert isinstance(storage, LocalStorage)
    assert storage.root == tmp_path / "files"
    get_settings.cache_clear()


def test_get_storage_rejects_an_unknown_backend(monkeypatch):
    monkeypatch.setenv("STORAGE_BACKEND", "dropbox")
    get_settings.cache_clear()

    with pytest.raises(ValueError, match="unknown storage_backend"):
        get_storage()

    get_settings.cache_clear()


def test_settings_defaults():
    get_settings.cache_clear()
    settings = get_settings()

    assert settings.storage_backend == "local"
    assert settings.storage_root == "./storage"
    assert settings.max_upload_mb == 20
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `cd backend && .venv/Scripts/python -m pytest tests/services/test_storage.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.storage'`

- [ ] **Step 4: Add the settings fields**

In `backend/app/core/settings.py`, add three fields after `secret_key`:
```python
    secret_key: str = "dev-only-insecure-secret"

    # --- file storage (docs/PLAN.md section 1 #9) ---
    storage_backend: str = "local"  # "supabase" arrives in Stage 8
    storage_root: str = "./storage"
    max_upload_mb: int = 20
```
Stage 2 already added `access_token_minutes`, `refresh_token_days` and `cookie_secure`; leave those alone.

- [ ] **Step 5: Write the implementation**

`backend/app/services/__init__.py`: empty file.

`backend/app/services/storage.py`:
```python
"""Uploaded files live behind this interface: local disk now, S3-compatible in Stage 8.

docs/PLAN.md section 1 #9 — Railway and Render disks are wiped on redeploy, so nothing
outside this module may assume a filesystem. `save()` returns the *key*, and that key is
what goes into DB `file_path` columns, so the same row works against any backend.
"""

from pathlib import Path
from typing import Protocol, runtime_checkable

from app.core.settings import get_settings


@runtime_checkable
class StorageBackend(Protocol):
    def save(self, key: str, data: bytes) -> str: ...

    def read(self, key: str) -> bytes: ...

    def delete(self, key: str) -> None: ...


def _check_key(key: str) -> str:
    parts = key.split("/")
    if not key or key.startswith("/") or "" in parts or ".." in parts:
        raise ValueError(f"invalid storage key: {key!r}")
    return key


class LocalStorage:
    """Dev and test backend. Keys are relative POSIX-style paths under `root`."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)

    def path_for(self, key: str) -> Path:
        return self.root / _check_key(key)

    def save(self, key: str, data: bytes) -> str:
        path = self.path_for(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return key

    def read(self, key: str) -> bytes:
        path = self.path_for(key)
        if not path.is_file():
            raise FileNotFoundError(key)
        return path.read_bytes()

    def delete(self, key: str) -> None:
        self.path_for(key).unlink(missing_ok=True)


def get_storage() -> StorageBackend:
    """Deliberately not cached: tests point `storage_root` at a fresh tmp_path per test."""
    settings = get_settings()
    if settings.storage_backend == "local":
        return LocalStorage(settings.storage_root)
    raise ValueError(f"unknown storage_backend: {settings.storage_backend!r}")
```

- [ ] **Step 6: Run the test to verify it passes**

Run: `cd backend && .venv/Scripts/python -m pytest tests/services/test_storage.py -v`
Expected: `11 passed` (the 4 parametrized key cases count separately).

- [ ] **Step 7: Lint and commit**

Run: `cd backend && .venv/Scripts/ruff check . && .venv/Scripts/ruff format .`
Expected: `All checks passed!`
```bash
git add backend/app/services backend/app/core/settings.py backend/tests/services
git commit -m "feat(storage): StorageBackend protocol with LocalStorage and settings" \
           -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 2: Upload service — hashing, validation, template

**Files:**
- Create: `backend/app/core/errors.py`
- Create: `backend/app/services/upload.py`
- Create: `backend/app/schemas/uploads.py`
- Verify only: `backend/tests/conftest.py` (Stage 2 already added `bound_engine`)
- Create: `backend/tests/services/conftest.py`, `backend/tests/services/test_upload_service.py`

**Interfaces:**
- Consumes: `get_storage()` (Task 1); Stage 1's `load_csv(source, config) -> LoadResult(df, errors, warnings, row_count, date_range, ok)`, `RowIssue(row, column, message)`, `PipelineConfig.from_overrides(dict)` and `REQUIRED_COLUMNS`; the `AdDataUpload` and `Client` models.
- Produces:
  ```python
  # app/core/errors.py
  class AppError(Exception): status_code: int; detail: object
  class NotFoundError(AppError):        status_code = 404
  class DuplicateUploadError(AppError): status_code = 409
  class FileTooLargeError(AppError):    status_code = 413
  class InvalidUploadError(AppError):   status_code = 422

  # app/services/upload.py
  storage_key(client_id: int, digest: str) -> str                # "uploads/{client_id}/{sha}.csv"
  create_upload(session: Session, client: Client, filename: str, data: bytes) -> AdDataUpload
  list_uploads(session: Session, client_id: int) -> list[AdDataUpload]            # newest first
  get_upload(session: Session, client_id: int, upload_id: int) -> AdDataUpload    # NotFoundError
  template_csv() -> bytes

  # app/schemas/uploads.py
  UploadOut(id, uploaded_at, original_filename, row_count, date_range_start,
            date_range_end, status, validation_report)
  UploadRejected(upload_id: int, status: str, errors: list[dict], warnings: list[dict])
  ```

- [ ] **Step 1: Confirm the bound engine is already in place**

Stage 2 created the single database-wiring mechanism this stage depends on: `bound_engine` in
`backend/tests/conftest.py` (`INTERFACES.md` §"Test-fixture contract"). It is a `StaticPool`
in-memory engine with `Base.metadata.create_all` applied, monkeypatched onto `app.core.db`'s
`_engine` and `_session_factory`, and the Stage 2 `session` fixture already rides on it. That
module-level patch — rather than a `get_session` dependency override — is exactly what makes
Task 5's background task, which opens its own session through `session_scope()`, land in the
same database. **Do not add a second engine, and do not modify `tests/conftest.py` in this
stage.**

Run: `cd backend && grep -n 'def bound_engine\|_session_factory' tests/conftest.py`
Expected: two lines — `def bound_engine(monkeypatch) -> Engine:` and the `db_module, "_session_factory", sessionmaker(...)` line. If grep prints nothing, Stage 2 Task 3 Step 1 was not completed — finish it before continuing; nothing in this stage works without it.

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_models.py -v`
Expected: still all `passed` — the Stage 0 model tests use `session` and must be unaffected.

- [ ] **Step 2: Write the failing tests**

`backend/tests/services/conftest.py`:
```python
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app.core.settings import get_settings
from app.models import Client, User


@pytest.fixture(autouse=True)
def storage_root(tmp_path: Path, monkeypatch):
    """Every service test writes its files into its own tmp_path."""
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path / "storage"))
    get_settings.cache_clear()
    yield tmp_path / "storage"
    get_settings.cache_clear()


def _make_client(session: Session, email: str, name: str) -> Client:
    user = User(email=email, password_hash="x", role="client", is_active=True)
    session.add(user)
    session.flush()
    client = Client(
        user_id=user.id,
        business_name=name,
        pricing_model="hybrid",
        base_fee=Decimal("15000"),
        performance_fee_pct=Decimal("20"),
        config_overrides={},
    )
    session.add(client)
    session.commit()
    session.refresh(client)
    return client


@pytest.fixture
def client_row(session: Session) -> Client:
    return _make_client(session, "a@example.com", "Alpha Traders")


@pytest.fixture
def other_client_row(session: Session) -> Client:
    return _make_client(session, "b@example.com", "Beta Traders")
```

`backend/tests/services/test_upload_service.py`:
```python
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app.core.errors import DuplicateUploadError, NotFoundError
from app.models import Client
from app.pipeline.data_generator import write_sample_csv
from app.pipeline.loader import load_csv
from app.services.storage import get_storage
from app.services.upload import create_upload, get_upload, list_uploads, template_csv

HEADER = (
    b"date,campaign_id,placement,age_group,gender,device,time_slot,"
    b"spend,impressions,clicks,conversions,revenue\n"
)
GOOD_CSV = (
    HEADER
    + b"2026-08-01,C1,facebook_feed,25-34,male,mobile,morning,1200.50,10000,250,5,12500\n"
    + b"2026-08-03,C1,audience_network,25-34,female,mobile,evening,800,9000,180,0,0\n"
)
BAD_CSV = (
    HEADER
    + b"2026-08-01,C1,facebook_feed,25-34,male,mobile,morning,abc,1000,20,1,500\n"
    + b"not-a-date,C1,facebook_feed,25-34,male,mobile,morning,100,1000,20,1,500\n"
)


def test_valid_upload_is_stored_validated_and_summarised(session: Session, client_row: Client):
    upload = create_upload(session, client_row, "august.csv", GOOD_CSV)

    assert upload.id is not None
    assert upload.client_id == client_row.id
    assert upload.original_filename == "august.csv"
    assert upload.status == "validated"
    assert upload.row_count == 2
    assert str(upload.date_range_start) == "2026-08-01"
    assert str(upload.date_range_end) == "2026-08-03"
    assert upload.validation_report == {"errors": [], "warnings": []}
    assert upload.file_path == f"uploads/{client_row.id}/{upload.file_sha256}.csv"
    assert get_storage().read(upload.file_path) == GOOD_CSV


def test_invalid_upload_is_kept_with_row_level_errors(session: Session, client_row: Client):
    upload = create_upload(session, client_row, "broken.csv", BAD_CSV)

    assert upload.status == "failed"
    errors = upload.validation_report["errors"]
    assert any(e["row"] == 1 and e["column"] == "spend" for e in errors), errors
    assert any(e["row"] == 2 and e["column"] == "date" for e in errors), errors
    # the bytes are still stored, so the client can be shown exactly what they sent
    assert get_storage().read(upload.file_path) == BAD_CSV


def test_unreadable_bytes_fail_validation_instead_of_raising(session: Session, client_row: Client):
    upload = create_upload(session, client_row, "photo.jpg", b"\xff\xd8\xff\xe0\x00\x10JFIF")

    assert upload.status == "failed"
    assert upload.validation_report["errors"][0]["row"] is None
    assert "could not read the file as CSV" in upload.validation_report["errors"][0]["message"]


def test_same_bytes_twice_for_one_client_is_a_duplicate(session: Session, client_row: Client):
    first = create_upload(session, client_row, "august.csv", GOOD_CSV)

    with pytest.raises(DuplicateUploadError) as excinfo:
        create_upload(session, client_row, "august-copy.csv", GOOD_CSV)

    assert excinfo.value.detail["upload_id"] == first.id
    assert excinfo.value.status_code == 409


def test_the_same_bytes_from_another_client_are_not_a_duplicate(
    session: Session, client_row: Client, other_client_row: Client
):
    create_upload(session, client_row, "august.csv", GOOD_CSV)

    other = create_upload(session, other_client_row, "august.csv", GOOD_CSV)

    assert other.client_id == other_client_row.id
    assert other.file_path == f"uploads/{other_client_row.id}/{other.file_sha256}.csv"


def test_list_uploads_is_newest_first_and_tenant_scoped(
    session: Session, client_row: Client, other_client_row: Client
):
    first = create_upload(session, client_row, "one.csv", GOOD_CSV)
    second = create_upload(
        session, client_row, "two.csv", GOOD_CSV.replace(b"1200.50", b"1300.50")
    )
    create_upload(session, other_client_row, "theirs.csv", GOOD_CSV)

    listed = list_uploads(session, client_row.id)

    assert [u.id for u in listed] == [second.id, first.id]


def test_get_upload_from_another_tenant_is_not_found(
    session: Session, client_row: Client, other_client_row: Client
):
    theirs = create_upload(session, other_client_row, "theirs.csv", GOOD_CSV)

    with pytest.raises(NotFoundError) as excinfo:
        get_upload(session, client_row.id, theirs.id)

    assert excinfo.value.status_code == 404


def test_get_upload_missing_id_is_not_found(session: Session, client_row: Client):
    with pytest.raises(NotFoundError):
        get_upload(session, client_row.id, 4242)


def test_template_csv_round_trips_through_the_loader(tmp_path: Path):
    path = tmp_path / "template.csv"
    path.write_bytes(template_csv())

    result = load_csv(path)

    assert result.ok, result.errors
    assert result.warnings == []
    assert result.row_count == 3


def test_a_generated_sample_file_uploads_cleanly(
    session: Session, client_row: Client, tmp_path: Path
):
    path = write_sample_csv(tmp_path / "sample.csv", days=3, seed=5)

    upload = create_upload(session, client_row, "sample.csv", path.read_bytes())

    assert upload.status == "validated"
    assert upload.row_count == 3 * 4 * 5 * 3 * 4
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `cd backend && .venv/Scripts/python -m pytest tests/services/test_upload_service.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.core.errors'`

- [ ] **Step 4: Write the error hierarchy**

`backend/app/core/errors.py`:
```python
"""Service-layer failures and the HTTP status each one becomes.

Services must not import FastAPI (they are reused by the background task and by scripts/),
so they raise these instead. `create_app()` installs one handler for the whole hierarchy
and renders `{"detail": exc.detail}`.
"""


class AppError(Exception):
    """Base class. `detail` is rendered as the JSON body's `detail` field."""

    status_code: int = 400

    def __init__(self, detail: object) -> None:
        super().__init__(detail if isinstance(detail, str) else repr(detail))
        self.detail = detail


class NotFoundError(AppError):
    """Missing, or owned by another tenant — docs/PLAN.md section 4 says 404, not 403."""

    status_code = 404


class DuplicateUploadError(AppError):
    status_code = 409


class FileTooLargeError(AppError):
    status_code = 413


class InvalidUploadError(AppError):
    status_code = 422
```

- [ ] **Step 5: Write the upload service**

`backend/app/services/upload.py`:
```python
"""Turn uploaded bytes into an AdDataUpload row: hash, store, validate, summarise."""

import hashlib
import io
from dataclasses import asdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import DuplicateUploadError, NotFoundError
from app.models import AdDataUpload, Client
from app.pipeline.config import REQUIRED_COLUMNS, PipelineConfig
from app.pipeline.loader import RowIssue, load_csv
from app.services.storage import get_storage

# Three rows a real Meta or Google export could plausibly contain. Served by
# GET /api/uploads/template.csv (docs/PLAN.md section 1 #3).
_TEMPLATE_ROWS = (
    "2026-08-01,CAMP-1,facebook_feed,25-34,male,mobile,morning,12500.00,420000,8400,168,420000",
    "2026-08-01,CAMP-1,instagram_stories,18-24,female,mobile,evening,7300.50,210000,3900,52,130000",
    "2026-08-02,CAMP-1,audience_network,35-44,male,tablet,night,9800.00,380000,5100,12,30000",
)


def template_csv() -> bytes:
    lines = [",".join(REQUIRED_COLUMNS), *_TEMPLATE_ROWS]
    return ("\n".join(lines) + "\n").encode("utf-8")


def storage_key(client_id: int, digest: str) -> str:
    return f"uploads/{client_id}/{digest}.csv"


def create_upload(session: Session, client: Client, filename: str, data: bytes) -> AdDataUpload:
    """Store the bytes and record the row.

    Never raises on a bad CSV: the row is kept with status "failed" and a row-level
    validation report, so the UI can point at the exact bad lines.
    """
    digest = hashlib.sha256(data).hexdigest()
    existing = session.scalars(
        select(AdDataUpload).where(
            AdDataUpload.client_id == client.id, AdDataUpload.file_sha256 == digest
        )
    ).first()
    if existing is not None:
        raise DuplicateUploadError(
            {"message": "this file has already been uploaded", "upload_id": existing.id}
        )

    config = PipelineConfig.from_overrides(client.config_overrides or {})
    try:
        result = load_csv(io.BytesIO(data), config)
        errors = list(result.errors)
        warnings = list(result.warnings)
        row_count = result.row_count
        date_range = result.date_range
    except Exception as exc:  # noqa: BLE001 - a binary or empty file must not 500 the request
        errors = [RowIssue(None, None, f"could not read the file as CSV: {exc}")]
        warnings = []
        row_count = 0
        date_range = None

    key = get_storage().save(storage_key(client.id, digest), data)
    start, end = date_range if date_range else (None, None)

    upload = AdDataUpload(
        client_id=client.id,
        original_filename=filename,
        file_path=key,
        file_sha256=digest,
        row_count=row_count,
        date_range_start=start,
        date_range_end=end,
        status="validated" if not errors else "failed",
        validation_report={
            "errors": [asdict(issue) for issue in errors],
            "warnings": [asdict(issue) for issue in warnings],
        },
    )
    session.add(upload)
    session.commit()
    session.refresh(upload)
    return upload


def list_uploads(session: Session, client_id: int) -> list[AdDataUpload]:
    return list(
        session.scalars(
            select(AdDataUpload)
            .where(AdDataUpload.client_id == client_id)
            .order_by(AdDataUpload.uploaded_at.desc(), AdDataUpload.id.desc())
        )
    )


def get_upload(session: Session, client_id: int, upload_id: int) -> AdDataUpload:
    upload = session.scalars(
        select(AdDataUpload).where(
            AdDataUpload.id == upload_id, AdDataUpload.client_id == client_id
        )
    ).first()
    if upload is None:
        raise NotFoundError("upload not found")
    return upload
```

- [ ] **Step 6: Write the upload schemas**

`backend/app/schemas/uploads.py`:
```python
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class UploadOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    uploaded_at: datetime
    original_filename: str
    row_count: int | None
    date_range_start: date | None
    date_range_end: date | None
    status: str
    validation_report: dict


class UploadRejected(BaseModel):
    """Body of the 422 returned when a CSV fails validation (docs/PLAN.md section 6)."""

    upload_id: int
    status: str
    errors: list[dict]
    warnings: list[dict]
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `cd backend && .venv/Scripts/python -m pytest tests/services/test_upload_service.py -v`
Expected: `10 passed`. If `test_invalid_upload_is_kept_with_row_level_errors` fails, print
`upload.validation_report["errors"]`: Stage 1's loader owns the message wording, but the
`row` (1-based, header excluded) and `column` are what this stage guarantees — fix the code,
not the assertion, if either is missing.

- [ ] **Step 8: Lint and commit**

Run: `cd backend && .venv/Scripts/ruff check . && .venv/Scripts/ruff format .`
```bash
git add backend/app/core/errors.py backend/app/services/upload.py backend/app/schemas/uploads.py \
        backend/tests/conftest.py backend/tests/services
git commit -m "feat(uploads): upload service with sha256 dedupe, validation report and template" \
           -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 3: `/api/uploads` router and the API test fixtures

**Files:**
- Create: `backend/app/routers/uploads.py`
- Modify: `backend/app/main.py`
- Modify: `backend/tests/api/conftest.py` (Stage 2 created this file)
- Modify: `backend/tests/api/helpers.py` (Stage 2 created this file)
- Create: `backend/tests/api/test_uploads.py`

**Interfaces:**
- Consumes: `create_upload`, `list_uploads`, `get_upload`, `template_csv`, `UploadOut`, and the `AppError` subclasses (Task 2); `CurrentClient` from `app.core.deps` and `get_session` from `app.core.db` (Stage 2); `get_settings().max_upload_mb` (Task 1).
- Produces:
  ```python
  # app/routers/uploads.py
  router: APIRouter                        # prefix "/api/uploads"
  # POST   /api/uploads               multipart field "file" -> 201 UploadOut | 409 | 413 | 422
  # GET    /api/uploads               -> 200 list[UploadOut]
  # GET    /api/uploads/template.csv  -> 200 text/csv   (declared BEFORE /{upload_id})
  # GET    /api/uploads/{upload_id}   -> 200 UploadOut | 404
  # app/main.py: create_app() mounts the router and installs one AppError handler
  ```
- **Stage 2 already created `backend/tests/api/conftest.py` and `backend/tests/api/helpers.py`**
  (`INTERFACES.md` §"Test-fixture contract"). Stage 3 makes exactly three changes to them, all
  shown below: `api_env` gains a tmp storage root; the two tenant `TestClient`s and their
  `Client` rows plus `admin_row` / `admin_client` are appended to the conftest; `make_upload` and `make_run`
  are appended to `helpers.py`. **Do not re-add `api_env`, `db`, `api`, `login_as`,
  `make_client` or `make_admin` — they already exist and are imported, not redefined.**

- [ ] **Step 1: Extend `api_env` with a storage root**

Every upload written by an API test must land under that test's own `tmp_path`, so `api_env`
— already autouse from Stage 2 — grows two `monkeypatch.setenv` calls. Change it in
`backend/tests/api/conftest.py` so that the fixture reads exactly like the right-hand side of
this diff (`+` lines are added; every other line is Stage 2's and stays as it is):

```diff
+from pathlib import Path
+
 import pytest
 from fastapi.testclient import TestClient
 from sqlalchemy import Engine
 from sqlalchemy.orm import Session


 @pytest.fixture(autouse=True)
-def api_env(bound_engine: Engine) -> Engine:
+def api_env(tmp_path: Path, monkeypatch, bound_engine: Engine) -> Engine:
     """Fresh settings plus the shared in-memory DB, for every test in tests/api/.

     Autouse, so no API test can accidentally run against an unbound engine.
+    From Stage 3 on it also points LocalStorage at this test's own tmp_path, so uploads
+    never touch the developer's ./storage directory.
     """
     from app.core.settings import get_settings

+    monkeypatch.setenv("STORAGE_BACKEND", "local")
+    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path / "storage"))
     get_settings.cache_clear()
     yield bound_engine
     get_settings.cache_clear()
```

- [ ] **Step 2: Add the tenant fixtures**

Append to `backend/tests/api/conftest.py` (keep everything Stage 2 put there, including
`_new_client()`, which these fixtures reuse):
```python
from sqlalchemy import select

from app.models import Client, User
from tests.api.helpers import TEST_PASSWORD, login_as, make_admin


def _signup(email: str, business_name: str) -> TestClient:
    """A brand-new TestClient that has just signed up - so its cookie jar is logged in."""
    http = _new_client()
    response = http.post(
        "/api/auth/signup",
        json={"email": email, "password": TEST_PASSWORD, "business_name": business_name},
    )
    assert response.status_code == 201, response.text
    return http


@pytest.fixture
def client_a() -> TestClient:
    """A logged-in client (cookies set by signup). Its own cookie jar."""
    return _signup("a@example.com", "Alpha Traders")


@pytest.fixture
def client_b() -> TestClient:
    """A second, unrelated tenant - used by every isolation test."""
    return _signup("b@example.com", "Beta Traders")


@pytest.fixture
def admin_row(db: Session) -> User:
    """The admin User row. Requesting it alongside `admin_client` gives you both."""
    return make_admin(db, "admin@example.com")


@pytest.fixture
def admin_client(admin_row: User) -> TestClient:
    """A logged-in admin. Stage 6 mounts /api/admin/*; here it proves runs stay invisible."""
    http = _new_client()
    login_as(http, admin_row)
    return http


def _client_row(db: Session, email: str) -> Client:
    user = db.scalars(select(User).where(User.email == email)).one()
    return db.scalars(select(Client).where(Client.user_id == user.id)).one()


@pytest.fixture
def client_a_row(db: Session, client_a: TestClient) -> Client:
    return _client_row(db, "a@example.com")


@pytest.fixture
def client_b_row(db: Session, client_b: TestClient) -> Client:
    return _client_row(db, "b@example.com")
```

`client_a` / `client_b` sign up through the real endpoint rather than through `make_client`,
because these tests are about the HTTP surface and signup is the only path that creates a
client in production. `TEST_PASSWORD` is the same constant `make_client` hashes, so `login_as`
works against either kind of tenant.

- [ ] **Step 3: Add `make_upload` and `make_run` to the shared helpers**

Append to `backend/tests/api/helpers.py` (Stage 2 created it with `TEST_PASSWORD`, `login_as`,
`user_for`, `make_client` and `make_admin`; keep all of those). These two builders are how
every later stage gets an upload or a finished run without driving the pipeline, and their
keyword arguments already cover Stage 6's needs, so no stage has to re-edit them:
```python
from datetime import UTC, date, datetime
from uuid import uuid4

from app.models import AdDataUpload, AnalysisRun, SegmentMetric, WasteReport

CONFIG_SNAPSHOT = {
    "benchmark_mode": "account_avg",
    "waste_multiplier": 1.5,
    "min_spend": 1000.0,
    "min_clicks": 100,
    "min_spend_zero_conv": 1000.0,
    "max_cut_pct": 0.6,
}


def make_upload(db: Session, client: Client, *, status: str = "validated") -> AdDataUpload:
    """A committed AdDataUpload row for `client`. No bytes are written to storage."""
    upload = AdDataUpload(
        client_id=client.id,
        original_filename="august.csv",
        file_path=f"uploads/{client.id}/{uuid4().hex}.csv",
        file_sha256=uuid4().hex,
        row_count=900,
        date_range_start=date(2026, 8, 1),
        date_range_end=date(2026, 8, 31),
        status=status,
        validation_report={"errors": [], "warnings": []},
    )
    db.add(upload)
    db.commit()
    db.refresh(upload)
    return upload


def make_run(
    db: Session,
    client: Client,
    upload: AdDataUpload | None = None,
    *,
    status: str = "done",
    review_status: str = "pending",
    created_at: datetime | None = None,
    headline_waste: Decimal | None = Decimal("52000.00"),
    segments: tuple[tuple[str, str, str, bool], ...] = (),
) -> AnalysisRun:
    """A committed AnalysisRun for `client`, optionally with its WasteReport rows.

    `segments` entries are (dimension, segment_value, wasted_spend, is_flagged); one
    WasteReport is created per distinct dimension and its total_wasted_spend is the sum of
    that dimension's segments. With the default empty tuple the run carries no reports,
    which is all a status-polling or review-queue test needs.
    """
    if upload is None:
        upload = make_upload(db, client)
    run = AnalysisRun(
        client_id=client.id,
        upload_id=upload.id,
        config_snapshot=dict(CONFIG_SNAPSHOT),
        status=status,
        review_status=review_status,
        headline_waste=headline_waste,
        created_at=created_at or datetime(2026, 9, 1, 12, 0, tzinfo=UTC),
    )
    db.add(run)
    db.flush()

    reports: dict[str, WasteReport] = {}
    for dimension, segment_value, wasted, flagged in segments:
        if dimension not in reports:
            report = WasteReport(
                run_id=run.id,
                client_id=client.id,
                upload_id=upload.id,
                dimension=dimension,
                total_spend=Decimal("100000.00"),
                total_wasted_spend=Decimal("0.00"),
                benchmark_cpa=Decimal("800.00"),
            )
            db.add(report)
            db.flush()
            reports[dimension] = report
        report = reports[dimension]
        report.total_wasted_spend = report.total_wasted_spend + Decimal(wasted)
        db.add(
            SegmentMetric(
                report_id=report.id,
                segment_value=segment_value,
                spend=Decimal("84000.00"),
                impressions=100000,
                clicks=2000,
                conversions=40,
                revenue=Decimal("60000.00"),
                cpa=Decimal("2100.00"),
                is_significant=True,
                is_flagged=flagged,
                wasted_spend=Decimal(wasted),
            )
        )
    db.commit()
    db.refresh(run)
    return run
```

`ruff format` merges these imports into the ones Stage 2 already wrote at the top of the file
(`Decimal`, `TestClient`, `Session`, `Client`, `User`); keep one import block, not two.

They live here, in the stage that owns the `AdDataUpload` / `AnalysisRun` write path, because
this is where their column shapes are settled; Stage 3's own API tests deliberately drive the
real endpoints instead (proving the pipeline, which is this stage's point), and Stages 5–7
import these two builders rather than writing their own.

Run: `cd backend && .venv/Scripts/python -m pytest tests/api -q --collect-only | tail -3`
Expected: collection succeeds (no `ImportError` from `tests/api/helpers.py`) and the Stage 2
API tests are listed unchanged.

If `backend/tests/api/__init__.py` does not exist, create it empty.

- [ ] **Step 4: Write the failing tests**

`backend/tests/api/test_uploads.py`:
```python
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.settings import get_settings
from app.pipeline.data_generator import write_sample_csv
from app.pipeline.loader import load_csv

HEADER = (
    "date,campaign_id,placement,age_group,gender,device,time_slot,"
    "spend,impressions,clicks,conversions,revenue\n"
)
GOOD_ROW = "2026-08-01,C1,facebook_feed,25-34,male,mobile,morning,1200.50,10000,250,5,12500\n"
BAD_CSV = HEADER + "2026-08-01,C1,facebook_feed,25-34,male,mobile,morning,abc,1000,20,1,500\n"


def _post(http: TestClient, name: str, body: bytes):
    return http.post("/api/uploads", files={"file": (name, body, "text/csv")})


def test_upload_happy_path_returns_201_and_a_validated_upload(client_a: TestClient, tmp_path: Path):
    path = write_sample_csv(tmp_path / "sample.csv", days=3, seed=5)

    response = _post(client_a, "sample.csv", path.read_bytes())

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "validated"
    assert body["original_filename"] == "sample.csv"
    assert body["row_count"] == 3 * 4 * 5 * 3 * 4
    assert body["date_range_start"] == "2026-08-01"
    assert body["validation_report"] == {"errors": [], "warnings": []}
    assert "client_id" not in body, "the response must not leak tenant ids"


def test_invalid_csv_returns_422_with_row_level_errors(client_a: TestClient):
    response = _post(client_a, "broken.csv", BAD_CSV.encode())

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["status"] == "failed"
    assert isinstance(detail["upload_id"], int)
    assert any(e["row"] == 1 and e["column"] == "spend" for e in detail["errors"]), detail


def test_duplicate_upload_returns_409_naming_the_first_upload(client_a: TestClient):
    first = _post(client_a, "aug.csv", (HEADER + GOOD_ROW).encode()).json()

    response = _post(client_a, "aug-again.csv", (HEADER + GOOD_ROW).encode())

    assert response.status_code == 409
    assert response.json()["detail"]["upload_id"] == first["id"]


def test_oversize_upload_returns_413(client_a: TestClient, monkeypatch):
    monkeypatch.setenv("MAX_UPLOAD_MB", "1")
    get_settings.cache_clear()
    body = (HEADER + GOOD_ROW * 20000).encode()  # ~1.5 MB
    assert len(body) > 1024 * 1024

    response = _post(client_a, "huge.csv", body)

    assert response.status_code == 413
    assert "larger than 1 MB" in response.json()["detail"]


def test_upload_requires_authentication():
    from app.main import create_app

    anonymous = TestClient(create_app())

    response = _post(anonymous, "aug.csv", (HEADER + GOOD_ROW).encode())

    assert response.status_code == 401


def test_list_and_detail_are_scoped_to_the_caller(client_a: TestClient, client_b: TestClient):
    mine = _post(client_a, "mine.csv", (HEADER + GOOD_ROW).encode()).json()
    _post(client_b, "theirs.csv", (HEADER + GOOD_ROW).encode())

    listed = client_a.get("/api/uploads").json()

    assert [u["id"] for u in listed] == [mine["id"]]
    assert client_a.get(f"/api/uploads/{mine['id']}").json()["id"] == mine["id"]


def test_client_a_cannot_read_client_bs_upload(client_a: TestClient, client_b: TestClient):
    theirs = _post(client_b, "theirs.csv", (HEADER + GOOD_ROW).encode()).json()

    response = client_a.get(f"/api/uploads/{theirs['id']}")

    assert response.status_code == 404, "another tenant's id must look missing, not forbidden"
    assert response.json()["detail"] == "upload not found"


def test_template_csv_downloads_and_round_trips(client_a: TestClient, tmp_path: Path):
    response = client_a.get("/api/uploads/template.csv")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment" in response.headers["content-disposition"]

    path = tmp_path / "template.csv"
    path.write_bytes(response.content)
    result = load_csv(path)

    assert result.ok, result.errors
    assert result.row_count == 3


def test_the_downloaded_template_can_be_uploaded_as_is(client_a: TestClient):
    template = client_a.get("/api/uploads/template.csv").content

    response = _post(client_a, "template.csv", template)

    assert response.status_code == 201
    assert response.json()["status"] == "validated"
```

- [ ] **Step 5: Run the tests to verify they fail**

Run: `cd backend && .venv/Scripts/python -m pytest tests/api/test_uploads.py -v`
Expected: FAIL — every test gets 404 because `/api/uploads` is not mounted yet
(`assert 404 == 201`).

- [ ] **Step 6: Write the router**

`backend/app/routers/uploads.py`:
```python
"""/api/uploads — docs/PLAN.md section 5. The client_id always comes from the JWT."""

from typing import Annotated

from fastapi import APIRouter, Depends, File, Response, UploadFile
from sqlalchemy.orm import Session

from app.core.db import get_session
from app.core.deps import CurrentClient
from app.core.errors import FileTooLargeError, InvalidUploadError
from app.core.settings import get_settings
from app.models import AdDataUpload
from app.schemas.uploads import UploadOut
from app.services.upload import create_upload, get_upload, list_uploads, template_csv

router = APIRouter(prefix="/api/uploads", tags=["uploads"])

SessionDep = Annotated[Session, Depends(get_session)]

_CHUNK = 1024 * 1024


async def _read_limited(file: UploadFile, max_bytes: int) -> bytes:
    """Read the upload a megabyte at a time and abort as soon as it goes over the limit."""
    chunks: list[bytes] = []
    total = 0
    while chunk := await file.read(_CHUNK):
        total += len(chunk)
        if total > max_bytes:
            raise FileTooLargeError(f"file is larger than {max_bytes // (1024 * 1024)} MB")
        chunks.append(chunk)
    return b"".join(chunks)


# Declared before "/{upload_id}" so the literal path wins the match.
@router.get("/template.csv")
def download_template() -> Response:
    return Response(
        content=template_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="ad_data_template.csv"'},
    )


@router.post("", status_code=201, response_model=UploadOut)
async def upload_file(
    client: CurrentClient,
    session: SessionDep,
    file: Annotated[UploadFile, File()],
) -> AdDataUpload:
    max_bytes = get_settings().max_upload_mb * 1024 * 1024
    data = await _read_limited(file, max_bytes)
    upload = create_upload(session, client, file.filename or "upload.csv", data)
    if upload.status == "failed":
        raise InvalidUploadError(
            {
                "upload_id": upload.id,
                "status": upload.status,
                "errors": upload.validation_report.get("errors", []),
                "warnings": upload.validation_report.get("warnings", []),
            }
        )
    return upload


@router.get("", response_model=list[UploadOut])
def read_uploads(client: CurrentClient, session: SessionDep) -> list[AdDataUpload]:
    return list_uploads(session, client.id)


@router.get("/{upload_id}", response_model=UploadOut)
def read_upload(upload_id: int, client: CurrentClient, session: SessionDep) -> AdDataUpload:
    return get_upload(session, client.id, upload_id)
```

- [ ] **Step 7: Mount it and map the errors**

`backend/app/main.py`:
```python
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.errors import AppError
from app.core.settings import get_settings
from app.routers import auth, uploads


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(title="Ad Spend Optimization API", version="0.1.0")

    @application.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "env": settings.env}

    @application.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    application.include_router(auth.router)
    application.include_router(uploads.router)
    return application


app = create_app()
```
Keep whatever Stage 2 added inside `create_app()` (the slowapi limiter wiring and its
`RateLimitExceeded` handler) exactly where it is. Only two lines belong to this task: the
`AppError` handler and `include_router(uploads.router)`.

- [ ] **Step 8: Run the tests to verify they pass**

Run: `cd backend && .venv/Scripts/python -m pytest tests/api/test_uploads.py -v`
Expected: `9 passed`. If `test_template_csv_downloads_and_round_trips` returns 422, the
`/template.csv` route was declared after `/{upload_id}` — move it above.

- [ ] **Step 9: Lint and commit**

Run: `cd backend && .venv/Scripts/ruff check . && .venv/Scripts/ruff format .`
```bash
git add backend/app/routers/uploads.py backend/app/main.py backend/tests/api
git commit -m "feat(api): /api/uploads with size limit, dedupe, row-level 422 and template" \
           -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 4: `session_scope()`, `to_money()` and `create_run()`

**Files:**
- Modify: `backend/app/core/db.py`
- Create: `backend/app/services/analysis.py`
- Create: `backend/tests/services/test_analysis_service.py`

**Interfaces:**
- Consumes: `get_upload` and the `InvalidUploadError`/`NotFoundError` classes (Task 2); `PipelineConfig.from_overrides(dict).to_dict()`; the `AnalysisRun` model.
- Produces:
  ```python
  # app/core/db.py
  session_scope() -> ContextManager[Session]   # same factory as get_session(); non-request code
  # app/services/analysis.py
  to_money(value: float) -> Decimal                      # 2 places, ROUND_HALF_UP
  to_money_or_none(value: float | None) -> Decimal | None
  create_run(session: Session, client: Client, upload_id: int) -> AnalysisRun   # status "queued"
  get_run(session: Session, client_id: int, run_id: int) -> AnalysisRun         # NotFoundError
  ```

- [ ] **Step 1: Write the failing tests**

`backend/tests/services/test_analysis_service.py`:
```python
import io
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.core.db import session_scope
from app.core.errors import InvalidUploadError, NotFoundError
from app.models import AdDataUpload, AnalysisRun, Client
from app.pipeline.config import PipelineConfig
from app.services.analysis import create_run, get_run, to_money
from app.services.upload import create_upload

HEADER = (
    b"date,campaign_id,placement,age_group,gender,device,time_slot,"
    b"spend,impressions,clicks,conversions,revenue\n"
)
GOOD = HEADER + b"2026-08-01,C1,facebook_feed,25-34,male,mobile,morning,1200.50,10000,250,5,12500\n"
BAD = HEADER + b"2026-08-01,C1,facebook_feed,25-34,male,mobile,morning,abc,1000,20,1,500\n"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (1200.5, Decimal("1200.50")),
        (0.0, Decimal("0.00")),
        (5176.470588235294, Decimal("5176.47")),
        (0.125, Decimal("0.13")),  # ROUND_HALF_UP, not banker's rounding
        (2.5, Decimal("2.50")),
    ],
)
def test_to_money_quantises_to_two_places_half_up(raw: float, expected: Decimal):
    value = to_money(raw)

    assert value == expected
    assert value.as_tuple().exponent == -2


def test_session_scope_uses_the_same_database_as_get_session(session: Session, client_row: Client):
    upload = create_upload(session, client_row, "aug.csv", GOOD)

    with session_scope() as other:
        assert other.get(AdDataUpload, upload.id) is not None


def test_create_run_queues_a_run_with_a_config_snapshot(session: Session, client_row: Client):
    upload = create_upload(session, client_row, "aug.csv", GOOD)

    run = create_run(session, client_row, upload.id)

    assert run.client_id == client_row.id
    assert run.upload_id == upload.id
    assert run.status == "queued"
    assert run.review_status == "pending"
    assert run.headline_waste is None
    assert run.config_snapshot == PipelineConfig().to_dict()
    assert PipelineConfig.from_overrides(run.config_snapshot) == PipelineConfig()


def test_create_run_snapshots_the_clients_overrides(session: Session, client_row: Client):
    client_row.config_overrides = {"waste_multiplier": 2.0, "min_spend": 1000}
    session.commit()
    upload = create_upload(session, client_row, "aug.csv", GOOD)

    run = create_run(session, client_row, upload.id)

    assert run.config_snapshot["waste_multiplier"] == 2.0
    assert run.config_snapshot["min_spend"] == 1000
    assert run.config_snapshot["min_clicks"] == PipelineConfig().min_clicks


def test_create_run_rejects_an_upload_that_failed_validation(session: Session, client_row: Client):
    upload = create_upload(session, client_row, "broken.csv", BAD)
    assert upload.status == "failed"

    with pytest.raises(InvalidUploadError) as excinfo:
        create_run(session, client_row, upload.id)

    assert excinfo.value.status_code == 422
    assert excinfo.value.detail["upload_id"] == upload.id


def test_create_run_on_another_tenants_upload_is_not_found(
    session: Session, client_row: Client, other_client_row: Client
):
    theirs = create_upload(session, other_client_row, "theirs.csv", GOOD)

    with pytest.raises(NotFoundError):
        create_run(session, client_row, theirs.id)


def test_get_run_is_tenant_scoped(session: Session, client_row: Client, other_client_row: Client):
    theirs_upload = create_upload(session, other_client_row, "theirs.csv", GOOD)
    theirs_run = create_run(session, other_client_row, theirs_upload.id)

    assert get_run(session, other_client_row.id, theirs_run.id).id == theirs_run.id
    with pytest.raises(NotFoundError):
        get_run(session, client_row.id, theirs_run.id)


def test_get_run_missing_id_is_not_found(session: Session, client_row: Client):
    with pytest.raises(NotFoundError):
        get_run(session, client_row.id, 9999)
    assert session.get(AnalysisRun, 9999) is None
```
(`io` is imported here because Task 5 appends tests to this same file that use it.)

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && .venv/Scripts/python -m pytest tests/services/test_analysis_service.py -v`
Expected: FAIL with `ImportError: cannot import name 'session_scope' from 'app.core.db'`

- [ ] **Step 3: Add `session_scope()` to `app/core/db.py`**

Add `from contextlib import contextmanager` to the imports, then replace everything from
`def get_session` down with:
```python
@contextmanager
def session_scope() -> Iterator[Session]:
    """A session outside the request cycle: background tasks, scripts, the CLI.

    `get_session()` is a FastAPI dependency and its session is closed before background
    tasks run, so anything that runs after the response must open its own.
    """
    get_engine()
    assert _session_factory is not None
    with _session_factory() as session:
        yield session


def get_session() -> Iterator[Session]:
    """FastAPI dependency: one session per request, always closed."""
    with session_scope() as session:
        yield session
```

- [ ] **Step 4: Write the first half of the analysis service**

`backend/app/services/analysis.py`:
```python
"""Analysis runs: create one, execute it in the background, and read the report back.

Money crossing from pandas floats into NUMERIC(14,2) goes through `to_money()` and
nowhere else (docs/PLAN.md section 1 #6).
"""

from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import InvalidUploadError, NotFoundError
from app.models import AnalysisRun, Client
from app.pipeline.config import PipelineConfig
from app.services.upload import get_upload

TWO_PLACES = Decimal("0.01")


def to_money(value: float) -> Decimal:
    """pandas float -> PKR NUMERIC(14,2). `repr` first so 0.125 rounds up, not to even."""
    return Decimal(repr(float(value))).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def to_money_or_none(value: float | None) -> Decimal | None:
    return None if value is None else to_money(value)


def create_run(session: Session, client: Client, upload_id: int) -> AnalysisRun:
    upload = get_upload(session, client.id, upload_id)  # 404 for another tenant
    if upload.status != "validated":
        raise InvalidUploadError(
            {
                "message": "this upload did not pass validation and cannot be analysed",
                "upload_id": upload.id,
            }
        )
    config = PipelineConfig.from_overrides(client.config_overrides or {})
    run = AnalysisRun(
        client_id=client.id,
        upload_id=upload.id,
        config_snapshot=config.to_dict(),
        status="queued",
        review_status="pending",
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    return run


def get_run(session: Session, client_id: int, run_id: int) -> AnalysisRun:
    run = session.scalars(
        select(AnalysisRun).where(AnalysisRun.id == run_id, AnalysisRun.client_id == client_id)
    ).first()
    if run is None:
        raise NotFoundError("run not found")
    return run
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd backend && .venv/Scripts/python -m pytest tests/services/test_analysis_service.py -v`
Expected: `12 passed` (5 parametrized `to_money` cases plus 7 others).

- [ ] **Step 6: Lint and commit**

Run: `cd backend && .venv/Scripts/ruff check . && .venv/Scripts/ruff format .`
```bash
git add backend/app/core/db.py backend/app/services/analysis.py \
        backend/tests/services/test_analysis_service.py
git commit -m "feat(analysis): session_scope, to_money and queued analysis runs" \
           -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 5: `execute_run()` — the background job that persists the analysis

**Files:**
- Modify: `backend/app/services/analysis.py`
- Modify: `backend/tests/services/test_analysis_service.py` (append)

**Interfaces:**
- Consumes: `session_scope()`, `to_money`, `to_money_or_none` (Task 4); `get_storage()` (Task 1); Stage 1's `load_csv`, `analyze_all_dimensions(df, config) -> dict[str, DimensionResult]`, `build_recommendations(results, config) -> list[Recommendation]`, `headline_waste(results) -> float`, `DIMENSIONS`; the models `AdDataUpload`, `WasteReport`, `SegmentMetric`, `Recommendation as RecommendationRow`.
- Produces:
  ```python
  execute_run(run_id: int) -> None
  # queued -> running -> done (or failed + error_message); writes one WasteReport per
  # dimension, one SegmentMetric per segment, one Recommendation per flagged segment,
  # and run.headline_waste
  ```
- Stage 1 fields used — `DimensionResult`: `dimension, benchmark_cpa, total_spend,
  total_wasted_spend, segments`. `SegmentMetrics`: `segment, spend, impressions, clicks,
  conversions, revenue, cpa, is_significant, is_flagged, wasted_spend`. Pipeline
  `Recommendation`: `dimension, segment_name, current_spend, recommended_cut, reason`.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/services/test_analysis_service.py` (and add the imports shown to
the top of the file):
```python
from pathlib import Path

from sqlalchemy import select

from app.models import Recommendation as RecommendationRow
from app.models import SegmentMetric, WasteReport
from app.pipeline.analyzer import analyze_all_dimensions
from app.pipeline.data_generator import write_sample_csv
from app.pipeline.loader import load_csv
from app.pipeline.optimizer import headline_waste
from app.services.analysis import execute_run
from app.services.storage import get_storage

WASTE = {"placement": {"audience_network": 3.0}}


def _upload_sample(session: Session, client: Client, tmp_path: Path) -> AdDataUpload:
    path = write_sample_csv(tmp_path / "sample.csv", days=30, seed=42, waste=WASTE)
    return create_upload(session, client, "sample.csv", path.read_bytes())


def _expected(raw: bytes):
    result = load_csv(io.BytesIO(raw), PipelineConfig())
    assert result.ok, result.errors
    return analyze_all_dimensions(result.df, PipelineConfig())


def test_execute_run_persists_every_dimension_segment_and_recommendation(
    session: Session, client_row: Client, tmp_path: Path
):
    upload = _upload_sample(session, client_row, tmp_path)
    run = create_run(session, client_row, upload.id)
    expected = _expected(get_storage().read(upload.file_path))

    execute_run(run.id)

    session.expire_all()
    run = session.get(AnalysisRun, run.id)
    assert run.status == "done"
    assert run.error_message is None
    assert run.review_status == "pending", "approval is a Stage 6 admin action"
    assert run.headline_waste == to_money(headline_waste(expected))

    reports = session.scalars(
        select(WasteReport).where(WasteReport.run_id == run.id).order_by(WasteReport.id)
    ).all()
    assert [r.dimension for r in reports] == ["placement", "age_group", "time_slot"]
    for report in reports:
        dim = expected[report.dimension]
        assert report.client_id == client_row.id
        assert report.upload_id == upload.id
        assert report.total_spend == to_money(dim.total_spend)
        assert report.total_wasted_spend == to_money(dim.total_wasted_spend)
        assert report.benchmark_cpa == to_money(dim.benchmark_cpa)
        segments = session.scalars(
            select(SegmentMetric).where(SegmentMetric.report_id == report.id)
        ).all()
        assert len(segments) == len(dim.segments)

    placement = next(r for r in reports if r.dimension == "placement")
    flagged = session.scalars(
        select(SegmentMetric).where(
            SegmentMetric.report_id == placement.id, SegmentMetric.is_flagged.is_(True)
        )
    ).all()
    assert [s.segment_value for s in flagged] == ["audience_network"]
    assert flagged[0].wasted_spend > 0
    assert flagged[0].is_significant

    recs = session.scalars(
        select(RecommendationRow).where(RecommendationRow.report_id == placement.id)
    ).all()
    assert [r.segment_name for r in recs] == ["audience_network"]
    assert recs[0].recommended_cut <= flagged[0].spend
    assert "audience network" in recs[0].reason.lower()


def test_execute_run_stores_money_as_two_place_decimals(
    session: Session, client_row: Client, tmp_path: Path
):
    upload = _upload_sample(session, client_row, tmp_path)
    run = create_run(session, client_row, upload.id)

    execute_run(run.id)

    session.expire_all()
    values = session.scalars(select(SegmentMetric.spend)).all()
    assert values
    for value in values:
        assert isinstance(value, Decimal)
        assert value.as_tuple().exponent == -2


def test_execute_run_uses_the_snapshot_not_the_live_client_config(
    session: Session, client_row: Client, tmp_path: Path
):
    upload = _upload_sample(session, client_row, tmp_path)
    run = create_run(session, client_row, upload.id)
    expected = _expected(get_storage().read(upload.file_path))

    # The admin changes the client's thresholds after the run was queued: with a 99x
    # multiplier nothing would ever be flagged, so a zero headline would prove the bug.
    client_row.config_overrides = {"waste_multiplier": 99.0}
    session.commit()

    execute_run(run.id)

    session.expire_all()
    run = session.get(AnalysisRun, run.id)
    assert run.headline_waste == to_money(headline_waste(expected))
    assert run.headline_waste > 0


def test_execute_run_marks_the_run_failed_when_the_file_is_gone(
    session: Session, client_row: Client, tmp_path: Path
):
    upload = _upload_sample(session, client_row, tmp_path)
    run = create_run(session, client_row, upload.id)
    get_storage().delete(upload.file_path)

    execute_run(run.id)

    session.expire_all()
    run = session.get(AnalysisRun, run.id)
    assert run.status == "failed"
    assert upload.file_sha256 in run.error_message
    assert session.scalars(select(WasteReport).where(WasteReport.run_id == run.id)).all() == []


def test_execute_run_on_an_unknown_id_is_a_no_op():
    execute_run(987654)  # must not raise
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && .venv/Scripts/python -m pytest tests/services/test_analysis_service.py -k execute -v`
Expected: FAIL with `ImportError: cannot import name 'execute_run' from 'app.services.analysis'`

- [ ] **Step 3: Write `execute_run`**

Append to `backend/app/services/analysis.py`, extending its imports with:
```python
import io

from app.core.db import session_scope
from app.models import AdDataUpload
from app.models import Recommendation as RecommendationRow
from app.models import SegmentMetric, WasteReport
from app.pipeline.analyzer import analyze_all_dimensions
from app.pipeline.config import DIMENSIONS
from app.pipeline.loader import load_csv
from app.pipeline.optimizer import build_recommendations, headline_waste
from app.services.storage import get_storage
```
```python
def execute_run(run_id: int) -> None:
    """FastAPI BackgroundTask. Runs after the response, so it opens its own session."""
    with session_scope() as session:
        run = session.get(AnalysisRun, run_id)
        if run is None:
            return
        run.status = "running"
        session.commit()
        try:
            _persist_analysis(session, run)
        except Exception as exc:  # noqa: BLE001 - every failure must land on the run row
            session.rollback()
            failed = session.get(AnalysisRun, run_id)
            if failed is not None:
                failed.status = "failed"
                failed.error_message = f"{type(exc).__name__}: {exc}"[:1000]
                session.commit()


def _persist_analysis(session: Session, run: AnalysisRun) -> None:
    upload = session.get(AdDataUpload, run.upload_id)
    if upload is None:
        raise RuntimeError(f"upload {run.upload_id} no longer exists")

    data = get_storage().read(upload.file_path)
    config = PipelineConfig.from_overrides(run.config_snapshot)  # the snapshot, never the client
    result = load_csv(io.BytesIO(data), config)
    if not result.ok:
        raise RuntimeError(f"stored file failed validation: {result.errors[0].message}")

    results = analyze_all_dimensions(result.df, config)
    by_dimension: dict[str, list] = {dimension: [] for dimension in DIMENSIONS}
    for rec in build_recommendations(results, config):
        by_dimension[rec.dimension].append(rec)

    for dimension in DIMENSIONS:
        dim = results[dimension]
        report = WasteReport(
            run_id=run.id,
            client_id=run.client_id,
            upload_id=run.upload_id,
            dimension=dimension,
            total_spend=to_money(dim.total_spend),
            total_wasted_spend=to_money(dim.total_wasted_spend),
            benchmark_cpa=to_money_or_none(dim.benchmark_cpa),
        )
        session.add(report)
        session.flush()  # we need report.id for the children

        for seg in dim.segments:
            session.add(
                SegmentMetric(
                    report_id=report.id,
                    segment_value=seg.segment,
                    spend=to_money(seg.spend),
                    impressions=seg.impressions,
                    clicks=seg.clicks,
                    conversions=seg.conversions,
                    revenue=to_money(seg.revenue),
                    cpa=to_money_or_none(seg.cpa),
                    is_significant=seg.is_significant,
                    is_flagged=seg.is_flagged,
                    wasted_spend=to_money(seg.wasted_spend),
                )
            )

        for rec in by_dimension[dimension]:
            session.add(
                RecommendationRow(
                    report_id=report.id,
                    dimension=dimension,
                    segment_name=rec.segment_name,
                    current_spend=to_money(rec.current_spend),
                    recommended_cut=to_money(rec.recommended_cut),
                    reason=rec.reason,
                )
            )

    run.headline_waste = to_money(headline_waste(results))
    run.status = "done"
    session.commit()
```
Note the aliased import: `app.models.Recommendation` (the table) and
`app.pipeline.optimizer.Recommendation` (the dataclass) share a name, so the model is
imported as `RecommendationRow` everywhere in this stage.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && .venv/Scripts/python -m pytest tests/services/test_analysis_service.py -v`
Expected: `17 passed`. If it fails on `benchmark_cpa` because a dimension's benchmark is
`None`, the generated data has no significant segments for that dimension — keep `days=30`
(as written) rather than relaxing the assertion. `to_money(None)` would raise, which is
exactly why `to_money_or_none` exists for the nullable columns.

- [ ] **Step 5: Lint and commit**

Run: `cd backend && .venv/Scripts/ruff check . && .venv/Scripts/ruff format .`
```bash
git add backend/app/services/analysis.py backend/tests/services/test_analysis_service.py
git commit -m "feat(analysis): background execute_run persisting reports, segments and recs" \
           -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 6: Report schemas and the approval-gated read model

**Files:**
- Create: `backend/app/schemas/reports.py`
- Modify: `backend/app/services/analysis.py` (append `get_report`, `latest_report`, `_build_report`)
- Create: `backend/tests/services/test_reports_service.py`

**Interfaces:**
- Consumes: `get_run` (Task 4); `execute_run` (Task 5); the models `WasteReport`, `SegmentMetric`, `Recommendation as RecommendationRow`, `AdDataUpload`.
- Produces:
  ```python
  # app/schemas/reports.py   (names and fields verbatim from INTERFACES.md)
  SegmentOut(segment, spend, impressions, clicks, conversions, revenue, cpa, ctr, cvr, roas,
             is_significant, is_flagged, wasted_spend, flag_reason)
      SegmentOut.from_row(row: SegmentMetric) -> SegmentOut
  DimensionOut(dimension, benchmark_cpa, total_spend, total_wasted_spend,
               segments: list[SegmentOut])
  RecommendationOut(id, dimension, segment_name, current_spend, recommended_cut, reason)
  ReportOut(run_id, upload_id, generated_at, date_range_start, date_range_end, total_spend,
            headline_waste, recovery_pct, dimensions: list[DimensionOut],
            recommendations: list[RecommendationOut], config_snapshot: dict)
  RunOut(id, upload_id, status, review_status, headline_waste, error_message, created_at)
  # app/services/analysis.py
  get_report(session, client_id: int, run_id: int) -> ReportOut    # NotFoundError unless
                                                                   # status done AND approved
  latest_report(session, client_id: int) -> ReportOut | None
  ```

- [ ] **Step 1: Write the failing tests**

`backend/tests/services/test_reports_service.py`:
```python
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.models import AnalysisRun, Client
from app.pipeline.data_generator import write_sample_csv
from app.services.analysis import create_run, execute_run, get_report, latest_report
from app.services.upload import create_upload

WASTE = {"placement": {"audience_network": 3.0}}


def _done_run(
    session: Session, client: Client, tmp_path: Path, name: str = "s.csv", seed: int = 42
) -> AnalysisRun:
    # A different seed means different bytes, so a second sample is not a duplicate upload.
    path = write_sample_csv(tmp_path / name, days=30, seed=seed, waste=WASTE)
    upload = create_upload(session, client, name, path.read_bytes())
    run = create_run(session, client, upload.id)
    execute_run(run.id)
    session.expire_all()
    return session.get(AnalysisRun, run.id)


def _approve(session: Session, run: AnalysisRun) -> None:
    run.review_status = "approved"  # Stage 6 gives the admin a real endpoint for this
    session.commit()


def test_a_pending_run_has_no_report_for_the_client(
    session: Session, client_row: Client, tmp_path: Path
):
    run = _done_run(session, client_row, tmp_path)
    assert run.status == "done" and run.review_status == "pending"

    with pytest.raises(NotFoundError) as excinfo:
        get_report(session, client_row.id, run.id)

    assert excinfo.value.status_code == 404


def test_an_approved_run_returns_the_full_report(
    session: Session, client_row: Client, tmp_path: Path
):
    run = _done_run(session, client_row, tmp_path)
    _approve(session, run)

    report = get_report(session, client_row.id, run.id)

    assert report.run_id == run.id
    assert report.upload_id == run.upload_id
    assert [d.dimension for d in report.dimensions] == ["placement", "age_group", "time_slot"]
    assert report.headline_waste == run.headline_waste
    assert report.total_spend == max(d.total_spend for d in report.dimensions)
    assert report.config_snapshot == run.config_snapshot
    assert str(report.date_range_start) == "2026-08-01"
    assert report.recommendations, "the injected waste must produce at least one recommendation"
    assert report.recommendations == sorted(
        report.recommendations, key=lambda r: r.recommended_cut, reverse=True
    )


def test_recovery_pct_is_headline_waste_over_total_spend(
    session: Session, client_row: Client, tmp_path: Path
):
    run = _done_run(session, client_row, tmp_path)
    _approve(session, run)

    report = get_report(session, client_row.id, run.id)

    expected = (report.headline_waste / report.total_spend * 100).quantize(Decimal("0.01"))
    assert report.recovery_pct == expected
    assert Decimal("0") < report.recovery_pct < Decimal("100")


def test_segments_carry_derived_rates_and_a_flag_reason(
    session: Session, client_row: Client, tmp_path: Path
):
    run = _done_run(session, client_row, tmp_path)
    _approve(session, run)

    report = get_report(session, client_row.id, run.id)
    placement = next(d for d in report.dimensions if d.dimension == "placement")
    flagged = [s for s in placement.segments if s.is_flagged]

    assert [s.segment for s in flagged] == ["audience_network"]
    assert flagged[0].flag_reason == "high_cpa"
    assert flagged[0].is_significant
    assert flagged[0].ctr == pytest.approx(flagged[0].clicks / flagged[0].impressions)
    assert flagged[0].cvr == pytest.approx(flagged[0].conversions / flagged[0].clicks)
    assert flagged[0].roas == pytest.approx(float(flagged[0].revenue) / float(flagged[0].spend))
    assert all(s.flag_reason is None for s in placement.segments if not s.is_flagged)
    assert placement.segments == sorted(placement.segments, key=lambda s: s.spend, reverse=True)


def test_a_client_cannot_read_another_tenants_report(
    session: Session, client_row: Client, other_client_row: Client, tmp_path: Path
):
    run = _done_run(session, other_client_row, tmp_path)
    _approve(session, run)

    with pytest.raises(NotFoundError):
        get_report(session, client_row.id, run.id)


def test_latest_report_is_none_until_a_run_is_approved(
    session: Session, client_row: Client, tmp_path: Path
):
    run = _done_run(session, client_row, tmp_path)

    assert latest_report(session, client_row.id) is None

    _approve(session, run)
    assert latest_report(session, client_row.id).run_id == run.id


def test_latest_report_picks_the_newest_approved_run(
    session: Session, client_row: Client, tmp_path: Path
):
    older = _done_run(session, client_row, tmp_path, "older.csv", seed=42)
    _approve(session, older)
    newer = _done_run(session, client_row, tmp_path, "newer.csv", seed=43)
    _approve(session, newer)

    assert latest_report(session, client_row.id).run_id == newer.id


def test_latest_report_ignores_other_tenants(
    session: Session, client_row: Client, other_client_row: Client, tmp_path: Path
):
    theirs = _done_run(session, other_client_row, tmp_path, "theirs.csv")
    _approve(session, theirs)

    assert latest_report(session, client_row.id) is None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && .venv/Scripts/python -m pytest tests/services/test_reports_service.py -v`
Expected: FAIL with `ImportError: cannot import name 'get_report' from 'app.services.analysis'`

- [ ] **Step 3: Write the report schemas**

`backend/app/schemas/reports.py`:
```python
"""Read models for the dashboard.

Decimal fields serialise as JSON strings (Pydantic v2's default), which keeps rupee values
exact across the wire; the Stage 4 client parses them with Number().
"""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.models import SegmentMetric


class SegmentOut(BaseModel):
    segment: str
    spend: Decimal
    impressions: int
    clicks: int
    conversions: int
    revenue: Decimal
    cpa: Decimal | None
    ctr: float
    cvr: float
    roas: float | None
    is_significant: bool
    is_flagged: bool
    wasted_spend: Decimal
    flag_reason: str | None

    @classmethod
    def from_row(cls, row: SegmentMetric) -> "SegmentOut":
        """ctr/cvr/roas/flag_reason are derived, not stored.

        `segment_metrics` (docs/PLAN.md section 4) has no columns for them, and all four
        follow exactly from what is stored: a flagged segment with zero conversions is a
        zero-conversions flag, and any other flagged segment is a high-CPA flag (the
        analyzer can only raise high_cpa when conversions > 0).
        """
        spend = float(row.spend)
        flag_reason: str | None = None
        if row.is_flagged:
            flag_reason = "zero_conversions" if row.conversions == 0 else "high_cpa"
        return cls(
            segment=row.segment_value,
            spend=row.spend,
            impressions=row.impressions,
            clicks=row.clicks,
            conversions=row.conversions,
            revenue=row.revenue,
            cpa=row.cpa,
            ctr=row.clicks / row.impressions if row.impressions else 0.0,
            cvr=row.conversions / row.clicks if row.clicks else 0.0,
            roas=float(row.revenue) / spend if spend else None,
            is_significant=row.is_significant,
            is_flagged=row.is_flagged,
            wasted_spend=row.wasted_spend,
            flag_reason=flag_reason,
        )


class DimensionOut(BaseModel):
    dimension: str
    benchmark_cpa: Decimal | None
    total_spend: Decimal
    total_wasted_spend: Decimal
    segments: list[SegmentOut]


class RecommendationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    dimension: str
    segment_name: str
    current_spend: Decimal
    recommended_cut: Decimal
    reason: str


class ReportOut(BaseModel):
    run_id: int
    upload_id: int
    generated_at: datetime
    date_range_start: date | None
    date_range_end: date | None
    total_spend: Decimal
    headline_waste: Decimal
    recovery_pct: Decimal
    dimensions: list[DimensionOut]
    recommendations: list[RecommendationOut]
    config_snapshot: dict


class RunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    upload_id: int
    status: str
    review_status: str
    headline_waste: Decimal | None
    error_message: str | None
    created_at: datetime
```

- [ ] **Step 4: Write the read model**

Append to `backend/app/services/analysis.py` (extend its imports with
`from app.schemas.reports import DimensionOut, RecommendationOut, ReportOut, SegmentOut`):
```python
ZERO = Decimal("0.00")


def get_report(session: Session, client_id: int, run_id: int) -> ReportOut:
    """Clients only ever see finished, admin-approved runs (docs/PLAN.md section 4)."""
    run = get_run(session, client_id, run_id)
    if run.status != "done" or run.review_status != "approved":
        raise NotFoundError("report not found")
    return _build_report(session, run)


def latest_report(session: Session, client_id: int) -> ReportOut | None:
    run = session.scalars(
        select(AnalysisRun)
        .where(
            AnalysisRun.client_id == client_id,
            AnalysisRun.status == "done",
            AnalysisRun.review_status == "approved",
        )
        .order_by(AnalysisRun.created_at.desc(), AnalysisRun.id.desc())
    ).first()
    return None if run is None else _build_report(session, run)


def _build_report(session: Session, run: AnalysisRun) -> ReportOut:
    upload = session.get(AdDataUpload, run.upload_id)
    reports = list(
        session.scalars(
            select(WasteReport).where(WasteReport.run_id == run.id).order_by(WasteReport.id)
        )
    )

    dimensions: list[DimensionOut] = []
    recommendations: list[RecommendationOut] = []
    for report in reports:
        segments = session.scalars(
            select(SegmentMetric)
            .where(SegmentMetric.report_id == report.id)
            .order_by(SegmentMetric.spend.desc(), SegmentMetric.id)
        )
        dimensions.append(
            DimensionOut(
                dimension=report.dimension,
                benchmark_cpa=report.benchmark_cpa,
                total_spend=report.total_spend,
                total_wasted_spend=report.total_wasted_spend,
                segments=[SegmentOut.from_row(s) for s in segments],
            )
        )
        rows = session.scalars(
            select(RecommendationRow)
            .where(RecommendationRow.report_id == report.id)
            .order_by(RecommendationRow.recommended_cut.desc(), RecommendationRow.id)
        )
        recommendations.extend(RecommendationOut.model_validate(row) for row in rows)

    recommendations.sort(key=lambda rec: rec.recommended_cut, reverse=True)

    # Account spend = the widest dimension's total. Dimensions can cover different subsets
    # of the rows (docs/PLAN.md section 1 #3), so the largest is the best account figure.
    total_spend = max((d.total_spend for d in dimensions), default=ZERO)
    headline = run.headline_waste if run.headline_waste is not None else ZERO
    recovery_pct = (
        ZERO
        if total_spend == 0
        else (headline / total_spend * 100).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    )

    return ReportOut(
        run_id=run.id,
        upload_id=run.upload_id,
        generated_at=reports[0].generated_at if reports else run.created_at,
        date_range_start=upload.date_range_start if upload else None,
        date_range_end=upload.date_range_end if upload else None,
        total_spend=total_spend,
        headline_waste=headline,
        recovery_pct=recovery_pct,
        dimensions=dimensions,
        recommendations=recommendations,
        config_snapshot=run.config_snapshot,
    )
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd backend && .venv/Scripts/python -m pytest tests/services/test_reports_service.py -v`
Expected: `8 passed`.

- [ ] **Step 6: Lint and commit**

Run: `cd backend && .venv/Scripts/ruff check . && .venv/Scripts/ruff format .`
```bash
git add backend/app/schemas/reports.py backend/app/services/analysis.py \
        backend/tests/services/test_reports_service.py
git commit -m "feat(reports): approval-gated report read model with recovery_pct" \
           -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 7: `/api/analyze`, `/api/runs` and `/api/reports` routers

**Files:**
- Create: `backend/app/routers/analysis.py`, `backend/app/routers/reports.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/api/test_analysis.py`

**Interfaces:**
- Consumes: `create_run`, `execute_run`, `get_run`, `get_report`, `latest_report` (Tasks 4–6); `RunOut`, `ReportOut` (Task 6); `CurrentClient`, `get_session`; the fixtures `client_a`, `client_b`, `admin_client`, `client_a_row`, `db` (Task 3).
- Produces:
  ```python
  # app/routers/analysis.py  (prefix "/api")
  # POST /api/analyze/{upload_id} -> 202 RunOut, schedules execute_run(run.id) in the background
  # GET  /api/runs/{run_id}       -> 200 RunOut | 404
  # app/routers/reports.py   (prefix "/api/reports")
  # GET  /api/reports/latest      -> 200 ReportOut | 404   (declared BEFORE /{run_id})
  # GET  /api/reports/{run_id}    -> 200 ReportOut | 404
  ```
- **How the background task is exercised in tests:** Starlette's `TestClient` runs
  `BackgroundTasks` synchronously as part of the request, so by the time
  `client_a.post("/api/analyze/...")` returns, `execute_run` has already finished and the
  run is `done`. No sleeping, no polling loop, and no calling `execute_run` by hand in the
  API tests — the service tests in Task 5 already call it directly for the failure path.

- [ ] **Step 1: Write the failing tests**

`backend/tests/api/test_analysis.py`:
```python
import io
from decimal import Decimal
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AnalysisRun, Client
from app.pipeline.analyzer import analyze_all_dimensions
from app.pipeline.config import PipelineConfig
from app.pipeline.data_generator import write_sample_csv
from app.pipeline.loader import load_csv
from app.pipeline.optimizer import headline_waste
from app.services.analysis import to_money

WASTE = {"placement": {"audience_network": 3.0}}


def _sample_bytes(tmp_path: Path, name: str = "sample.csv", seed: int = 42) -> bytes:
    return write_sample_csv(tmp_path / name, days=30, seed=seed, waste=WASTE).read_bytes()


def _upload(http: TestClient, body: bytes, name: str = "sample.csv") -> int:
    response = http.post("/api/uploads", files={"file": (name, body, "text/csv")})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _approve(db: Session, run_id: int) -> None:
    run = db.get(AnalysisRun, run_id)
    run.review_status = "approved"  # Stage 6 replaces this with POST /api/admin/runs/{id}/approve
    db.commit()


def test_analyze_returns_202_and_the_run_reaches_done(
    client_a: TestClient, tmp_path: Path, db: Session
):
    upload_id = _upload(client_a, _sample_bytes(tmp_path))

    response = client_a.post(f"/api/analyze/{upload_id}")

    assert response.status_code == 202, response.text
    run = response.json()
    assert run["upload_id"] == upload_id
    assert run["review_status"] == "pending"
    assert "client_id" not in run

    # TestClient runs BackgroundTasks inside the request, so the job is already finished.
    polled = client_a.get(f"/api/runs/{run['id']}").json()
    assert polled["status"] == "done", polled
    assert polled["error_message"] is None
    assert Decimal(polled["headline_waste"]) > 0
    db.expire_all()
    assert db.get(AnalysisRun, run["id"]).status == "done"


def test_analyze_on_an_upload_that_failed_validation_is_422(client_a: TestClient):
    header = (
        "date,campaign_id,placement,age_group,gender,device,time_slot,"
        "spend,impressions,clicks,conversions,revenue\n"
    )
    bad = header + "2026-08-01,C1,facebook_feed,25-34,male,mobile,morning,abc,1000,20,1,500\n"
    rejected = client_a.post("/api/uploads", files={"file": ("bad.csv", bad.encode(), "text/csv")})
    upload_id = rejected.json()["detail"]["upload_id"]

    response = client_a.post(f"/api/analyze/{upload_id}")

    assert response.status_code == 422


def test_report_numbers_match_the_pipeline_on_the_same_file(
    client_a: TestClient, tmp_path: Path, db: Session
):
    body = _sample_bytes(tmp_path)
    upload_id = _upload(client_a, body)
    run_id = client_a.post(f"/api/analyze/{upload_id}").json()["id"]
    _approve(db, run_id)

    report = client_a.get(f"/api/reports/{run_id}").json()

    loaded = load_csv(io.BytesIO(body), PipelineConfig())
    assert loaded.ok, loaded.errors
    expected = analyze_all_dimensions(loaded.df, PipelineConfig())

    assert Decimal(report["headline_waste"]) == to_money(headline_waste(expected))
    assert {d["dimension"] for d in report["dimensions"]} == set(expected)
    for dim in report["dimensions"]:
        result = expected[dim["dimension"]]
        assert Decimal(dim["total_wasted_spend"]) == to_money(result.total_wasted_spend)
        assert Decimal(dim["total_spend"]) == to_money(result.total_spend)
        assert Decimal(dim["benchmark_cpa"]) == to_money(result.benchmark_cpa)
        assert len(dim["segments"]) == len(result.segments)

    placement = next(d for d in report["dimensions"] if d["dimension"] == "placement")
    assert [s["segment"] for s in placement["segments"] if s["is_flagged"]] == ["audience_network"]
    assert Decimal(report["recovery_pct"]) > 0
    assert report["config_snapshot"] == PipelineConfig().to_dict()


def test_report_is_404_while_pending_and_200_once_approved(
    client_a: TestClient, tmp_path: Path, db: Session
):
    upload_id = _upload(client_a, _sample_bytes(tmp_path))
    run_id = client_a.post(f"/api/analyze/{upload_id}").json()["id"]

    pending = client_a.get(f"/api/reports/{run_id}")
    assert pending.status_code == 404
    assert client_a.get("/api/reports/latest").status_code == 404

    _approve(db, run_id)

    approved = client_a.get(f"/api/reports/{run_id}")
    assert approved.status_code == 200
    assert approved.json()["run_id"] == run_id
    assert client_a.get("/api/reports/latest").json()["run_id"] == run_id


def test_client_a_cannot_reach_client_bs_run_or_report(
    client_a: TestClient, client_b: TestClient, tmp_path: Path, db: Session
):
    upload_id = _upload(client_b, _sample_bytes(tmp_path))
    run_id = client_b.post(f"/api/analyze/{upload_id}").json()["id"]
    _approve(db, run_id)
    assert client_b.get(f"/api/reports/{run_id}").status_code == 200

    assert client_a.get(f"/api/uploads/{upload_id}").status_code == 404
    assert client_a.get(f"/api/runs/{run_id}").status_code == 404
    assert client_a.get(f"/api/reports/{run_id}").status_code == 404
    assert client_a.post(f"/api/analyze/{upload_id}").status_code == 404
    assert client_a.get("/api/reports/latest").status_code == 404


def test_the_run_is_owned_by_the_caller_from_the_jwt(
    client_a: TestClient, tmp_path: Path, db: Session, client_a_row: Client
):
    upload_id = _upload(client_a, _sample_bytes(tmp_path))

    run_id = client_a.post(f"/api/analyze/{upload_id}").json()["id"]

    db.expire_all()
    run = db.scalars(select(AnalysisRun).where(AnalysisRun.id == run_id)).one()
    assert run.client_id == client_a_row.id


def test_an_admin_is_not_a_client_on_client_routes(admin_client: TestClient):
    assert admin_client.get("/api/reports/latest").status_code == 403
    assert admin_client.get("/api/uploads").status_code == 403
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && .venv/Scripts/python -m pytest tests/api/test_analysis.py -v`
Expected: FAIL with `assert 404 == 202`, because `/api/analyze/{upload_id}` is not mounted.

- [ ] **Step 3: Write the analysis router**

`backend/app/routers/analysis.py`:
```python
"""POST /api/analyze/{upload_id} and GET /api/runs/{id} — docs/PLAN.md section 5."""

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.orm import Session

from app.core.db import get_session
from app.core.deps import CurrentClient
from app.models import AnalysisRun
from app.schemas.reports import RunOut
from app.services.analysis import create_run, execute_run, get_run

router = APIRouter(prefix="/api", tags=["analysis"])

SessionDep = Annotated[Session, Depends(get_session)]


@router.post("/analyze/{upload_id}", status_code=202, response_model=RunOut)
def start_analysis(
    upload_id: int,
    background_tasks: BackgroundTasks,
    client: CurrentClient,
    session: SessionDep,
) -> AnalysisRun:
    run = create_run(session, client, upload_id)
    # No Redis in the MVP (docs/PLAN.md section 0): FastAPI BackgroundTasks. The task opens
    # its own session, because this request's session is closed before it runs.
    background_tasks.add_task(execute_run, run.id)
    return run


@router.get("/runs/{run_id}", response_model=RunOut)
def read_run(run_id: int, client: CurrentClient, session: SessionDep) -> AnalysisRun:
    return get_run(session, client.id, run_id)
```

- [ ] **Step 4: Write the reports router**

`backend/app/routers/reports.py`:
```python
"""GET /api/reports/latest and /api/reports/{run_id} — approved runs only."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_session
from app.core.deps import CurrentClient
from app.core.errors import NotFoundError
from app.schemas.reports import ReportOut
from app.services.analysis import get_report, latest_report

router = APIRouter(prefix="/api/reports", tags=["reports"])

SessionDep = Annotated[Session, Depends(get_session)]


# Declared before "/{run_id}" so the literal path wins the match.
@router.get("/latest", response_model=ReportOut)
def read_latest_report(client: CurrentClient, session: SessionDep) -> ReportOut:
    report = latest_report(session, client.id)
    if report is None:
        raise NotFoundError("no approved report yet")
    return report


@router.get("/{run_id}", response_model=ReportOut)
def read_report(run_id: int, client: CurrentClient, session: SessionDep) -> ReportOut:
    return get_report(session, client.id, run_id)
```

- [ ] **Step 5: Mount both routers**

In `backend/app/main.py`, extend the import and the `include_router` block:
```python
from app.routers import analysis, auth, reports, uploads
```
```python
    application.include_router(auth.router)
    application.include_router(uploads.router)
    application.include_router(analysis.router)
    application.include_router(reports.router)
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `cd backend && .venv/Scripts/python -m pytest tests/api/test_analysis.py -v`
Expected: `7 passed`. If `polled["status"]` is `"queued"`, the background task never ran —
check that the endpoint calls `background_tasks.add_task(...)` on an injected
`BackgroundTasks` parameter (returning your own `JSONResponse` with `background=` would
bypass it). If it is `"failed"`, print `polled["error_message"]`: `FileNotFoundError` means
the request and `api_env` disagreed about `storage_root`, and
`OperationalError: no such table` means `bound_engine` did not patch `app.core.db`.

- [ ] **Step 7: Lint and commit**

Run: `cd backend && .venv/Scripts/ruff check . && .venv/Scripts/ruff format .`
```bash
git add backend/app/routers/analysis.py backend/app/routers/reports.py backend/app/main.py \
        backend/tests/api/test_analysis.py
git commit -m "feat(api): analyze/runs/reports endpoints with approval and tenant gates" \
           -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 8: Confirm no migration is needed, document, and gate the suite

**Files:**
- Modify: `README.md`
- Modify: `backend/.env.example`
- Verify only: `backend/alembic/versions/55eb15843c97_initial_schema.py`

**Interfaces:** none new.

- [ ] **Step 1: Prove the schema is unchanged**

Stage 3 writes only columns that `55eb15843c97_initial_schema` already created:
`ad_data_uploads` (`file_path`, `file_sha256`, `row_count`, `date_range_start`,
`date_range_end`, `status`, `validation_report`), `analysis_runs` (`config_snapshot`,
`status`, `review_status`, `headline_waste`, `error_message`), `waste_reports`,
`segment_metrics` and `recommendations`. `ctr`, `cvr`, `roas` and `flag_reason` are
**derived in `SegmentOut.from_row`**, not stored, which is why no new column is required.

Run:
```bash
cd backend && DATABASE_URL="sqlite:///./dev.db" .venv/Scripts/alembic upgrade head \
  && DATABASE_URL="sqlite:///./dev.db" .venv/Scripts/alembic check
```
Expected: `No new upgrade operations detected.`
If it prints `New upgrade operations detected` instead, a model was changed by mistake —
revert that model change. Only if a column genuinely turns out to be missing, add it here:
`.venv/Scripts/alembic revision --autogenerate -m "stage 3: <column>"`, read the generated
file before keeping it, re-run `alembic upgrade head`, and commit the revision together with
the code that needs it.

- [ ] **Step 2: Document the new settings**

Append to `backend/.env.example`:
```dotenv
# Stage 3 — file storage and upload limits
STORAGE_BACKEND=local
STORAGE_ROOT=./storage
MAX_UPLOAD_MB=20
```
Check that the repo-root `.gitignore` ignores uploaded files; if it does not, add:
```gitignore
backend/storage/
```

- [ ] **Step 3: Document the endpoints**

Append to `README.md` under the backend section:
````markdown
### Uploads & analysis (Stage 3)

All routes need the client session cookies from `POST /api/auth/login`.

```bash
curl -b cookies.txt -F "file=@august.csv" http://localhost:8000/api/uploads   # 201, or 422 + row errors
curl -b cookies.txt -X POST http://localhost:8000/api/analyze/1               # 202 + run id
curl -b cookies.txt http://localhost:8000/api/runs/1                          # queued|running|done|failed
curl -b cookies.txt http://localhost:8000/api/reports/1                       # 404 until an admin approves
curl -O http://localhost:8000/api/uploads/template.csv                        # blank template
```

Uploaded CSVs are written through the storage interface (`STORAGE_ROOT`, default
`./storage`). Files over `MAX_UPLOAD_MB` are rejected with 413, and re-uploading identical
bytes with 409. A report becomes visible only once its run is `done` **and** an admin has
set `review_status = approved` (Stage 6).
````

- [ ] **Step 4: Run the whole suite and the linter**

Run: `cd backend && .venv/Scripts/ruff check . && .venv/Scripts/ruff format --check . && .venv/Scripts/python -m pytest -q`
Expected: `All checks passed!`, `N files already formatted`, and every test passing —
Stage 0 + Stage 1 + Stage 2 plus this stage's 62 new tests (11 + 10 + 9 + 17 + 8 + 7).

Run: `cd backend && .venv/Scripts/python -m pytest --cov --cov-report=term-missing`
Expected: the Stage 1 gate (`app/pipeline` ≥ 90%) still passes — this stage adds no
pipeline code and so cannot lower it.

- [ ] **Step 5: Commit**

```bash
git add README.md backend/.env.example .gitignore
git commit -m "docs(stage-3): document upload/analysis endpoints and storage settings" \
           -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

## Stage 3 exit checklist (from `docs/PLAN.md` §6)

- [ ] A sample file goes upload → pending run with correct stored numbers
      (`tests/api/test_analysis.py::test_report_numbers_match_the_pipeline_on_the_same_file`).
- [ ] The isolation tests pass (`test_client_a_cannot_read_client_bs_upload`,
      `test_client_a_cannot_reach_client_bs_run_or_report`) — every cross-tenant read is 404,
      never 403.
- [ ] Row-level validation errors reach the client
      (`test_invalid_csv_returns_422_with_row_level_errors`).
- [ ] Size limit (413), duplicate detection (409) and the template CSV round-trip are covered.
- [ ] `alembic check` reports no new operations.
- [ ] Owner checkpoint: run the four `curl` commands from the README against a local server
      and eyeball the JSON before Stage 4 starts.

## Decisions

1. **`save()` returns the storage key, and the key is what `AdDataUpload.file_path` holds.**
   `StorageBackend.read(key)` then round-trips straight from the DB row, and the same row
   keeps working when Stage 8 swaps in `SupabaseStorage`.
2. **`get_storage()` is not cached.** Tests point `storage_root` at a per-test `tmp_path`;
   a cache would leak the first test's directory into every later one.
3. **Service errors are `AppError` subclasses carrying a `status_code`, rendered by one
   handler in `create_app()`.** Services stay importable by the background task and by
   `scripts/` without dragging FastAPI in.
4. **A CSV that fails validation is still stored, with `status = "failed"`**, and the router
   turns it into a 422 whose `detail` carries `upload_id` plus the row-level errors. The
   client sees exactly which lines to fix, and the file stays available for support.
5. **`ctr`, `cvr`, `roas` and `flag_reason` are derived in `SegmentOut.from_row`, not stored.**
   `segment_metrics` (`docs/PLAN.md` §4) has no columns for them and all four follow exactly
   from the stored values — so Stage 3 needs no Alembic migration.
6. **`ReportOut.total_spend` is the largest per-dimension `total_spend`**, and
   `recovery_pct = headline_waste / total_spend × 100`, quantized to 2 places. Dimensions can
   cover different subsets of the rows (§1 #3), so the widest one is the best account-level
   spend figure.
7. **`Decimal` fields serialise as JSON strings** (Pydantic v2's default). Kept deliberately:
   rupee values stay exact over the wire. Tests compare with `Decimal(body["..."])`; the
   Stage 4 client parses with `Number()`.
8. **Background execution is verified through `TestClient`'s synchronous task execution**,
   not by calling `execute_run` by hand in the API tests, so those tests cover the real
   wiring (`BackgroundTasks` + `session_scope`). Service tests still call `execute_run(run_id)`
   directly, which is how the failure path gets exercised.
9. **The shared test engine is patched onto `app.core.db`'s module globals** (`bound_engine`
   in `tests/conftest.py`, created by Stage 2) rather than through `dependency_overrides`,
   because the background task opens its own session. Stage 3 adds no second engine and no
   second `db` fixture; it extends `api_env` and appends to `tests/api/helpers.py`, per
   `INTERFACES.md` §"Test-fixture contract".
10. **`execute_run` reads `run.config_snapshot`, never the live client config**, and a test
    mutates the client's overrides mid-flight to prove it (`docs/PLAN.md` §3 and §8 "wrong
    numbers mean billing disputes").
11. **Upload bytes are buffered in memory up to `max_upload_mb`** (FastAPI already spools the
    multipart part to disk past 1 MB). Streaming straight into storage is a Stage 8 concern
    and is not worth the complexity at a 20 MB cap.
12. **`UploadOut`/`UploadRejected` live in `app/schemas/uploads.py`; `SegmentOut`,
    `DimensionOut`, `RecommendationOut`, `ReportOut` and `RunOut` live in
    `app/schemas/reports.py`.** The field lists are `INTERFACES.md` verbatim; only the file
    split, which that document leaves implicit, is decided here.
13. **The `app.models.Recommendation` table is imported as `RecommendationRow`** wherever
    `app.pipeline.optimizer.Recommendation` is also in scope.
14. **`POST /api/analyze/{upload_id}` on an upload with `status == "failed"` returns 422**,
    not 409 or 400: the request is well-formed but the referenced data is unusable.

## Self-review notes

- **Spec coverage.** `docs/PLAN.md` §6 Stage 3, line by line: streaming upload with a size
  limit → Task 3 (`_read_limited` plus the 413 test); SHA-256 duplicate detection → Task 2
  and Task 3 (409, plus the cross-client non-duplicate case); loader validation with a
  row-level error response → Tasks 2 and 3 (the 422 body); storage interface → Task 1;
  template CSV → Task 2 (`template_csv`) and Task 3 (download, round-trip, re-upload);
  background analysis writing `analysis_runs`, `waste_reports`, `segment_metrics` and
  `recommendations` → Tasks 4 and 5; "correct stored numbers" plus isolation → Task 7.
  §5 API surface: `POST /api/uploads`, `GET /api/uploads`, `GET /api/uploads/{id}`,
  `GET /api/uploads/template.csv`, `POST /api/analyze/{upload_id}` (202 + run id),
  `GET /api/runs/{id}`, `GET /api/reports/latest`, `GET /api/reports/{run_id}` — all mounted
  in Tasks 3 and 7. (`GET /api/reports/{run_id}/pdf` is Stage 5 and deliberately absent.)
  §4 tenant isolation: no endpoint accepts a `client_id`; every service filters on it; 404 on
  cross-tenant; clients see approved runs only — Tasks 2, 4, 6, 7. §1 #3 partial dimensions: a
  `WasteReport` row is written for all three `DIMENSIONS` regardless of coverage. §1 #6:
  `to_money` is the single float→`Decimal` boundary, tested for `ROUND_HALF_UP`. §1 #9: the
  storage interface, Task 1.
- **Placeholder scan.** No TBD/TODO anywhere; every code step carries the full file or the
  exact replacement block; every test step carries real assertions against real expected
  values; every command has an expected output.
- **Type consistency.** `create_upload`/`list_uploads`/`get_upload`/`template_csv`,
  `create_run`/`execute_run`/`get_run`/`get_report`/`latest_report`,
  `StorageBackend.save`/`read`/`delete`, `get_storage`, `to_money`, and every schema field
  name match `INTERFACES.md` exactly and are used identically in Tasks 3–7.
  `LoadResult.df/errors/warnings/row_count/date_range/ok`,
  `DimensionResult.{dimension,benchmark_cpa,total_spend,total_wasted_spend,segments}` and
  `SegmentMetrics.{segment,spend,impressions,clicks,conversions,revenue,cpa,is_significant,
  is_flagged,wasted_spend}` match the Stage 1 plan. `RecommendationRow` is the aliased model
  in Tasks 5 and 6 alike; `SessionDep` is redefined per router file (they are independent
  modules) and always means `Annotated[Session, Depends(get_session)]`.
- **Deliberate non-goals.** No admin approval endpoint (Stage 6), no PDF (Stage 5), no
  Meta/Google export header mapping (mentioned in §1 #3 as "also planned for Stage 3" but not
  part of §6's "Done when" — the template CSV covers the MVP need, and column mapping is
  listed as a later mitigation in §8), and no Supabase storage backend (Stage 8).
