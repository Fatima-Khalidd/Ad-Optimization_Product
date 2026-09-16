# Stage 8 — Hardening & Deploy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Take the feature-complete app from Stages 0–7 and make it safe to run in public — error reporting, security headers, a locked-down CORS policy, a request-size cap, structured logs, Supabase Storage for files, production connection pooling, deploy files for Railway and Vercel, a seeded demo account, the three policy pages, and a README smoke-test checklist the owner can follow click by click.

**Architecture:** All new backend cross-cutting HTTP behaviour lives in one new module, `backend/app/core/middleware.py`, and is wired up in `create_app()` in a fixed, documented order; nothing else in the app changes shape. The only new service code is a second implementation of Stage 3's existing `StorageBackend` protocol (`SupabaseStorage`), selected by a Settings value, so no caller changes. Everything that is code is written and tested locally against SQLite and `httpx.MockTransport`; everything that is a cloud-console click is written up as an **owner checkpoint** in the README with an exact step list, because the owner — not the implementer — holds the accounts.

**Tech Stack:** Python 3.11, FastAPI 0.141, Starlette middleware, SQLAlchemy 2.0.53, sentry-sdk 2.69.2, httpx 0.28.1, pytest 9 · Node 24, Next.js 16.3.5, @sentry/nextjs 10.74.0, Vitest 5.0.1 + Testing Library · Railway (backend), Vercel (frontend), Supabase Postgres + Storage (Mumbai `ap-south-1`), Sentry.

**Spec:** `docs/PLAN.md` (§6 "Stage 8", §0 "Your machine", §7 decision #3 "Database", §8 "Risks to watch"; §9 "After the MVP: automatic payments" is explicitly **out of scope**) and `docs/superpowers/plans/INTERFACES.md` (the cross-stage contract — its "Stage 8" block is authoritative for every new name used below).

**Additions to `INTERFACES.md`** (declared here as that document requires; nothing existing is renamed): `StorageError(RuntimeError)` in `app/services/storage.py` (Task 6, written back into `INTERFACES.md` in Task 6 Step 8); `CorsMisconfiguredError(RuntimeError)` and `_init_sentry()` in `app/main.py` (Tasks 3–4); the concrete contents of `app/core/middleware.py` — `REQUEST_ID_HEADER`, `request_id_var`, `JsonFormatter`, `configure_logging()`, `SecurityHeadersMiddleware`, `RequestContextMiddleware`, `RequestSizeLimitMiddleware` (Tasks 2–3); the deploy files `backend/runtime.txt` and `backend/railway.toml` (Task 8, the contract's "railway.toml or render.yaml" choice); `scripts.seed_demo.main() -> int` plus `backend/scripts/__init__.py` (Task 9); and `frontend/instrumentation-client.ts`, `PolicyLayout`, `Footer` (Tasks 5, 10).

## Global Constraints

- **Stages 0–7 are complete and merged** before this plan starts. Every name this plan consumes (`create_app`, `Settings`, `get_settings`, `make_engine`, `StorageBackend`, `LocalStorage`, `get_storage`, `create_admin`, `signup_client`, `create_upload`, `create_run`, `execute_run`, `approve_run`, `write_sample_csv`) is defined in `docs/superpowers/plans/INTERFACES.md` and is used **verbatim**.
- **Secrets only ever come from environment variables.** No DSN, database URL, service key or password is written into a tracked file. `.env`, `.env.production` and `.env.local` stay ignored by git (`docs/PLAN.md` §7).
- **HTTPS is enforced by the hosts.** Railway and Vercel both terminate TLS and redirect HTTP; the app adds HSTS but never performs its own redirect.
- **CORS is locked to the frontend origin.** `cors_origins` is an explicit list; `"*"` is refused at startup when `env == "prod"` (§6 Stage 8).
- **The Supabase service-role key is backend-only.** Never in a `NEXT_PUBLIC_*` variable, never sent to the browser, never logged (`docs/PLAN.md` §7 "Supabase notes").
- **Backups are on**: prod is a Supabase **Pro** project in Mumbai (`ap-south-1`) with daily backups; dev is a **Free** project. Point-in-time recovery stays off until there are paying clients (§7 #3).
- **Owner checkpoints:** the owner performs every cloud-console action (creating projects, pasting env vars, pressing Deploy). The implementer writes and tests everything that is code and writes the exact step list the owner follows. An implementer must never invent, guess or commit a real credential.
- **Placeholders are forbidden** everywhere except legal copy: `TODO-OWNER` markers are allowed **only** inside the `/terms`, `/privacy` and `/refunds` page copy, and as angle-bracket values inside `.env.*.example` files (`INTERFACES.md`, Stage 8).
- Python target **3.11**; Node **24**. Ruff `line-length = 100`, rules `E,F,I,B,UP` (`backend/pyproject.toml`).
- Owner's machine is **Windows without Docker** (`docs/PLAN.md` §0). Backend commands run through Git Bash as `backend/.venv/Scripts/python`, `.../ruff`, `.../alembic`.
- Every commit ends with the attribution trailer, passed as a **second** `-m`:
  `git commit -m "<subject>" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"`
- No queue, no Celery, no Docker (§0). No payment gateway — that is `docs/PLAN.md` §9, after the MVP.

---

## File Structure

```
backend/
├── requirements.txt                      # MODIFY: + sentry-sdk[fastapi], httpx (moves out of dev)
├── requirements-dev.txt                  # MODIFY: httpx removed (now a runtime dep)
├── runtime.txt                           # NEW: python-3.11.9 (host Python pin)
├── Procfile                              # NEW: migrate-then-serve
├── railway.toml                          # NEW: Railway build/deploy/healthcheck
├── .env.production.example               # NEW: every prod env var, no real values
├── app/
│   ├── main.py                           # MODIFY: Sentry init, logging, middleware stack, CORS
│   ├── core/
│   │   ├── settings.py                   # MODIFY: Stage 8 fields + cookie_secure guard
│   │   ├── db.py                         # MODIFY: make_engine() pool tuning for Postgres
│   │   └── middleware.py                 # NEW: headers, size cap, request id, JSON logging
│   └── services/
│       └── storage.py                    # MODIFY: + StorageError, SupabaseStorage, get_storage switch
├── scripts/
│   ├── __init__.py                       # NEW: makes scripts importable as a package
│   └── seed_demo.py                      # NEW: idempotent demo client + approved run
└── tests/
    ├── test_settings_stage8.py           # NEW
    ├── test_middleware.py                # NEW
    ├── test_cors.py                      # NEW
    ├── test_sentry_init.py               # NEW
    ├── test_engine_pool.py               # NEW
    ├── test_storage_supabase.py          # NEW
    └── test_seed_demo.py                 # NEW

frontend/
├── package.json                          # MODIFY: + @sentry/nextjs, vitest stack, "test" script
├── next.config.ts                        # MODIFY: withSentryConfig when a DSN is present
├── vitest.config.ts                      # NEW (keep Stage 4's if it exists)
├── vitest.setup.ts                       # NEW (keep Stage 4's if it exists)
├── instrumentation.ts                    # NEW: server/edge Sentry register + onRequestError
├── instrumentation-client.ts             # NEW: one-line bridge to sentry.client.config
├── sentry.client.config.ts               # NEW: browser init, guarded by NEXT_PUBLIC_SENTRY_DSN
├── sentry.server.config.ts               # NEW: node init, guarded by NEXT_PUBLIC_SENTRY_DSN
├── .env.production.example               # NEW
└── src/
    ├── app/
    │   ├── layout.tsx                    # MODIFY: render <Footer />
    │   ├── terms/page.tsx                # NEW (TODO-OWNER legal copy)
    │   ├── privacy/page.tsx              # NEW (TODO-OWNER legal copy)
    │   ├── refunds/page.tsx              # NEW (TODO-OWNER legal copy)
    │   └── dashboard/billing/page.tsx    # MODIFY: link the three policies
    └── components/ui/
        ├── PolicyLayout.tsx              # NEW: shared shell for the three pages
        ├── PolicyPages.test.tsx          # NEW
        ├── Footer.tsx                    # NEW
        └── Footer.test.tsx               # NEW

.github/workflows/ci.yml                  # MODIFY: npm test + pytest coverage flag
.gitignore                                # MODIFY: .env.production, .sentryclirc
README.md                                 # MODIFY: Run locally, Deploy, Smoke-test checklist
```

**Why there is no `frontend/vercel.json`:** Vercel auto-detects Next.js and needs no config file. This app's only routing rule is the `/api/*` rewrite, and that already lives in `next.config.ts`, where it also works under local `next dev`. Duplicating it in `vercel.json` would create two sources of truth that silently disagree. Do not create the file.

---

### Task 1: Stage 8 settings and the cookie hardening check

**Files:**
- Modify: `backend/app/core/settings.py`
- Modify: `backend/.env.example`
- Test: `backend/tests/test_settings_stage8.py`

**Interfaces:**
- Consumes: `Settings` / `get_settings()` from `backend/app/core/settings.py` (Stage 0), already carrying `env`, `database_url`, `secret_key` (Stage 0), `access_token_minutes`, `refresh_token_days`, `cookie_secure` (Stage 2), `storage_backend`, `storage_root`, `max_upload_mb` (Stage 3), `payment_provider` (Stage 7).
- Produces, on `Settings`:
  - `sentry_dsn: str | None = None`
  - `cors_origins: list[str] = ["http://localhost:3000"]` — read from the **comma-separated** env var `CORS_ORIGINS`
  - `max_request_mb: int = 25`
  - `supabase_url: str | None = None`
  - `supabase_service_key: str | None = None`
  - `storage_bucket: str = "ad-optimizer"`
  - `cookie_secure: bool` — `True` exactly when `env == "prod"`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_settings_stage8.py`:

```python
from app.core.settings import Settings

BASE = {"database_url": "sqlite+pysqlite:///:memory:", "secret_key": "x" * 32}


def test_stage8_defaults_are_safe():
    settings = Settings(env="dev", **BASE)
    assert settings.sentry_dsn is None
    assert settings.cors_origins == ["http://localhost:3000"]
    assert settings.max_request_mb == 25
    assert settings.supabase_url is None
    assert settings.supabase_service_key is None
    assert settings.storage_bucket == "ad-optimizer"


def test_cors_origins_parses_a_comma_separated_env_var(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "https://app.example.com, https://www.example.com/")
    settings = Settings(env="prod", **BASE)
    assert settings.cors_origins == ["https://app.example.com", "https://www.example.com"]


def test_cors_origins_accepts_a_single_origin(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "https://app.example.com")
    assert Settings(env="prod", **BASE).cors_origins == ["https://app.example.com"]


def test_cors_origins_ignores_blank_entries(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "https://a.example.com,,  ,https://b.example.com")
    settings = Settings(env="prod", **BASE)
    assert settings.cors_origins == ["https://a.example.com", "https://b.example.com"]


def test_cookie_secure_is_true_in_prod():
    assert Settings(env="prod", **BASE).cookie_secure is True


def test_cookie_secure_is_false_outside_prod():
    assert Settings(env="dev", **BASE).cookie_secure is False
    assert Settings(env="test", **BASE).cookie_secure is False


def test_supabase_values_come_from_the_environment(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://abcdefgh.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "service-role-key")
    monkeypatch.setenv("STORAGE_BUCKET", "ad-optimizer-prod")
    settings = Settings(env="prod", **BASE)
    assert settings.supabase_url == "https://abcdefgh.supabase.co"
    assert settings.supabase_service_key == "service-role-key"
    assert settings.storage_bucket == "ad-optimizer-prod"
```

- [ ] **Step 2: Run them and watch them fail**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_settings_stage8.py -v`
Expected: FAIL — `AttributeError: 'Settings' object has no attribute 'sentry_dsn'`. (The two `cookie_secure` tests may already pass, because Stage 2 defined that field; that is fine.)

- [ ] **Step 3: Add the Stage 8 fields to `Settings`**

In `backend/app/core/settings.py`, change the imports at the top of the file to:

```python
from functools import lru_cache
from typing import Annotated, Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict
```

Then, **leaving every Stage 0/2/3/7 field exactly where it is**, append this block as the last group inside `class Settings`:

```python
    # --- Stage 8: hardening & deploy -------------------------------------
    sentry_dsn: str | None = None
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:3000"]
    max_request_mb: int = 25
    supabase_url: str | None = None
    supabase_service_key: str | None = None
    storage_bucket: str = "ad-optimizer"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_cors_origins(cls, value: object) -> object:
        """CORS_ORIGINS is a comma-separated list, not JSON. Trailing slashes are dropped
        because browsers send `Origin` without one and Starlette compares exact strings."""
        if isinstance(value, str):
            return [part.strip().rstrip("/") for part in value.split(",") if part.strip()]
        return value
```

`NoDecode` is what stops pydantic-settings from JSON-decoding the env value before the validator runs. Without it, `CORS_ORIGINS=https://a,https://b` raises `SettingsError: error parsing value for field "cors_origins"`.

- [ ] **Step 4: Add `cookie_secure` only if Stage 2 did not**

Run: `cd backend && grep -n "cookie_secure" app/core/settings.py`

- If it prints a line, Stage 2 already defined it — do nothing here.
- If it prints nothing, change the pydantic import to `from pydantic import computed_field, field_validator` and add this to `class Settings`, directly after the validator:

```python
    @computed_field  # type: ignore[prop-decorator]
    @property
    def cookie_secure(self) -> bool:
        """Auth cookies get `Secure` in production only, so local http:// dev still works."""
        return self.env == "prod"
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_settings_stage8.py -v`
Expected: PASS — `7 passed`.

- [ ] **Step 6: Document the new variables in `backend/.env.example`**

Append to `backend/.env.example`:

```
# --- Stage 8 ---------------------------------------------------------------
# Comma-separated list of browser origins allowed to call this API.
CORS_ORIGINS=http://localhost:3000

# Largest request body the API accepts, in MB. Uploads have their own MAX_UPLOAD_MB cap.
MAX_REQUEST_MB=25

# Leave empty in dev: Sentry stays off when there is no DSN.
SENTRY_DSN=

# File storage. "local" writes under STORAGE_ROOT; "supabase" uses the private bucket below.
STORAGE_BACKEND=local
STORAGE_BUCKET=ad-optimizer
# Supabase -> Project Settings -> API. The service_role key is BACKEND ONLY.
SUPABASE_URL=
SUPABASE_SERVICE_KEY=
```

- [ ] **Step 7: Lint and commit**

Run: `cd backend && .venv/Scripts/ruff check . && .venv/Scripts/ruff format --check .`
Expected: `All checks passed!` followed by `N files already formatted`.

```bash
git add backend/app/core/settings.py backend/.env.example backend/tests/test_settings_stage8.py
git commit -m "feat(core): add Stage 8 settings for Sentry, CORS, request size and Supabase Storage" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 2: Security headers, request IDs and structured JSON logging

**Files:**
- Create: `backend/app/core/middleware.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_middleware.py`

**Interfaces:**
- Consumes: `get_settings()` and the Stage 8 fields (Task 1); `create_app()` from `backend/app/main.py` (Stage 0); the `client` fixture from `backend/tests/conftest.py` (Stage 0).
- Produces, from `app.core.middleware`:
  - `REQUEST_ID_HEADER: str = "X-Request-ID"`
  - `request_id_var: ContextVar[str]` — the current request id, `"-"` outside a request
  - `JsonFormatter(logging.Formatter)` — one JSON object per line
  - `configure_logging(level: str = "INFO") -> None` — installs `JsonFormatter` on the root logger and makes uvicorn's loggers propagate into it
  - `SecurityHeadersMiddleware(app, *, hsts: bool = False)`
  - `RequestContextMiddleware(app)` — echoes or generates `X-Request-ID`, logs one structured access line per request
- (`RequestSizeLimitMiddleware` is added in Task 3, into the same module.)

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_middleware.py`:

```python
import json
import logging

import pytest
from fastapi.testclient import TestClient

from app.core.middleware import REQUEST_ID_HEADER, JsonFormatter, request_id_var
from app.core.settings import get_settings
from app.main import create_app


@pytest.fixture
def build_app(monkeypatch):
    """Build a fresh app with specific env vars, then restore the settings cache."""

    def build(**env: str):
        for key, value in env.items():
            monkeypatch.setenv(key, value)
        get_settings.cache_clear()
        return create_app()

    yield build
    get_settings.cache_clear()


def test_security_headers_are_on_every_response(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    policy = response.headers["Permissions-Policy"]
    assert "camera=()" in policy
    assert "microphone=()" in policy
    assert "geolocation=()" in policy


def test_hsts_is_absent_outside_prod(client):
    assert "Strict-Transport-Security" not in client.get("/api/health").headers


def test_hsts_is_present_in_prod(build_app):
    app = build_app(ENV="prod", SECRET_KEY="p" * 32, CORS_ORIGINS="https://app.example.com")
    with TestClient(app) as prod_client:
        header = prod_client.get("/api/health").headers["Strict-Transport-Security"]
    assert header == "max-age=31536000; includeSubDomains"


def test_request_id_is_generated_when_the_client_sends_none(client):
    value = client.get("/api/health").headers[REQUEST_ID_HEADER]
    assert len(value) == 32
    int(value, 16)  # raises ValueError if it is not hex


def test_request_id_is_echoed_when_the_client_sends_one(client):
    response = client.get("/api/health", headers={REQUEST_ID_HEADER: "abc-123_XYZ"})
    assert response.headers[REQUEST_ID_HEADER] == "abc-123_XYZ"


def test_a_hostile_request_id_is_replaced_not_echoed(client):
    hostile = "not a valid id " + "x" * 200
    response = client.get("/api/health", headers={REQUEST_ID_HEADER: hostile})
    assert response.headers[REQUEST_ID_HEADER] != hostile
    assert len(response.headers[REQUEST_ID_HEADER]) == 32


def test_every_request_gets_its_own_id(client):
    first = client.get("/api/health").headers[REQUEST_ID_HEADER]
    second = client.get("/api/health").headers[REQUEST_ID_HEADER]
    assert first != second


def test_json_formatter_emits_one_parseable_object():
    record = logging.LogRecord(
        name="app.access",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="request",
        args=(),
        exc_info=None,
    )
    record.method = "GET"
    record.path = "/api/health"
    record.status = 200
    record.duration_ms = 1.25
    record.request_id = "deadbeef"

    payload = json.loads(JsonFormatter().format(record))

    assert payload["level"] == "INFO"
    assert payload["logger"] == "app.access"
    assert payload["msg"] == "request"
    assert payload["method"] == "GET"
    assert payload["path"] == "/api/health"
    assert payload["status"] == 200
    assert payload["duration_ms"] == 1.25
    assert payload["request_id"] == "deadbeef"
    assert payload["ts"].endswith("Z")


def test_json_formatter_never_emits_a_newline_inside_a_record():
    record = logging.LogRecord(
        name="app",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg="line one\nline two",
        args=(),
        exc_info=None,
    )
    assert "\n" not in JsonFormatter().format(record)


def test_request_id_var_defaults_outside_a_request():
    assert request_id_var.get() == "-"


def test_access_line_is_logged_with_the_request_id(client, caplog):
    with caplog.at_level(logging.INFO, logger="app.access"):
        response = client.get("/api/health")
    record = next(r for r in caplog.records if r.name == "app.access")
    assert record.request_id == response.headers[REQUEST_ID_HEADER]
    assert record.status == 200
    assert record.path == "/api/health"
```

- [ ] **Step 2: Run them and watch them fail**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_middleware.py -v`
Expected: FAIL — collection error, `ModuleNotFoundError: No module named 'app.core.middleware'`.

- [ ] **Step 3: Write `app/core/middleware.py`**

Create `backend/app/core/middleware.py`:

```python
"""Cross-cutting HTTP concerns: security headers, request ids and structured logging.

Nothing here knows about the product. Each middleware does one thing, so `create_app()`
composes them in a deliberate order (see `app/main.py`).
"""

from __future__ import annotations

import json
import logging
import re
import sys
import time
import uuid
from contextvars import ContextVar
from datetime import UTC, datetime

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

REQUEST_ID_HEADER = "X-Request-ID"
SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")

PERMISSIONS_POLICY = (
    "accelerometer=(), camera=(), geolocation=(), gyroscope=(), "
    "microphone=(), payment=(), usb=()"
)
HSTS_VALUE = "max-age=31536000; includeSubDomains"

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")
access_logger = logging.getLogger("app.access")

_EXTRA_FIELDS = ("method", "path", "status", "duration_ms")


class JsonFormatter(logging.Formatter):
    """One JSON object per line, so Railway's log viewer can filter on the fields."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC)
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "request_id": getattr(record, "request_id", request_id_var.get()),
        }
        for field in _EXTRA_FIELDS:
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, separators=(",", ":"), default=str)


def configure_logging(level: str = "INFO") -> None:
    """Send every log line to stdout as JSON. Safe to call more than once."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    for existing in list(root.handlers):
        root.removeHandler(existing)
    root.addHandler(handler)
    root.setLevel(level)

    # uvicorn installs its own colourised handlers; drop them and let ours format instead.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers = []
        uvicorn_logger.propagate = True


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Headers every response gets. `hsts` is on only behind real TLS (prod)."""

    def __init__(self, app: ASGIApp, *, hsts: bool = False) -> None:
        super().__init__(app)
        self.hsts = hsts

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", PERMISSIONS_POLICY)
        if self.hsts:
            response.headers.setdefault("Strict-Transport-Security", HSTS_VALUE)
        return response


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Give every request an id, echo it back, and log one structured access line."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        incoming = request.headers.get(REQUEST_ID_HEADER)
        request_id = incoming if incoming and SAFE_REQUEST_ID.match(incoming) else uuid.uuid4().hex
        token = request_id_var.set(request_id)
        request.state.request_id = request_id
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            access_logger.exception(
                "request failed",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                    "request_id": request_id,
                },
            )
            raise
        finally:
            request_id_var.reset(token)

        response.headers[REQUEST_ID_HEADER] = request_id
        access_logger.info(
            "request",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                "request_id": request_id,
            },
        )
        return response
```

Why an allowlist regex on the incoming id: an unchecked header goes straight into a log file and back out in a response header. `SAFE_REQUEST_ID` rules out newlines (log forging) and unbounded length.

- [ ] **Step 4: Wire both middlewares into `create_app()`**

In `backend/app/main.py`, add the imports and the two `add_middleware` calls. Keep every router include and the slowapi limiter that Stages 2–7 added exactly where they are:

```python
from fastapi import FastAPI

from app.core.middleware import (
    RequestContextMiddleware,
    SecurityHeadersMiddleware,
    configure_logging,
)
from app.core.settings import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging()
    application = FastAPI(title="Ad Spend Optimization API", version="0.1.0")

    # Starlette runs middleware in reverse registration order: the LAST one added is the
    # OUTERMOST. Registering the context middleware last means the request id wraps
    # everything, including responses produced by middleware registered earlier.
    application.add_middleware(SecurityHeadersMiddleware, hsts=settings.env == "prod")
    application.add_middleware(RequestContextMiddleware)

    @application.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "env": settings.env}

    # ... Stage 2-7 router includes and the slowapi limiter stay exactly as they are ...

    return application


app = create_app()
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_middleware.py -v`
Expected: PASS — `11 passed`.

- [ ] **Step 6: Run the whole suite to prove nothing else broke**

Run: `cd backend && .venv/Scripts/python -m pytest`
Expected: all pass. If a Stage 2–7 test asserted an exact set of response headers, widen that assertion to check only the headers it cares about — never delete a security header to make an old test pass.

- [ ] **Step 7: Lint and commit**

Run: `cd backend && .venv/Scripts/ruff check . && .venv/Scripts/ruff format --check .`
Expected: `All checks passed!`

```bash
git add backend/app/core/middleware.py backend/app/main.py backend/tests/test_middleware.py
git commit -m "feat(core): security headers, request ids and JSON access logging" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 3: Request-size cap (413) and CORS locked to the frontend origin

**Files:**
- Modify: `backend/app/core/middleware.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_middleware.py` (append)
- Test: `backend/tests/test_cors.py`

**Interfaces:**
- Consumes: `Settings.max_request_mb`, `Settings.cors_origins`, `Settings.env` (Task 1); `SecurityHeadersMiddleware`, `RequestContextMiddleware`, `REQUEST_ID_HEADER` (Task 2).
- Produces:
  - `app.core.middleware.RequestSizeLimitMiddleware(app, *, max_bytes: int)` — replies `413 {"detail": "request body too large"}` when `Content-Length` exceeds `max_bytes`, and `400 {"detail": "invalid Content-Length"}` when the header is not an integer.
  - `app.main.CorsMisconfiguredError(RuntimeError)` — raised by `create_app()` when `env == "prod"` and `cors_origins` is empty or contains `"*"`.

Stage 3's upload endpoint already caps the **uploaded file** at `max_upload_mb` (20 MB) after the multipart body is parsed. This middleware is the coarser, earlier guard on the **whole request** (`max_request_mb`, 25 MB), applied before any body is read, so a hostile 2 GB POST is rejected on its headers alone. The two numbers are deliberately different and `max_request_mb` must stay the larger, so a legal 20 MB upload plus multipart overhead still fits.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_middleware.py`:

```python
def test_body_within_the_cap_is_accepted(build_app):
    app = build_app(MAX_REQUEST_MB="1")
    with TestClient(app) as sized_client:
        response = sized_client.post("/api/health", content=b"0" * 1024)
    # /api/health has no POST handler, so anything other than 413 proves we got through.
    assert response.status_code == 405


def test_body_over_the_cap_is_rejected_with_413(build_app):
    app = build_app(MAX_REQUEST_MB="1")
    with TestClient(app) as sized_client:
        response = sized_client.post("/api/health", content=b"0" * (2 * 1024 * 1024))
    assert response.status_code == 413
    assert response.json() == {"detail": "request body too large"}


def test_413_still_carries_the_security_headers_and_a_request_id(build_app):
    app = build_app(MAX_REQUEST_MB="1")
    with TestClient(app) as sized_client:
        response = sized_client.post("/api/health", content=b"0" * (2 * 1024 * 1024))
    assert response.status_code == 413
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert len(response.headers[REQUEST_ID_HEADER]) == 32


def test_a_non_numeric_content_length_is_rejected_with_400(build_app):
    app = build_app(MAX_REQUEST_MB="1")
    with TestClient(app) as sized_client:
        response = sized_client.post(
            "/api/health", content=b"hi", headers={"Content-Length": "not-a-number"}
        )
    assert response.status_code == 400
    assert response.json() == {"detail": "invalid Content-Length"}
```

Create `backend/tests/test_cors.py`:

```python
import pytest
from fastapi.testclient import TestClient

from app.core.settings import get_settings
from app.main import CorsMisconfiguredError, create_app

ALLOWED = "https://app.example.com"


@pytest.fixture
def cors_client(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", f"{ALLOWED},https://staging.example.com")
    get_settings.cache_clear()
    with TestClient(create_app()) as c:
        yield c
    get_settings.cache_clear()


def test_allowed_origin_gets_the_cors_header(cors_client):
    response = cors_client.get("/api/health", headers={"Origin": ALLOWED})
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == ALLOWED
    assert response.headers["access-control-allow-credentials"] == "true"


def test_second_allowed_origin_also_works(cors_client):
    response = cors_client.get("/api/health", headers={"Origin": "https://staging.example.com"})
    assert response.headers["access-control-allow-origin"] == "https://staging.example.com"


def test_disallowed_origin_gets_no_cors_header(cors_client):
    response = cors_client.get("/api/health", headers={"Origin": "https://evil.example.com"})
    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers


def test_preflight_from_a_disallowed_origin_is_not_approved(cors_client):
    response = cors_client.options(
        "/api/health",
        headers={
            "Origin": "https://evil.example.com",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert "access-control-allow-origin" not in response.headers


def test_request_id_header_is_exposed_to_the_browser(cors_client):
    response = cors_client.get("/api/health", headers={"Origin": ALLOWED})
    assert "X-Request-ID" in response.headers["access-control-expose-headers"]


def test_wildcard_cors_is_refused_in_prod(monkeypatch):
    monkeypatch.setenv("ENV", "prod")
    monkeypatch.setenv("SECRET_KEY", "p" * 32)
    monkeypatch.setenv("CORS_ORIGINS", "*")
    get_settings.cache_clear()
    with pytest.raises(CorsMisconfiguredError):
        create_app()
    get_settings.cache_clear()


def test_empty_cors_list_is_refused_in_prod(monkeypatch):
    monkeypatch.setenv("ENV", "prod")
    monkeypatch.setenv("SECRET_KEY", "p" * 32)
    monkeypatch.setenv("CORS_ORIGINS", " , ")
    get_settings.cache_clear()
    with pytest.raises(CorsMisconfiguredError):
        create_app()
    get_settings.cache_clear()
```

- [ ] **Step 2: Run them and watch them fail**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_cors.py tests/test_middleware.py -v`
Expected: FAIL — `ImportError: cannot import name 'CorsMisconfiguredError' from 'app.main'` for `test_cors.py`, and the four new size tests returning `405` where `413` was expected.

- [ ] **Step 3: Add `RequestSizeLimitMiddleware`**

In `backend/app/core/middleware.py`, change the responses import to `from starlette.responses import JSONResponse, Response` and append:

```python
class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """Reject oversized requests on their headers, before any body is read.

    This is the blunt outer guard. The upload endpoint keeps its own, smaller
    `max_upload_mb` cap on the file itself (Stage 3).
    """

    def __init__(self, app: ASGIApp, *, max_bytes: int) -> None:
        super().__init__(app)
        self.max_bytes = max_bytes

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        raw_length = request.headers.get("content-length")
        if raw_length is not None:
            try:
                length = int(raw_length)
            except ValueError:
                return JSONResponse({"detail": "invalid Content-Length"}, status_code=400)
            if length > self.max_bytes:
                return JSONResponse({"detail": "request body too large"}, status_code=413)
        return await call_next(request)
```

- [ ] **Step 4: Wire the size cap and CORS into `create_app()`**

In `backend/app/main.py`, replace the middleware block from Task 2 with the full stack and add the CORS guard:

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.middleware import (
    REQUEST_ID_HEADER,
    RequestContextMiddleware,
    RequestSizeLimitMiddleware,
    SecurityHeadersMiddleware,
    configure_logging,
)
from app.core.settings import Settings, get_settings


class CorsMisconfiguredError(RuntimeError):
    """Raised at startup rather than shipping an API any website can call with cookies."""


def _check_cors(settings: Settings) -> None:
    if settings.env != "prod":
        return
    if not settings.cors_origins or "*" in settings.cors_origins:
        raise CorsMisconfiguredError(
            "CORS_ORIGINS must list the exact frontend origin(s) in production; "
            f"got {settings.cors_origins!r}"
        )


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging()
    _check_cors(settings)
    application = FastAPI(title="Ad Spend Optimization API", version="0.1.0")

    # Registration order is reversed at runtime, so the stack is, outermost first:
    #   RequestContext -> SecurityHeaders -> CORS -> RequestSizeLimit -> routes
    # Every response, including a 413 and a rejected preflight, therefore carries the
    # security headers and a request id.
    application.add_middleware(
        RequestSizeLimitMiddleware, max_bytes=settings.max_request_mb * 1024 * 1024
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", REQUEST_ID_HEADER],
        expose_headers=[REQUEST_ID_HEADER],
        max_age=600,
    )
    application.add_middleware(SecurityHeadersMiddleware, hsts=settings.env == "prod")
    application.add_middleware(RequestContextMiddleware)

    @application.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "env": settings.env}

    # ... Stage 2-7 router includes and the slowapi limiter stay exactly as they are ...

    return application


app = create_app()
```

`allow_credentials=True` is required because auth is cookie-based (`docs/PLAN.md` §5). That is exactly why `allow_origins` may never be `"*"`: browsers refuse the combination outright, so `_check_cors` turns a silent production outage into a loud startup failure.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_cors.py tests/test_middleware.py -v`
Expected: PASS — `7 passed` in `test_cors.py`, `15 passed` in `test_middleware.py`.

- [ ] **Step 6: Run the whole suite**

Run: `cd backend && .venv/Scripts/python -m pytest`
Expected: all pass.

- [ ] **Step 7: Lint and commit**

Run: `cd backend && .venv/Scripts/ruff check . && .venv/Scripts/ruff format --check .`
Expected: `All checks passed!`

```bash
git add backend/app/core/middleware.py backend/app/main.py backend/tests/test_middleware.py backend/tests/test_cors.py
git commit -m "feat(api): cap request bodies at 413 and lock CORS to the frontend origin" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 4: Sentry on the backend

**Files:**
- Modify: `backend/requirements.txt`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_sentry_init.py`

**Interfaces:**
- Consumes: `Settings.sentry_dsn`, `Settings.env` (Task 1); `create_app()` (Task 3).
- Produces: `app.main._init_sentry(settings: Settings) -> None` — calls `sentry_sdk.init(dsn=..., environment=settings.env, send_default_pii=False, traces_sample_rate=0.0)` exactly when `settings.sentry_dsn` is truthy, and returns immediately otherwise.

- [ ] **Step 1: Pin the current sentry-sdk version**

Run: `cd backend && .venv/Scripts/python -m pip index versions sentry-sdk`
Expected: a first line like `sentry-sdk (2.69.2)`. Use whatever version that command prints. At the time this plan was written it was **2.69.2**; the code below assumes that.

- [ ] **Step 2: Write the failing tests**

Create `backend/tests/test_sentry_init.py`:

```python
import pytest
import sentry_sdk
from fastapi.testclient import TestClient

from app.core.settings import get_settings
from app.main import create_app

FAKE_DSN = "https://publickey@o0.ingest.sentry.io/1"


@pytest.fixture
def captured_init(monkeypatch):
    """Record sentry_sdk.init kwargs instead of opening a real transport."""
    calls: list[dict] = []
    monkeypatch.setattr(sentry_sdk, "init", lambda **kwargs: calls.append(kwargs))
    yield calls
    get_settings.cache_clear()


def test_app_starts_and_serves_without_a_dsn(captured_init, monkeypatch):
    monkeypatch.delenv("SENTRY_DSN", raising=False)
    get_settings.cache_clear()
    with TestClient(create_app()) as c:
        assert c.get("/api/health").json()["status"] == "ok"
    assert captured_init == []


def test_app_starts_and_serves_with_a_dsn(captured_init, monkeypatch):
    monkeypatch.setenv("SENTRY_DSN", FAKE_DSN)
    get_settings.cache_clear()
    with TestClient(create_app()) as c:
        assert c.get("/api/health").json()["status"] == "ok"
    assert len(captured_init) == 1


def test_sentry_is_initialised_with_the_environment_and_no_pii(captured_init, monkeypatch):
    monkeypatch.setenv("SENTRY_DSN", FAKE_DSN)
    get_settings.cache_clear()
    create_app()
    kwargs = captured_init[0]
    assert kwargs["dsn"] == FAKE_DSN
    assert kwargs["environment"] == "test"
    assert kwargs["send_default_pii"] is False


def test_sentry_environment_follows_env(captured_init, monkeypatch):
    monkeypatch.setenv("SENTRY_DSN", FAKE_DSN)
    monkeypatch.setenv("ENV", "prod")
    monkeypatch.setenv("SECRET_KEY", "p" * 32)
    monkeypatch.setenv("CORS_ORIGINS", "https://app.example.com")
    get_settings.cache_clear()
    create_app()
    assert captured_init[0]["environment"] == "prod"


def test_an_empty_dsn_string_counts_as_off(captured_init, monkeypatch):
    monkeypatch.setenv("SENTRY_DSN", "")
    get_settings.cache_clear()
    create_app()
    assert captured_init == []
```

The last test matters in practice: Railway and Vercel both set an unfilled variable to the empty string rather than leaving it unset, so `if not settings.sentry_dsn` (not `is None`) is the correct guard.

- [ ] **Step 3: Run them and watch them fail**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_sentry_init.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'sentry_sdk'`.

- [ ] **Step 4: Add the dependency and install it**

In `backend/requirements.txt`, append:

```
sentry-sdk[fastapi]==2.69.2
```

Run: `cd backend && .venv/Scripts/python -m pip install -r requirements-dev.txt`
Expected: `Successfully installed sentry-sdk-2.69.2` (plus its `urllib3`/`certifi` requirements if they were absent).

- [ ] **Step 5: Initialise Sentry inside `create_app()`**

In `backend/app/main.py`, add `_init_sentry` above `create_app` and call it as the second line of `create_app`:

```python
def _init_sentry(settings: Settings) -> None:
    """Error reporting, off unless a DSN is configured.

    `send_default_pii=False` keeps client email addresses, cookies and request bodies out
    of Sentry — this app handles invoices and payment references (`docs/PLAN.md` §7).
    The FastAPI/Starlette integrations auto-enable; no integration list is needed.
    """
    if not settings.sentry_dsn:
        return
    import sentry_sdk

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.env,
        send_default_pii=False,
        traces_sample_rate=0.0,
    )


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging()
    _init_sentry(settings)
    _check_cors(settings)
    application = FastAPI(title="Ad Spend Optimization API", version="0.1.0")
    # ... the rest of create_app is unchanged ...
```

The `import sentry_sdk` sits inside the function on purpose: module attribute lookup happens at call time, which is what makes the `monkeypatch.setattr(sentry_sdk, "init", ...)` in the tests take effect.

- [ ] **Step 6: Run the tests to verify they pass**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_sentry_init.py -v`
Expected: PASS — `5 passed`.

- [ ] **Step 7: Prove it end to end against a real (but harmless) init**

Run:
```bash
cd backend && SENTRY_DSN="https://publickey@o0.ingest.sentry.io/1" .venv/Scripts/python -c "from app.main import create_app; create_app(); print('app built with sentry on')"
```
Expected: prints `app built with sentry on` and exits 0. Sentry buffers events and never blocks startup, so an unreachable DSN must not raise.

- [ ] **Step 8: Run the whole suite, lint and commit**

Run: `cd backend && .venv/Scripts/python -m pytest && .venv/Scripts/ruff check . && .venv/Scripts/ruff format --check .`
Expected: all pass, `All checks passed!`

```bash
git add backend/requirements.txt backend/app/main.py backend/tests/test_sentry_init.py
git commit -m "feat(obs): report backend errors to Sentry when a DSN is configured" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 5: Sentry on the frontend

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/next.config.ts`
- Create: `frontend/sentry.client.config.ts`
- Create: `frontend/sentry.server.config.ts`
- Create: `frontend/instrumentation.ts`
- Create: `frontend/instrumentation-client.ts`
- Create: `frontend/.env.production.example`
- Modify: `frontend/.env.example`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: the existing `next.config.ts` rewrite (`BACKEND_URL`, Stage 0).
- Produces: `NEXT_PUBLIC_SENTRY_DSN` (browser + server init guard), `NEXT_PUBLIC_SENTRY_ENV` (defaults to `"development"`), and the build-time-only `SENTRY_ORG` / `SENTRY_PROJECT` / `SENTRY_AUTH_TOKEN` used for source-map upload. No other module imports these files — Next.js loads them by filename.

Do **not** run `npx @sentry/wizard`. The wizard rewrites `next.config.ts` in place, adds a `.sentryclirc`, and its output varies by version — which makes the repo unreviewable. Every file it would have produced is written explicitly below.

- [ ] **Step 1: Install the SDK**

Run: `cd frontend && npm install --save-exact @sentry/nextjs@10.74.0`
Expected: `added N packages`. Confirm with `npm ls @sentry/nextjs` → `@sentry/nextjs@10.74.0`.

- [ ] **Step 2: Write the browser config**

Create `frontend/sentry.client.config.ts`:

```ts
import * as Sentry from "@sentry/nextjs";

const dsn = process.env.NEXT_PUBLIC_SENTRY_DSN;

// No DSN (local dev, CI, preview builds) means Sentry stays completely off.
if (dsn) {
  Sentry.init({
    dsn,
    environment: process.env.NEXT_PUBLIC_SENTRY_ENV ?? "development",
    tracesSampleRate: 0,
    sendDefaultPii: false,
    replaysSessionSampleRate: 0,
    replaysOnErrorSampleRate: 0,
  });
}
```

- [ ] **Step 3: Write the server config and the instrumentation hooks**

Create `frontend/sentry.server.config.ts`:

```ts
import * as Sentry from "@sentry/nextjs";

const dsn = process.env.NEXT_PUBLIC_SENTRY_DSN;

if (dsn) {
  Sentry.init({
    dsn,
    environment: process.env.NEXT_PUBLIC_SENTRY_ENV ?? "development",
    tracesSampleRate: 0,
    sendDefaultPii: false,
  });
}
```

Create `frontend/instrumentation.ts`:

```ts
import * as Sentry from "@sentry/nextjs";

export async function register() {
  if (process.env.NEXT_RUNTIME === "nodejs") {
    await import("./sentry.server.config");
  }
}

export const onRequestError = Sentry.captureRequestError;
```

Create `frontend/instrumentation-client.ts`:

```ts
// Next.js 15.3+ loads browser instrumentation from this file. Keeping the real
// configuration in sentry.client.config.ts means there is still one place to edit.
import "./sentry.client.config";
```

The edge runtime is deliberately not wired up: this app has no edge routes or edge middleware, so there is nothing for it to instrument.

- [ ] **Step 4: Wrap `next.config.ts` only when a DSN exists**

Replace `frontend/next.config.ts` with:

```ts
import { withSentryConfig } from "@sentry/nextjs";
import type { NextConfig } from "next";

const backendUrl = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${backendUrl}/api/:path*` }];
  },
};

// Without a DSN the plugin would still try to resolve an org/project at build time,
// so local builds and CI use the bare config.
export default process.env.NEXT_PUBLIC_SENTRY_DSN
  ? withSentryConfig(nextConfig, {
      org: process.env.SENTRY_ORG,
      project: process.env.SENTRY_PROJECT,
      silent: true,
      widenClientFileUpload: true,
      disableLogger: true,
      // Source maps are uploaded to Sentry, then removed from the deployed bundle.
      sourcemaps: { deleteSourcemapsAfterUpload: true },
    })
  : nextConfig;
```

- [ ] **Step 5: Document the variables**

Append to `frontend/.env.example`:

```
# Leave empty locally: Sentry stays off when there is no DSN.
NEXT_PUBLIC_SENTRY_DSN=
NEXT_PUBLIC_SENTRY_ENV=development
```

Create `frontend/.env.production.example`:

```
# Vercel -> Project -> Settings -> Environment Variables. Copy, do not commit real values.

# The public Railway URL of the FastAPI service. Used server-side by next.config.ts rewrites.
BACKEND_URL=https://<railway-service>.up.railway.app

# Sentry (frontend project). The DSN is public by design; the auth token is NOT.
NEXT_PUBLIC_SENTRY_DSN=https://<public-key>@o<org-id>.ingest.sentry.io/<project-id>
NEXT_PUBLIC_SENTRY_ENV=production
SENTRY_ORG=<sentry-org-slug>
SENTRY_PROJECT=<sentry-project-slug>
SENTRY_AUTH_TOKEN=<build-time only, scope project:releases>
```

Add to `.gitignore`, under the `# Secrets & local` block:

```
.env.production
.sentryclirc
```

- [ ] **Step 6: Verify the build succeeds with Sentry off**

Run: `cd frontend && npx tsc --noEmit && npm run lint && npm run build`
Expected: `tsc` prints nothing; lint reports no errors; the build ends with a route table and no Sentry warnings (the plugin is not loaded without a DSN).

- [ ] **Step 7: Verify the build succeeds with Sentry on**

Run: `cd frontend && NEXT_PUBLIC_SENTRY_DSN="https://publickey@o0.ingest.sentry.io/1" npm run build`
Expected: the build completes. A warning that no auth token was found, so source maps were not uploaded, is expected and correct here — `SENTRY_AUTH_TOKEN` only exists on Vercel.

- [ ] **Step 8: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/next.config.ts frontend/sentry.client.config.ts frontend/sentry.server.config.ts frontend/instrumentation.ts frontend/instrumentation-client.ts frontend/.env.example frontend/.env.production.example .gitignore
git commit -m "feat(obs): report frontend errors to Sentry when a DSN is configured" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 6: `SupabaseStorage` and the storage backend switch

**Files:**
- Modify: `backend/requirements.txt`
- Modify: `backend/requirements-dev.txt`
- Modify: `backend/app/services/storage.py`
- Test: `backend/tests/test_storage_supabase.py`

**Interfaces:**
- Consumes: Stage 3's `StorageBackend` Protocol (`save(key: str, data: bytes) -> str`, `read(key: str) -> bytes`, `delete(key: str) -> None`), `LocalStorage(root: Path)` and `get_storage() -> StorageBackend`, all in `backend/app/services/storage.py`; `Settings.storage_backend`, `storage_root`, `supabase_url`, `supabase_service_key`, `storage_bucket` (Task 1).
- Produces, in the same module:
  - `class StorageError(RuntimeError)` — raised on any non-2xx storage response or missing configuration. **This is an addition to `INTERFACES.md`'s Stage 8 block; record it there when this task lands.**
  - `class SupabaseStorage:` with `__init__(self, supabase_url: str, service_key: str, bucket: str, *, transport: httpx.BaseTransport | None = None, timeout: float = 30.0)` and the three `StorageBackend` methods. `save()` returns the **key it was given**, so `read(save(key, data))` round-trips and `AdDataUpload.file_path` keeps holding a key, exactly as with `LocalStorage`.
  - `get_storage()` gains a `"supabase"` branch; `"local"` behaviour is unchanged.

**Endpoint shapes used** (Supabase Storage REST API v1, private bucket, `Authorization: Bearer <service_role key>` + `apikey: <service_role key>`):

| Operation | Method and path |
|---|---|
| upload / overwrite | `POST {supabase_url}/storage/v1/object/{bucket}/{key}` with header `x-upsert: true` |
| download | `GET {supabase_url}/storage/v1/object/{bucket}/{key}` |
| delete | `DELETE {supabase_url}/storage/v1/object/{bucket}/{key}` |

There is also a `/storage/v1/object/authenticated/{bucket}/{key}` download alias. **This implementation uses the plain `/object/{bucket}/{key}` form for all three verbs**, because it is the same path for upload, download and delete, which keeps `_path()` to one line and makes the mock-transport assertions unambiguous. Both forms require the same bearer token; the `authenticated/` alias exists for end-user JWTs, which this backend never holds.

- [ ] **Step 1: Move `httpx` to a runtime dependency**

In `backend/requirements.txt`, append:

```
httpx==0.28.1
```

In `backend/requirements-dev.txt`, delete the line `httpx==0.28.1` (it is now pulled in by `-r requirements.txt`, and TestClient still gets it).

Run: `cd backend && .venv/Scripts/python -m pip install -r requirements-dev.txt`
Expected: `Requirement already satisfied: httpx==0.28.1`.

- [ ] **Step 2: Write the failing tests**

Create `backend/tests/test_storage_supabase.py`:

```python
from pathlib import Path

import httpx
import pytest

from app.core.settings import get_settings
from app.services.storage import LocalStorage, StorageError, SupabaseStorage, get_storage

URL = "https://abcdefgh.supabase.co"
KEY = "service-role-key"
BUCKET = "ad-optimizer"


def _storage(handler) -> SupabaseStorage:
    return SupabaseStorage(URL, KEY, BUCKET, transport=httpx.MockTransport(handler))


def test_save_posts_to_the_object_endpoint_and_returns_the_key():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"Key": f"{BUCKET}/uploads/7/abc.csv"})

    returned = _storage(handler).save("uploads/7/abc.csv", b"date,spend\n")

    assert returned == "uploads/7/abc.csv"
    assert len(seen) == 1
    request = seen[0]
    assert request.method == "POST"
    assert str(request.url) == f"{URL}/storage/v1/object/{BUCKET}/uploads/7/abc.csv"
    assert request.content == b"date,spend\n"


def test_save_sends_the_service_key_and_upsert_and_content_type():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={})

    _storage(handler).save("uploads/7/abc.csv", b"x")

    headers = seen[0].headers
    assert headers["authorization"] == f"Bearer {KEY}"
    assert headers["apikey"] == KEY
    assert headers["x-upsert"] == "true"
    assert headers["content-type"] == "text/csv"


def test_save_guesses_pdf_and_falls_back_to_octet_stream():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={})

    storage = _storage(handler)
    storage.save("reports/7/run-3.pdf", b"%PDF-")
    storage.save("proofs/7/9.bin", b"\x00")

    assert seen[0].headers["content-type"] == "application/pdf"
    assert seen[1].headers["content-type"] == "application/octet-stream"


def test_read_gets_the_object_and_returns_its_bytes():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, content=b"date,spend\n2026-01-01,100\n")

    data = _storage(handler).read("uploads/7/abc.csv")

    assert data == b"date,spend\n2026-01-01,100\n"
    assert seen[0].method == "GET"
    assert str(seen[0].url) == f"{URL}/storage/v1/object/{BUCKET}/uploads/7/abc.csv"


def test_delete_issues_a_delete():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"message": "Successfully deleted"})

    _storage(handler).delete("uploads/7/abc.csv")

    assert seen[0].method == "DELETE"
    assert str(seen[0].url) == f"{URL}/storage/v1/object/{BUCKET}/uploads/7/abc.csv"


def test_delete_tolerates_a_missing_object():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": "not_found"})

    _storage(handler).delete("uploads/7/gone.csv")  # must not raise


def test_a_failed_upload_raises_storage_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"message": "new row violates row-level security"})

    with pytest.raises(StorageError, match="403"):
        _storage(handler).save("uploads/7/abc.csv", b"x")


def test_a_missing_object_raises_storage_error_on_read():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": "not_found"})

    with pytest.raises(StorageError, match="404"):
        _storage(handler).read("uploads/7/missing.csv")


def test_the_service_key_is_never_in_the_error_message():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    with pytest.raises(StorageError) as excinfo:
        _storage(handler).save("uploads/7/abc.csv", b"x")
    assert KEY not in str(excinfo.value)


def test_a_trailing_slash_on_the_supabase_url_does_not_double_up():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={})

    SupabaseStorage(
        f"{URL}/", KEY, BUCKET, transport=httpx.MockTransport(handler)
    ).save("uploads/7/abc.csv", b"x")

    assert str(seen[0].url) == f"{URL}/storage/v1/object/{BUCKET}/uploads/7/abc.csv"


def test_local_storage_round_trips_through_its_save_return_value(tmp_path: Path):
    """The contract SupabaseStorage must match: whatever save() returns, read() accepts."""
    storage = LocalStorage(tmp_path)
    returned = storage.save("uploads/7/abc.csv", b"hello")
    assert storage.read(returned) == b"hello"


def test_get_storage_returns_local_by_default(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path))
    get_settings.cache_clear()
    assert isinstance(get_storage(), LocalStorage)
    get_settings.cache_clear()


def test_get_storage_returns_supabase_when_configured(monkeypatch):
    monkeypatch.setenv("STORAGE_BACKEND", "supabase")
    monkeypatch.setenv("SUPABASE_URL", URL)
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", KEY)
    monkeypatch.setenv("STORAGE_BUCKET", BUCKET)
    get_settings.cache_clear()
    storage = get_storage()
    assert isinstance(storage, SupabaseStorage)
    assert storage.bucket == BUCKET
    get_settings.cache_clear()


def test_get_storage_refuses_supabase_without_credentials(monkeypatch):
    monkeypatch.setenv("STORAGE_BACKEND", "supabase")
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_KEY", raising=False)
    get_settings.cache_clear()
    with pytest.raises(StorageError, match="SUPABASE_URL"):
        get_storage()
    get_settings.cache_clear()
```

If Stage 3's `get_storage()` is `lru_cache`d, add `get_storage.cache_clear()` next to each `get_settings.cache_clear()` in this file.

- [ ] **Step 3: Run them and watch them fail**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_storage_supabase.py -v`
Expected: FAIL — `ImportError: cannot import name 'StorageError' from 'app.services.storage'`.

- [ ] **Step 4: Implement `StorageError` and `SupabaseStorage`**

In `backend/app/services/storage.py`, add `import mimetypes` and `import httpx` to the imports, then append:

```python
class StorageError(RuntimeError):
    """The storage backend refused a request, or is not configured."""


class SupabaseStorage:
    """Supabase Storage (private bucket) over its REST API, using the service-role key.

    Endpoints (Supabase Storage API v1), all under `{supabase_url}/storage/v1`:
        upload    POST   /object/{bucket}/{key}   (header `x-upsert: true` to overwrite)
        download  GET    /object/{bucket}/{key}
        delete    DELETE /object/{bucket}/{key}

    The bucket is private: every one of these calls is authorised by the service-role key,
    which lives only on the backend (`docs/PLAN.md` §7). No public or signed URLs are
    handed out — files are streamed back through our own endpoints, which already enforce
    tenant isolation.
    """

    def __init__(
        self,
        supabase_url: str,
        service_key: str,
        bucket: str,
        *,
        transport: httpx.BaseTransport | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.bucket = bucket
        self._client = httpx.Client(
            base_url=f"{supabase_url.rstrip('/')}/storage/v1",
            headers={"Authorization": f"Bearer {service_key}", "apikey": service_key},
            timeout=timeout,
            transport=transport,
        )

    def _path(self, key: str) -> str:
        return f"/object/{self.bucket}/{key.lstrip('/')}"

    @staticmethod
    def _fail(action: str, response: httpx.Response) -> StorageError:
        # response.text, never the request headers: the service key must never be logged.
        return StorageError(f"supabase {action} failed ({response.status_code}): {response.text}")

    def save(self, key: str, data: bytes) -> str:
        content_type = mimetypes.guess_type(key)[0] or "application/octet-stream"
        response = self._client.post(
            self._path(key),
            content=data,
            headers={"Content-Type": content_type, "x-upsert": "true"},
        )
        if response.status_code >= 400:
            raise self._fail("upload", response)
        return key

    def read(self, key: str) -> bytes:
        response = self._client.get(self._path(key))
        if response.status_code >= 400:
            raise self._fail("download", response)
        return response.content

    def delete(self, key: str) -> None:
        response = self._client.delete(self._path(key))
        if response.status_code >= 400 and response.status_code != 404:
            raise self._fail("delete", response)
```

- [ ] **Step 5: Add the `supabase` branch to `get_storage()`**

Replace the body of the existing `get_storage()` in the same file with:

```python
def get_storage() -> StorageBackend:
    settings = get_settings()
    if settings.storage_backend == "supabase":
        if not settings.supabase_url or not settings.supabase_service_key:
            raise StorageError(
                "STORAGE_BACKEND=supabase needs SUPABASE_URL and SUPABASE_SERVICE_KEY"
            )
        return SupabaseStorage(
            settings.supabase_url, settings.supabase_service_key, settings.storage_bucket
        )
    return LocalStorage(Path(settings.storage_root))
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_storage_supabase.py -v`
Expected: PASS — `14 passed`.

- [ ] **Step 7: Prove the whole upload path still works on local storage**

Run: `cd backend && .venv/Scripts/python -m pytest tests/api -v`
Expected: every Stage 3 and Stage 7 upload/proof test still passes — `get_storage()` defaults to `local` under the test settings, so nothing changed for them.

- [ ] **Step 8: Record the addition, lint and commit**

In `docs/superpowers/plans/INTERFACES.md`, in the "Stage 8 — hardening & deploy" block, change the `SupabaseStorage` line to:

```
SupabaseStorage(StorageBackend) in services/storage.py (Supabase Storage REST, service key, private bucket)
  + StorageError(RuntimeError) raised by SupabaseStorage and by get_storage() on missing config
```

Run: `cd backend && .venv/Scripts/ruff check . && .venv/Scripts/ruff format --check .`
Expected: `All checks passed!`

```bash
git add backend/requirements.txt backend/requirements-dev.txt backend/app/services/storage.py backend/tests/test_storage_supabase.py docs/superpowers/plans/INTERFACES.md
git commit -m "feat(storage): add SupabaseStorage behind the existing StorageBackend protocol" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 7: Connection pool sized for the Supabase session pooler

**Files:**
- Modify: `backend/app/core/db.py`
- Test: `backend/tests/test_engine_pool.py`

**Interfaces:**
- Consumes: `make_engine(url: str) -> Engine` from `backend/app/core/db.py` (Stage 0).
- Produces: unchanged signature. For Postgres URLs the engine is created with `pool_size=5, max_overflow=5, pool_recycle=1800, pool_pre_ping=True`; for SQLite URLs the call is byte-for-byte what it is today (`pool_pre_ping=True`, `connect_args={"check_same_thread": False}`, no pool sizing).

Why: `docs/PLAN.md` §7 #3 says the backend connects "directly or through the session-mode pooler". Supabase's session pooler gives a Free project roughly 15 and a Pro project roughly 60 concurrent client connections, shared across every process. One Railway container with an unbounded default pool can exhaust that on its own. `pool_size=5 + max_overflow=5` caps a container at 10. `pool_recycle=1800` (30 minutes) drops connections before the pooler's idle timeout can close them underneath us, which is the usual cause of `server closed the connection unexpectedly` on the first request after a quiet spell.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_engine_pool.py`:

```python
from app.core.db import make_engine

# A URL is enough: SQLAlchemy does not connect until the first query.
PG_URL = "postgresql+psycopg://user:pass@aws-0-ap-south-1.pooler.supabase.com:5432/postgres"


def test_postgres_engine_is_sized_for_the_supabase_pooler():
    engine = make_engine(PG_URL)
    assert engine.dialect.name == "postgresql"
    assert engine.pool.size() == 5
    assert engine.pool._max_overflow == 5
    assert engine.pool._recycle == 1800
    assert engine.pool._pre_ping is True


def test_sqlite_engine_is_untouched():
    engine = make_engine("sqlite+pysqlite:///:memory:")
    assert engine.dialect.name == "sqlite"
    # -1 is SQLAlchemy's "never recycle" default: no pool tuning leaked onto SQLite.
    assert engine.pool._recycle == -1
    assert not hasattr(engine.pool, "_max_overflow")


def test_sqlite_still_allows_cross_thread_use():
    engine = make_engine("sqlite+pysqlite:///:memory:")
    with engine.connect() as connection:
        assert connection.exec_driver_sql("select 1").scalar() == 1


def test_a_plain_sqlite_file_url_is_also_treated_as_sqlite(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path / 'x.db'}")
    assert engine.dialect.name == "sqlite"
    assert engine.pool._recycle == -1
```

- [ ] **Step 2: Run them and watch them fail**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_engine_pool.py -v`
Expected: FAIL — `test_postgres_engine_is_sized_for_the_supabase_pooler` fails at `assert engine.pool._recycle == 1800` with `assert -1 == 1800`, because today's `make_engine` passes no pool arguments. The three SQLite tests already pass; that is the point — they are the regression guard for Step 3.

- [ ] **Step 3: Split the engine factory by dialect**

Replace `make_engine` in `backend/app/core/db.py` with:

```python
def make_engine(url: str) -> Engine:
    """SQLite keeps the dev/test defaults; Postgres is sized for Supabase's session pooler.

    A Supabase project shares a fixed number of pooler connections across every client, so
    each container is capped at pool_size + max_overflow = 10, and connections are recycled
    every 30 minutes so the pooler never closes one out from under us (`docs/PLAN.md` §7 #3).
    """
    if url.startswith("sqlite"):
        return create_engine(url, pool_pre_ping=True, connect_args={"check_same_thread": False})
    return create_engine(
        url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=5,
        pool_recycle=1800,
    )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_engine_pool.py -v`
Expected: PASS — `4 passed`.

- [ ] **Step 5: Run the whole suite, lint and commit**

Run: `cd backend && .venv/Scripts/python -m pytest && .venv/Scripts/ruff check . && .venv/Scripts/ruff format --check .`
Expected: all pass, `All checks passed!`

```bash
git add backend/app/core/db.py backend/tests/test_engine_pool.py
git commit -m "perf(db): size the Postgres pool for the Supabase session pooler" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 8: Deploy artefacts — Procfile, `railway.toml`, Python pin, production env examples

**Files:**
- Create: `backend/Procfile`
- Create: `backend/railway.toml`
- Create: `backend/runtime.txt`
- Create: `backend/.env.production.example`

**Interfaces:**
- Consumes: `app.main:app` (the module-level app object, Stage 0), `alembic upgrade head` (Stage 0), `GET /api/health` (Stage 0), every Settings name from Tasks 1 and 6.
- Produces: no Python names. Produces the contract the host reads — start command, health check path, Python version, and the full list of production environment variables.

**Host choice — Railway, not Render.** Recorded in Decisions at the end of this plan; the short version is that Railway's start command runs on the same container as the web process, so `alembic upgrade head && uvicorn ...` is a one-liner, while Render needs a separate `preDeployCommand` in a `render.yaml` blueprint. Railway also keeps an ap-south (Singapore/Mumbai-adjacent) region close to the Supabase Mumbai project. Do not create `render.yaml`.

- [ ] **Step 1: Write the Procfile**

Create `backend/Procfile` (no trailing newline issues — one line, ending with a newline):

```
web: alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Migrations run in the start command, not the build, so they execute with the production `DATABASE_URL` already injected and are re-run on every deploy (Alembic is a no-op when the DB is already at head).

- [ ] **Step 2: Write `railway.toml`**

Create `backend/railway.toml`:

```toml
# Railway reads this from the service's root directory, which must be set to `backend`
# in the Railway UI (Settings -> Source -> Root Directory).

[build]
builder = "NIXPACKS"

[deploy]
startCommand = "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT"
healthcheckPath = "/api/health"
healthcheckTimeout = 120
restartPolicyType = "ON_FAILURE"
restartPolicyMaxRetries = 3
numReplicas = 1
```

`numReplicas = 1` is deliberate: Stage 3 runs analysis in a FastAPI `BackgroundTasks` inside the web process (`docs/PLAN.md` §0, "No Celery for the MVP"), so a second replica would have no way to see a run queued on the first. Scaling past one replica is the moment to add the queue.

- [ ] **Step 3: Pin the Python version**

Create `backend/runtime.txt`:

```
python-3.11.9
```

3.11 is the target from `docs/PLAN.md` §0; `.9` is the owner's local patch version, so local and production agree. Nixpacks reads `runtime.txt`; Render and Heroku read the identical format, so this file survives a host change.

- [ ] **Step 4: Write the production env example**

Create `backend/.env.production.example`:

```
# Railway -> service -> Variables. Copy this list; never commit real values.

ENV=prod

# Supabase (prod project, Pro plan, Mumbai ap-south-1)
#   Project Settings -> Database -> Connection string -> "Session pooler"
#   then replace the postgresql:// scheme with postgresql+psycopg://
DATABASE_URL=postgresql+psycopg://postgres.<project-ref>:<db-password>@aws-0-ap-south-1.pooler.supabase.com:5432/postgres

# Generate once and never rotate casually - rotating logs every client out:
#   python -c "import secrets; print(secrets.token_hex(32))"
SECRET_KEY=<64 hex characters>

# Exactly the Vercel origin(s) that may call this API. No wildcard, no trailing slash.
CORS_ORIGINS=https://<your-app>.vercel.app

# Error reporting (Sentry -> backend project -> Client Keys)
SENTRY_DSN=https://<public-key>@o<org-id>.ingest.sentry.io/<project-id>

# Request limits. MAX_REQUEST_MB must stay larger than MAX_UPLOAD_MB.
MAX_REQUEST_MB=25
MAX_UPLOAD_MB=20

# Files: a PRIVATE Supabase Storage bucket. The service_role key is backend-only and
# must never appear in a NEXT_PUBLIC_* variable or anywhere in the frontend.
STORAGE_BACKEND=supabase
STORAGE_BUCKET=ad-optimizer
SUPABASE_URL=https://<project-ref>.supabase.co
SUPABASE_SERVICE_KEY=<service_role key>

# Manual payments only in the MVP (docs/PLAN.md §7 #5).
PAYMENT_PROVIDER=manual

# Only needed while running scripts/seed_demo.py. Remove afterwards.
DEMO_PASSWORD=
```

- [ ] **Step 5: Verify the start command locally, exactly as the host will run it**

Run:
```bash
cd backend && PORT=8010 .venv/Scripts/alembic upgrade head && PORT=8010 .venv/Scripts/python -m uvicorn app.main:app --host 127.0.0.1 --port 8010
```
Expected: Alembic prints `Running upgrade ...` or nothing (already at head), then uvicorn prints `Uvicorn running on http://127.0.0.1:8010`, and the first log lines are **single-line JSON objects** (Task 2's formatter). In a second terminal, `curl -i http://127.0.0.1:8010/api/health` returns `200`, `{"status":"ok","env":"dev"}` and the `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy` and `X-Request-ID` headers. Stop with Ctrl-C.

Binding to `0.0.0.0` is correct on the host and wrong on a laptop; that is the only difference between this command and the Procfile.

- [ ] **Step 6: Verify the prod guard rails fire**

Run:
```bash
cd backend && ENV=prod SECRET_KEY=$(python -c "import secrets;print(secrets.token_hex(32))") CORS_ORIGINS='*' .venv/Scripts/python -c "from app.core.settings import get_settings; get_settings.cache_clear(); from app.main import create_app; create_app()"
```
Expected: exits non-zero with `CorsMisconfiguredError: CORS_ORIGINS must list the exact frontend origin(s) in production; got ['*']`. This is the proof that a misconfigured deploy fails loudly at boot instead of serving an open API.

- [ ] **Step 7: Commit**

```bash
git add backend/Procfile backend/railway.toml backend/runtime.txt backend/.env.production.example
git commit -m "chore(deploy): Railway start command, health check, Python pin and prod env template" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 9: `scripts/seed_demo.py` — an idempotent demo client with an approved report

**Files:**
- Create: `backend/scripts/__init__.py`
- Create: `backend/scripts/seed_demo.py`
- Test: `backend/tests/test_seed_demo.py`

**Interfaces:**
- Consumes, all verbatim from `INTERFACES.md`:
  - `app.core.db.get_engine()`, `app.core.db.Base`
  - `app.models.User`, `Client`, `AdDataUpload`, `AnalysisRun`
  - `app.pipeline.data_generator.write_sample_csv(path, **kw)` (Stage 1)
  - `app.services.auth.signup_client(session, email, password, business_name) -> User` and `create_admin(session, email, password) -> User` (Stage 2)
  - `app.services.upload.create_upload(session, client, filename, data) -> AdDataUpload` and `DuplicateUploadError` (Stage 3)
  - `app.services.analysis.create_run(session, client, upload_id) -> AnalysisRun` and `execute_run(run_id) -> None` (Stage 3)
  - `app.services.admin.approve_run(session, actor, run_id, note) -> AnalysisRun` (Stage 6)
- Produces: `scripts.seed_demo.main() -> int` (0 on success, 2 when `DEMO_PASSWORD` is unset). Run as `python -m scripts.seed_demo` from `backend/`.

Idempotence rule: running it twice must leave exactly one demo user, one demo client, one upload and one approved run, and must not raise. This matters because the owner will run it on a live prod database during a sales-demo setup and may well run it again later.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_seed_demo.py`:

```python
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

import app.models  # noqa: F401  (registers every table on Base.metadata)
from app.core.settings import get_settings
from app.models import AdDataUpload, AnalysisRun, Client, User


@pytest.fixture
def seeded_db(tmp_path, monkeypatch):
    """Point the global engine at a throwaway file-backed SQLite database.

    A file, not :memory:, because execute_run() opens its own session and therefore its
    own connection - an in-memory database would be empty from that connection's view.
    """
    import app.core.db as db_module

    monkeypatch.setenv("DATABASE_URL", f"sqlite+pysqlite:///{tmp_path / 'seed.db'}")
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path / "storage"))
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("DEMO_PASSWORD", "demo-password-123")
    get_settings.cache_clear()
    db_module._engine = None
    db_module._session_factory = None

    db_module.Base.metadata.create_all(db_module.get_engine())
    yield db_module.get_engine()

    db_module._engine = None
    db_module._session_factory = None
    get_settings.cache_clear()


def test_seed_creates_a_demo_client_with_an_approved_run(seeded_db):
    from scripts.seed_demo import main

    assert main() == 0

    with Session(seeded_db) as session:
        demo = session.scalars(select(User).where(User.email == "demo@example.com")).one()
        assert demo.role == "client"
        client = session.scalars(select(Client).where(Client.user_id == demo.id)).one()

        upload = session.scalars(
            select(AdDataUpload).where(AdDataUpload.client_id == client.id)
        ).one()
        assert upload.status == "validated"
        assert upload.row_count > 0

        run = session.scalars(select(AnalysisRun).where(AnalysisRun.client_id == client.id)).one()
        assert run.status == "done"
        assert run.review_status == "approved"
        assert run.headline_waste is not None and run.headline_waste > 0


def test_seed_also_creates_the_admin_that_approves_the_run(seeded_db):
    from scripts.seed_demo import main

    assert main() == 0

    with Session(seeded_db) as session:
        admin = session.scalars(select(User).where(User.email == "admin@example.com")).one()
        assert admin.role == "admin"
        run = session.scalars(select(AnalysisRun)).one()
        assert run.reviewed_by == admin.id


def test_seed_is_idempotent(seeded_db):
    from scripts.seed_demo import main

    assert main() == 0
    assert main() == 0

    with Session(seeded_db) as session:
        assert len(session.scalars(select(User)).all()) == 2  # demo client + admin
        assert len(session.scalars(select(Client)).all()) == 1
        assert len(session.scalars(select(AdDataUpload)).all()) == 1
        assert len(session.scalars(select(AnalysisRun)).all()) == 1


def test_seed_refuses_to_run_without_a_password(seeded_db, monkeypatch, capsys):
    from scripts.seed_demo import main

    monkeypatch.delenv("DEMO_PASSWORD", raising=False)
    assert main() == 2
    assert "DEMO_PASSWORD" in capsys.readouterr().err
```

- [ ] **Step 2: Run it and watch it fail**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_seed_demo.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts'`.

- [ ] **Step 3: Make `scripts/` importable**

Create `backend/scripts/__init__.py` as an empty file:

```python
```

(Genuinely empty — it exists only so `python -m scripts.seed_demo` and `from scripts.seed_demo import main` both resolve. `scripts/create_admin.py` from Stage 2 keeps working unchanged.)

- [ ] **Step 4: Write the seed script**

Create `backend/scripts/seed_demo.py`:

```python
"""Seed a demo client with a finished, approved report, for sales demos.

Idempotent: every object is looked up before it is created, so running this twice
leaves exactly one demo client, one upload and one approved run.

    cd backend
    DEMO_PASSWORD='a-strong-password' python -m scripts.seed_demo
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_engine
from app.models import AdDataUpload, AnalysisRun, Client, User
from app.pipeline.data_generator import write_sample_csv
from app.services.admin import approve_run
from app.services.analysis import create_run, execute_run
from app.services.auth import create_admin, signup_client
from app.services.upload import DuplicateUploadError, create_upload

DEMO_EMAIL = os.environ.get("DEMO_EMAIL", "demo@example.com")
ADMIN_EMAIL = os.environ.get("DEMO_ADMIN_EMAIL", "admin@example.com")
BUSINESS_NAME = "Demo Retail Co"
SAMPLE_FILENAME = "sample_30d.csv"
APPROVAL_NOTE = "Seeded demo data."


def _get_or_create_demo_client(session: Session, password: str) -> Client:
    user = session.scalars(select(User).where(User.email == DEMO_EMAIL)).one_or_none()
    if user is None:
        user = signup_client(session, DEMO_EMAIL, password, BUSINESS_NAME)
        session.commit()
        print(f"created demo client {DEMO_EMAIL}")
    else:
        print(f"demo client {DEMO_EMAIL} already exists")
    return session.scalars(select(Client).where(Client.user_id == user.id)).one()


def _get_or_create_admin(session: Session, password: str) -> User:
    admin = session.scalars(select(User).where(User.email == ADMIN_EMAIL)).one_or_none()
    if admin is None:
        admin = create_admin(session, ADMIN_EMAIL, password)
        session.commit()
        print(f"created admin {ADMIN_EMAIL}")
    else:
        print(f"admin {ADMIN_EMAIL} already exists")
    return admin


def _sample_csv_bytes() -> bytes:
    """A 30-day synthetic account with injected waste, so the demo report has real numbers."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / SAMPLE_FILENAME
        write_sample_csv(path, days=30, seed=20260916)
        return path.read_bytes()


def _get_or_create_upload(session: Session, client: Client) -> AdDataUpload:
    try:
        upload = create_upload(session, client, SAMPLE_FILENAME, _sample_csv_bytes())
        session.commit()
        print(f"uploaded {SAMPLE_FILENAME} ({upload.row_count} rows)")
        return upload
    except DuplicateUploadError:
        session.rollback()
        upload = session.scalars(
            select(AdDataUpload)
            .where(AdDataUpload.client_id == client.id)
            .order_by(AdDataUpload.id)
        ).first()
        assert upload is not None  # DuplicateUploadError means one exists
        print(f"upload {SAMPLE_FILENAME} already exists")
        return upload


def _get_or_create_approved_run(session: Session, client: Client, upload_id: int, admin: User) -> AnalysisRun:
    existing = session.scalars(
        select(AnalysisRun)
        .where(AnalysisRun.client_id == client.id)
        .order_by(AnalysisRun.id)
    ).first()
    if existing is not None:
        print(f"run {existing.id} already exists ({existing.status}/{existing.review_status})")
        return existing

    run = create_run(session, client, upload_id)
    session.commit()
    run_id = run.id

    # Synchronous on purpose: the script must not exit before the analysis is written.
    execute_run(run_id)

    session.expire_all()
    run = session.get(AnalysisRun, run_id)
    assert run is not None
    if run.status != "done":
        raise RuntimeError(f"analysis run {run_id} finished as {run.status}: {run.error_message}")

    approve_run(session, admin, run_id, APPROVAL_NOTE)
    session.commit()
    print(f"run {run_id} analysed and approved (headline waste {run.headline_waste})")
    return run


def main() -> int:
    password = os.environ.get("DEMO_PASSWORD")
    if not password:
        print("DEMO_PASSWORD is not set. Refusing to seed accounts with a guessable password.", file=sys.stderr)
        return 2

    with Session(get_engine()) as session:
        admin = _get_or_create_admin(session, password)
        client = _get_or_create_demo_client(session, password)
        upload = _get_or_create_upload(session, client)
        _get_or_create_approved_run(session, client, upload.id, admin)

    print(f"done. Sign in as {DEMO_EMAIL} to see an approved report.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

Two details that matter:
- `execute_run(run_id)` is called **synchronously**, not through `BackgroundTasks`. Stage 3 defines it as a plain function that opens its own session, so calling it directly is correct and means the script cannot exit mid-analysis.
- The one long `def _get_or_create_approved_run(...)` signature line exceeds 100 characters. Let ruff format wrap it in Step 6 rather than hand-wrapping it now.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd backend && .venv/Scripts/python -m pytest tests/test_seed_demo.py -v`
Expected: PASS — `4 passed`. If `test_seed_is_idempotent` fails with a duplicate `User`, the cause is a missing `session.commit()` before the second lookup; fix the script, never the assertion.

- [ ] **Step 6: Run it for real against the local dev database**

Run:
```bash
cd backend && .venv/Scripts/alembic upgrade head && DEMO_PASSWORD='demo-password-123' .venv/Scripts/python -m scripts.seed_demo
```
Expected, first run:
```
created admin admin@example.com
created demo client demo@example.com
uploaded sample_30d.csv (NNN rows)
run 1 analysed and approved (headline waste NNNNN.NN)
done. Sign in as demo@example.com to see an approved report.
```
Run the identical command again. Expected, second run: the same five lines with `already exists` in place of `created`/`uploaded`, and exit code 0.

- [ ] **Step 7: Lint and commit**

Run: `cd backend && .venv/Scripts/ruff format . && .venv/Scripts/ruff check . && .venv/Scripts/python -m pytest`
Expected: `1 file reformatted` (the long signature), then `All checks passed!`, then all tests pass.

```bash
git add backend/scripts/__init__.py backend/scripts/seed_demo.py backend/tests/test_seed_demo.py
git commit -m "feat(scripts): idempotent demo seed with an approved sample report" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 10: Policy pages `/terms`, `/privacy`, `/refunds`

**Files:**
- Create: `frontend/src/components/ui/PolicyLayout.tsx`
- Create: `frontend/src/components/ui/Footer.tsx`
- Create: `frontend/src/app/terms/page.tsx`
- Create: `frontend/src/app/privacy/page.tsx`
- Create: `frontend/src/app/refunds/page.tsx`
- Modify: `frontend/src/app/layout.tsx`
- Modify: `frontend/src/app/dashboard/billing/page.tsx`
- Create: `frontend/vitest.config.ts`, `frontend/vitest.setup.ts` (only if Stage 4 did not)
- Modify: `frontend/package.json`
- Test: `frontend/src/components/ui/Footer.test.tsx`
- Test: `frontend/src/components/ui/PolicyPages.test.tsx`

**Interfaces:**
- Consumes: the Stage 0 Tailwind tokens (`ink`, `surface`, `teal`, `coral`, `paper`, `slate`) and font tokens (`font-display`, `font-body`) from `frontend/src/app/globals.css`; the `@/*` → `./src/*` path alias from `tsconfig.json`; Stage 7's `/dashboard/billing` page.
- Produces:
  - `PolicyLayout({ title, updated, children }: { title: string; updated: string; children: ReactNode })` — default export **not** used; named export from `@/components/ui/PolicyLayout`.
  - `Footer()` — named export from `@/components/ui/Footer`; renders one `<nav aria-label="Legal">` with links to `/terms`, `/privacy`, `/refunds`.
  - Routes `/terms`, `/privacy`, `/refunds`, each a server component with no client JS.
  - `npm test` → `vitest run`.

`TODO-OWNER` is the *only* permitted placeholder in this repo, and only inside these three pages' copy (`INTERFACES.md`, Stage 8). The owner supplies real wording before launch; a gateway application will reject boilerplate.

- [ ] **Step 1: Install the test harness (skip if Stage 4 already did)**

Run: `cd frontend && npm ls vitest`

- If it prints a vitest version, Stage 4 set this up. Skip to Step 3, and only make sure `package.json` has `"test": "vitest run"`.
- Otherwise run:

```bash
cd frontend && npm install --save-dev --save-exact vitest@5.0.1 @vitejs/plugin-react@6.1.1 jsdom@30.0.1 @testing-library/react@16.3.3 @testing-library/jest-dom@7.0.1
```
Expected: `added N packages`.

- [ ] **Step 2: Configure Vitest (skip if Stage 4 already did)**

Create `frontend/vitest.config.ts`:

```ts
import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
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

In `frontend/package.json`, add to `"scripts"`:

```json
    "test": "vitest run"
```

`globals: false` keeps `tsc --noEmit` honest: every test imports `describe`/`it`/`expect` explicitly instead of relying on ambient types.

- [ ] **Step 3: Write the failing tests**

Create `frontend/src/components/ui/Footer.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Footer } from "@/components/ui/Footer";

describe("Footer", () => {
  it("links to all three policy pages", () => {
    render(<Footer />);
    expect(screen.getByRole("link", { name: "Terms" })).toHaveAttribute("href", "/terms");
    expect(screen.getByRole("link", { name: "Privacy" })).toHaveAttribute("href", "/privacy");
    expect(screen.getByRole("link", { name: "Refunds" })).toHaveAttribute("href", "/refunds");
  });

  it("labels the legal navigation for screen readers", () => {
    render(<Footer />);
    expect(screen.getByRole("navigation", { name: "Legal" })).toBeInTheDocument();
  });
});
```

Create `frontend/src/components/ui/PolicyPages.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import PrivacyPage from "@/app/privacy/page";
import RefundsPage from "@/app/refunds/page";
import TermsPage from "@/app/terms/page";

describe("policy pages", () => {
  it("renders the Terms page with a heading", () => {
    render(<TermsPage />);
    expect(screen.getByRole("heading", { level: 1, name: "Terms of Service" })).toBeInTheDocument();
  });

  it("renders the Privacy page with a heading", () => {
    render(<PrivacyPage />);
    expect(screen.getByRole("heading", { level: 1, name: "Privacy Policy" })).toBeInTheDocument();
  });

  it("renders the Refunds page with a heading", () => {
    render(<RefundsPage />);
    expect(screen.getByRole("heading", { level: 1, name: "Refund Policy" })).toBeInTheDocument();
  });

  it("marks every unwritten clause with TODO-OWNER so none ships unnoticed", () => {
    for (const Page of [TermsPage, PrivacyPage, RefundsPage]) {
      const { container, unmount } = render(<Page />);
      expect(container.textContent).toContain("TODO-OWNER");
      unmount();
    }
  });

  it("names the manual payment methods on the refund page", () => {
    render(<RefundsPage />);
    const text = document.body.textContent ?? "";
    expect(text).toContain("JazzCash");
    expect(text).toContain("Easypaisa");
    expect(text).toContain("Raast");
  });
});
```

- [ ] **Step 4: Run them and watch them fail**

Run: `cd frontend && npm test`
Expected: FAIL — `Failed to resolve import "@/components/ui/Footer"` and the same for the three page modules.

- [ ] **Step 5: Write `PolicyLayout` and `Footer`**

Create `frontend/src/components/ui/PolicyLayout.tsx`:

```tsx
import type { ReactNode } from "react";

export function PolicyLayout({
  title,
  updated,
  children,
}: {
  title: string;
  updated: string;
  children: ReactNode;
}) {
  return (
    <main className="mx-auto max-w-3xl px-6 py-16">
      <h1 className="font-display text-4xl text-paper">{title}</h1>
      <p className="mt-2 text-sm text-slate">Last updated: {updated}</p>
      <div className="mt-10 space-y-8 text-paper/80 [&_h2]:font-display [&_h2]:text-xl [&_h2]:text-paper [&_p]:mt-2 [&_p]:leading-relaxed">
        {children}
      </div>
    </main>
  );
}
```

Create `frontend/src/components/ui/Footer.tsx`:

```tsx
import Link from "next/link";

const POLICY_LINKS = [
  { href: "/terms", label: "Terms" },
  { href: "/privacy", label: "Privacy" },
  { href: "/refunds", label: "Refunds" },
] as const;

export function Footer() {
  return (
    <footer className="mt-24 border-t border-slate/20 px-6 py-8">
      <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-4 text-sm text-slate">
        <p>&copy; {new Date().getFullYear()} Ad Spend Optimization</p>
        <nav aria-label="Legal" className="flex flex-wrap gap-6">
          {POLICY_LINKS.map((link) => (
            <Link key={link.href} href={link.href} className="transition-colors hover:text-teal">
              {link.label}
            </Link>
          ))}
        </nav>
      </div>
    </footer>
  );
}
```

- [ ] **Step 6: Write the three pages**

Create `frontend/src/app/terms/page.tsx`:

```tsx
import type { Metadata } from "next";

import { PolicyLayout } from "@/components/ui/PolicyLayout";

export const metadata: Metadata = {
  title: "Terms of Service",
  description: "The terms that govern use of the Ad Spend Optimization service.",
};

export default function TermsPage() {
  return (
    <PolicyLayout title="Terms of Service" updated="TODO-OWNER: effective date">
      <section>
        <h2>1. Who we are</h2>
        <p>TODO-OWNER: registered business name, address, and the contact email clients should use.</p>
      </section>
      <section>
        <h2>2. What the service does</h2>
        <p>
          You upload an export of your advertising data. We analyse it, flag segments whose cost per
          conversion is far above your account average, estimate the spend being wasted, and
          recommend budget cuts. Every report is reviewed by us before you see it.
        </p>
      </section>
      <section>
        <h2>3. What the analysis is and is not</h2>
        <p>
          The analysis is an estimate produced from the data you supply. It is not a guarantee of any
          result, and it is not advertising, financial or legal advice. Decisions about your budget
          remain yours.
        </p>
      </section>
      <section>
        <h2>4. Your account</h2>
        <p>
          You are responsible for keeping your password safe and for everything done through your
          account. Tell us immediately if you believe someone else has access.
        </p>
      </section>
      <section>
        <h2>5. Your data</h2>
        <p>
          You keep ownership of everything you upload. You confirm you are allowed to share it with
          us. How we handle it is described in our Privacy Policy.
        </p>
      </section>
      <section>
        <h2>6. Fees and payment</h2>
        <p>
          Fees are a monthly base fee plus a performance fee calculated on recovered waste that we
          confirm with you before invoicing. TODO-OWNER: the base fee amount, the performance
          percentage, any cap, and the payment window in days.
        </p>
      </section>
      <section>
        <h2>7. Ending the agreement</h2>
        <p>TODO-OWNER: notice period, and what happens to invoices already issued.</p>
      </section>
      <section>
        <h2>8. Limits on our liability</h2>
        <p>TODO-OWNER: liability cap and exclusions, checked by a lawyer before launch.</p>
      </section>
      <section>
        <h2>9. Governing law</h2>
        <p>TODO-OWNER: governing law and the courts that have jurisdiction.</p>
      </section>
    </PolicyLayout>
  );
}
```

Create `frontend/src/app/privacy/page.tsx`:

```tsx
import type { Metadata } from "next";

import { PolicyLayout } from "@/components/ui/PolicyLayout";

export const metadata: Metadata = {
  title: "Privacy Policy",
  description: "What data the Ad Spend Optimization service collects and how it is handled.",
};

export default function PrivacyPage() {
  return (
    <PolicyLayout title="Privacy Policy" updated="TODO-OWNER: effective date">
      <section>
        <h2>1. Who controls your data</h2>
        <p>TODO-OWNER: registered business name, address, and a privacy contact email.</p>
      </section>
      <section>
        <h2>2. What we collect</h2>
        <p>
          Your account details (business name, email address, and a hashed password — we never store
          the password itself); the advertising exports you upload; the reports generated from them;
          your invoices; and the payment details you submit, which are a method, a transaction
          reference, an amount, a date, and an optional screenshot.
        </p>
      </section>
      <section>
        <h2>3. Why we hold it</h2>
        <p>
          To run the analysis you asked for, to show you your reports, to invoice you, to confirm
          payments you tell us about, and to keep an audit trail so any billing dispute can be
          settled from records rather than memory.
        </p>
      </section>
      <section>
        <h2>4. Where it is stored</h2>
        <p>
          In a managed PostgreSQL database and a private file store hosted in the Mumbai
          (ap-south-1) region. Uploaded files and payment screenshots are never publicly
          accessible, and are only served back to the account that owns them.
        </p>
      </section>
      <section>
        <h2>5. Who else sees it</h2>
        <p>
          Our hosting, database and error-reporting providers, acting on our instructions. We do not
          sell your data and we do not use it to train anything. TODO-OWNER: list the providers by
          name once the production accounts are created.
        </p>
      </section>
      <section>
        <h2>6. How long we keep it</h2>
        <p>TODO-OWNER: retention period for uploads, reports and invoices, and what deletion covers.</p>
      </section>
      <section>
        <h2>7. Your rights</h2>
        <p>
          You can ask for a copy of your data, ask us to correct it, or ask us to delete it. Write to
          the privacy contact above. TODO-OWNER: the response time you commit to.
        </p>
      </section>
      <section>
        <h2>8. Cookies</h2>
        <p>
          We set two cookies, both strictly necessary: one short-lived session cookie and one refresh
          cookie, used only to keep you signed in. There is no advertising or tracking cookie.
        </p>
      </section>
    </PolicyLayout>
  );
}
```

Create `frontend/src/app/refunds/page.tsx`:

```tsx
import type { Metadata } from "next";

import { PolicyLayout } from "@/components/ui/PolicyLayout";

export const metadata: Metadata = {
  title: "Refund Policy",
  description: "When and how fees paid to Ad Spend Optimization are refunded.",
};

export default function RefundsPage() {
  return (
    <PolicyLayout title="Refund Policy" updated="TODO-OWNER: effective date">
      <section>
        <h2>1. How you pay</h2>
        <p>
          Invoices are paid manually to the accounts listed on the invoice: JazzCash, Easypaisa,
          NayaPay, or a bank transfer via Raast or IBAN. After paying, you submit the transaction ID
          on your billing page, and we confirm it against our own records before the invoice is
          marked paid.
        </p>
      </section>
      <section>
        <h2>2. If you were charged the wrong amount</h2>
        <p>
          Performance fees are based on recovered waste that we calculate and then confirm before
          issuing an invoice. If you believe the figure is wrong, raise it and we will re-check it
          against the stored report and its configuration snapshot. TODO-OWNER: the window in days
          for raising a billing query.
        </p>
      </section>
      <section>
        <h2>3. Duplicate or failed payments</h2>
        <p>
          If a payment reaches us twice, or reaches us for an invoice that was already settled, we
          refund the surplus to the account it came from. TODO-OWNER: how many working days that
          takes.
        </p>
      </section>
      <section>
        <h2>4. Monthly fees already paid</h2>
        <p>TODO-OWNER: whether a paid month is refundable, pro-rated, or non-refundable, and why.</p>
      </section>
      <section>
        <h2>5. How to request a refund</h2>
        <p>
          TODO-OWNER: the email address to write to, and what to include — invoice number,
          transaction ID, and the amount.
        </p>
      </section>
    </PolicyLayout>
  );
}
```

- [ ] **Step 7: Render the footer site-wide**

In `frontend/src/app/layout.tsx`, import the footer and wrap the children so it sits below every page:

```tsx
import type { Metadata } from "next";
import { Inter, Space_Grotesk } from "next/font/google";

import { Footer } from "@/components/ui/Footer";

import "./globals.css";
```

and replace the `<body>` line with:

```tsx
      <body className="flex min-h-screen flex-col bg-ink text-paper antialiased">
        <div className="flex-1">{children}</div>
        <Footer />
      </body>
```

- [ ] **Step 8: Link the policies from the billing page**

In `frontend/src/app/dashboard/billing/page.tsx`, make sure `Link` is imported (`import Link from "next/link";`) and add this as the last element inside the page's returned wrapper, after the invoice list:

```tsx
      <p className="mt-10 text-xs text-slate">
        Paying an invoice means you accept our{" "}
        <Link href="/terms" className="underline hover:text-teal">
          Terms
        </Link>
        ,{" "}
        <Link href="/privacy" className="underline hover:text-teal">
          Privacy Policy
        </Link>{" "}
        and{" "}
        <Link href="/refunds" className="underline hover:text-teal">
          Refund Policy
        </Link>
        .
      </p>
```

- [ ] **Step 9: Run the tests to verify they pass**

Run: `cd frontend && npm test`
Expected: PASS — `Test Files 2 passed`, `Tests 7 passed`.

- [ ] **Step 10: Check the pages in a browser at mobile width**

Run: `cd frontend && npm run dev`
Open `http://localhost:3000/terms`, `/privacy` and `/refunds`. Expected: each page renders its heading in Space Grotesk on the ink background, the footer shows all three links at the bottom, and at a 375px viewport (DevTools device toolbar) the text does not overflow horizontally and the footer links wrap rather than clip. Stop with Ctrl-C.

- [ ] **Step 11: Typecheck, lint, build and commit**

Run: `cd frontend && npx tsc --noEmit && npm run lint && npm run build`
Expected: no output from `tsc`, no lint errors, and the build's route table lists `/terms`, `/privacy` and `/refunds` as static (`○`) routes.

```bash
git add frontend/package.json frontend/package-lock.json frontend/vitest.config.ts frontend/vitest.setup.ts frontend/src/components/ui/PolicyLayout.tsx frontend/src/components/ui/Footer.tsx frontend/src/components/ui/Footer.test.tsx frontend/src/components/ui/PolicyPages.test.tsx frontend/src/app/terms/page.tsx frontend/src/app/privacy/page.tsx frontend/src/app/refunds/page.tsx frontend/src/app/layout.tsx frontend/src/app/dashboard/billing/page.tsx
git commit -m "feat(legal): add Terms, Privacy and Refund pages with a site footer" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 11: CI, the README deploy runbook and the smoke-test checklist

**Files:**
- Modify: `.github/workflows/ci.yml`
- Modify: `README.md`

**Interfaces:**
- Consumes: everything built in Tasks 1–10 — `npm test` (Task 10), the pytest coverage gate added by Stage 1 Task 7, `backend/Procfile`, `backend/railway.toml`, `backend/runtime.txt`, `backend/.env.production.example` (Task 8), `frontend/.env.production.example` (Task 5), `python -m scripts.seed_demo` (Task 9), `scripts/create_admin.py --email --password` (Stage 2).
- Produces: no code. Produces the runbook the owner follows, and the checklist that decides whether Stage 8 is done.

- [ ] **Step 1: Extend the CI workflow**

In `.github/workflows/ci.yml`:

1. In the `backend` job, confirm the test step reads `- run: pytest --cov --cov-report=term-missing` (Stage 1 Task 7 changed it). If it still reads `- run: pytest`, change it now.
2. In the `backend` job's `env:` block, add the two variables the new startup checks read, so CI exercises the same code path as production would if misconfigured:

```yaml
    env:
      ENV: test
      DATABASE_URL: sqlite+pysqlite:///:memory:
      SECRET_KEY: ci-secret
      CORS_ORIGINS: http://localhost:3000
      STORAGE_BACKEND: local
```

3. In the `frontend` job, insert a test step between `npm run lint` and `npm run build`:

```yaml
      - run: npx tsc --noEmit
      - run: npm test
      - run: npm run build
```

The frontend job deliberately has **no** `NEXT_PUBLIC_SENTRY_DSN`, so CI always builds the unwrapped config and never attempts a source-map upload.

- [ ] **Step 2: Dry-run the exact CI commands locally**

Run:
```bash
cd backend && .venv/Scripts/ruff check . && .venv/Scripts/ruff format --check . && .venv/Scripts/python -m pytest --cov --cov-report=term-missing
```
Expected: `All checks passed!`, everything formatted, all tests pass, and the coverage line does **not** print `FAIL Required test coverage of 90% not reached`.

Run:
```bash
cd frontend && npm ci && npm run lint && npx tsc --noEmit && npm test && npm run build
```
Expected: all five succeed.

- [ ] **Step 3: Rewrite the README's "Run locally" section**

Replace the existing "Run locally" and "Tests" sections of `README.md` with:

````markdown
## Run locally

### Backend

```bash
cd backend
python -m venv .venv
.venv/Scripts/activate            # Windows (Git Bash); use source .venv/bin/activate elsewhere
pip install -r requirements-dev.txt
cp .env.example .env              # then edit DATABASE_URL and SECRET_KEY
alembic upgrade head
uvicorn app.main:app --reload
```

Health check: <http://127.0.0.1:8000/api/health> — the response carries
`X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy` and
`X-Request-ID`. Logs are one JSON object per line.

Create an admin (signup can never make one):

```bash
cd backend
python scripts/create_admin.py --email you@example.com --password '<a long password>'
```

Seed a demo client with a finished, approved report (idempotent — safe to re-run):

```bash
cd backend
DEMO_PASSWORD='<a long password>' python -m scripts.seed_demo
```

That creates `demo@example.com` (client) and `admin@example.com` (admin), uploads a 30-day
synthetic account with injected waste, analyses it, and approves the run — so signing in as
`demo@example.com` lands on a populated dashboard.

### Frontend

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

Open <http://localhost:3000> — `/api/*` is proxied to the backend, which keeps auth cookies
first-party.

### Tests

```bash
cd backend && pytest --cov --cov-report=term-missing
cd backend && ruff check . && ruff format --check .
cd frontend && npm run lint && npx tsc --noEmit && npm test && npm run build
```

## Environment variables

| Variable | Where | What it does |
|---|---|---|
| `ENV` | backend | `dev` / `test` / `prod`. `prod` turns on HSTS, `Secure` cookies and the CORS guard |
| `DATABASE_URL` | backend | SQLAlchemy URL. Postgres uses `postgresql+psycopg://` and the Supabase session pooler |
| `SECRET_KEY` | backend | Signs JWTs. Rotating it signs every client out |
| `CORS_ORIGINS` | backend | Comma-separated list of allowed browser origins. `*` is refused when `ENV=prod` |
| `MAX_REQUEST_MB` | backend | Whole-request cap (413 above it). Must stay above `MAX_UPLOAD_MB` |
| `MAX_UPLOAD_MB` | backend | Per-file upload cap |
| `SENTRY_DSN` | backend | Empty = Sentry off |
| `STORAGE_BACKEND` | backend | `local` or `supabase` |
| `STORAGE_ROOT` | backend | Directory used when `STORAGE_BACKEND=local` |
| `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `STORAGE_BUCKET` | backend | Private Supabase Storage bucket. **The service key is backend-only** |
| `DEMO_PASSWORD` | backend | Only read by `scripts/seed_demo.py` |
| `BACKEND_URL` | frontend | Public URL of the API, used by the `/api/*` rewrite |
| `NEXT_PUBLIC_SENTRY_DSN`, `NEXT_PUBLIC_SENTRY_ENV` | frontend | Empty = Sentry off |
| `SENTRY_ORG`, `SENTRY_PROJECT`, `SENTRY_AUTH_TOKEN` | frontend | Build-time only, for source-map upload |

Full templates: `backend/.env.example`, `backend/.env.production.example`,
`frontend/.env.example`, `frontend/.env.production.example`. Never commit a filled-in copy.
````

- [ ] **Step 4: Add the "Deploy" runbook to the README**

Append to `README.md`:

````markdown
## Deploy

Supabase Postgres + Storage (Mumbai `ap-south-1`), backend on Railway, frontend on Vercel.
Every step below is an **owner checkpoint** — it needs an account the repository does not have.
Work through them in order; each one ends with something you can verify.

### 1. Supabase production project

1. Create a new project: name `ad-optimizer-prod`, region **Mumbai (ap-south-1)**, plan **Pro**.
2. Save the database password somewhere safe — it appears once.
3. Settings → Database → confirm **Daily backups** are enabled (included with Pro). Leave
   Point-in-Time Recovery off for now.
4. Settings → Database → Connection string → **Session pooler**. Copy it, then change the
   scheme from `postgresql://` to `postgresql+psycopg://`. That is your `DATABASE_URL`.
5. Storage → New bucket → name `ad-optimizer`, **Public bucket OFF**. The backend reaches it
   with the service key; nothing is ever served from a public URL.
6. Settings → API → copy the **Project URL** (`SUPABASE_URL`) and the **`service_role`** key
   (`SUPABASE_SERVICE_KEY`). The `service_role` key bypasses row-level security: it goes on
   Railway only, never into Vercel, never into a `NEXT_PUBLIC_*` variable.

Verify: the bucket list shows `ad-optimizer` with a padlock / "Private" label.

### 2. Sentry projects

1. Create two projects in Sentry: one **Python / FastAPI** (backend) and one **Next.js**
   (frontend).
2. Copy each project's DSN. Backend DSN → `SENTRY_DSN` on Railway. Frontend DSN →
   `NEXT_PUBLIC_SENTRY_DSN` on Vercel.
3. For source maps, create an org auth token with the `project:releases` scope →
   `SENTRY_AUTH_TOKEN` on Vercel, plus `SENTRY_ORG` and `SENTRY_PROJECT` slugs.

Verify: both projects show "Waiting for events".

### 3. Railway backend service

1. New project → Deploy from GitHub repo → pick this repository.
2. Service → Settings → Source → **Root Directory: `backend`**. Railway then picks up
   `backend/railway.toml`, `backend/runtime.txt` and `backend/requirements.txt`.
3. Service → Variables → paste every variable from `backend/.env.production.example`, filled
   in. `CORS_ORIGINS` is not known yet; set it to `https://localhost` for now and fix it in
   step 5.
4. Deploy. The start command runs `alembic upgrade head` before uvicorn, so the schema is
   created on the first boot.
5. Settings → Networking → Generate Domain. That URL is your `BACKEND_URL`.

Verify: `curl -i https://<railway-domain>/api/health` returns `200`,
`{"status":"ok","env":"prod"}`, and the response includes `Strict-Transport-Security`.
Railway's Deploy Logs show one JSON object per line.

### 4. Vercel frontend project

1. New Project → import the same repository → **Root Directory: `frontend`**. Framework
   preset: Next.js.
2. Environment Variables → paste everything from `frontend/.env.production.example`, with
   `BACKEND_URL` set to the Railway domain from step 3.
3. Deploy, then copy the production domain.

Verify: the Vercel domain loads the landing page, and `/terms`, `/privacy` and `/refunds`
all render.

### 5. Close the CORS loop

1. Back on Railway, set `CORS_ORIGINS` to the exact Vercel production origin, for example
   `https://ad-optimizer.vercel.app` — no trailing slash, no wildcard. Add the custom domain
   as a second comma-separated entry if you have one.
2. Redeploy the Railway service.

Verify: signing in on the Vercel domain works. If the browser console shows a CORS error,
the origin string does not match exactly — check for a trailing slash or `www.`.

### 6. Migrations and the first admin

The Procfile already ran `alembic upgrade head` on deploy. To run it by hand, or to create
the admin, open the Railway service shell (or `railway run` locally) and run:

```bash
alembic upgrade head
python scripts/create_admin.py --email you@example.com --password '<a long password>'
```

Optionally seed the sales-demo account, then delete the variable:

```bash
DEMO_PASSWORD='<a long password>' python -m scripts.seed_demo
```

Verify: signing in on the Vercel domain with the admin email reaches `/admin`.

### 7. Smoke test

Run the checklist below. Stage 8 is not done until every line is ticked **in production**.

## Smoke-test checklist (production)

Run in one sitting, in this order, on the live Vercel domain. Use a real browser, not curl —
the point is to prove the cookie, CORS and storage paths work end to end.

- [ ] **Signup.** `/signup` with a fresh email creates a client account and lands on the
      dashboard. The dashboard shows the "no uploads yet" empty state.
- [ ] **Upload.** `/dashboard/upload` accepts `backend/tests/fixtures/sample_30d.csv`. The
      file is accepted, row count and date range are shown, and the run status moves from
      queued to done.
- [ ] **Nothing leaks before approval.** As that client, the dashboard still shows the
      "awaiting review" state — an unapproved run is never visible.
- [ ] **Admin approve.** Sign in as the admin in a second browser profile. `/admin/runs`
      lists the pending run with its headline waste and config snapshot. Approve it with a
      note. `/admin/audit` shows a `run.approve` entry naming the admin.
- [ ] **Dashboard.** Back as the client, the dashboard now shows the hero, total spend,
      estimated waste and recovery %, the per-dimension breakdown tables with flagged rows
      in coral, and the recommendations list. Check it once at mobile width.
- [ ] **PDF.** `/api/reports/{run_id}/pdf` downloads, and the numbers on the cover match the
      dashboard exactly.
- [ ] **Invoice.** As admin, draft an invoice for the period, edit and confirm the recovered
      waste, then issue it. The client's `/dashboard/billing` shows it with the amount, due
      date and the payment accounts.
- [ ] **Manual payment confirmed.** As the client, submit a payment: method, transaction ID,
      amount, date, and a screenshot. The invoice moves to "payment submitted". As admin,
      confirm it. The invoice becomes **paid**, and `/admin/audit` has a `payment.confirm`
      entry.
- [ ] **A reused transaction ID is refused.** Submitting the same method and transaction ID
      again returns an error, not a second payment.
- [ ] **Tenant isolation.** Signed in as client A, opening client B's report or invoice URL
      returns 404, not 403 and not the data.
- [ ] **Files really are in Supabase.** The Supabase Storage bucket lists the uploaded CSV
      and the payment screenshot, and opening the object's public URL directly fails.
- [ ] **Errors reach Sentry.** Both Sentry projects have left "Waiting for events" (trigger
      one deliberately if needed, e.g. request a report id that does not exist).
- [ ] **Policy pages.** `/terms`, `/privacy` and `/refunds` load, and the footer links to all
      three from every page.
- [ ] **Security headers in prod.** `curl -I https://<railway-domain>/api/health` shows
      `Strict-Transport-Security`, `X-Content-Type-Options`, `X-Frame-Options`,
      `Referrer-Policy` and `Permissions-Policy`.
- [ ] **CORS is closed.** From a browser console on any other site,
      `fetch("https://<railway-domain>/api/auth/me", {credentials: "include"})` fails with a
      CORS error.
````

- [ ] **Step 5: Final full local verification — backend**

Run:
```bash
cd backend && .venv/Scripts/python -m pytest --cov --cov-report=term-missing
```
Expected: every test passes (Stage 0–7's suite plus this stage's `test_settings_stage8.py` 7, `test_middleware.py` 15, `test_cors.py` 7, `test_sentry_init.py` 5, `test_engine_pool.py` 4, `test_storage_supabase.py` 14, `test_seed_demo.py` 4 = 56 new), and the coverage total does not trip the 90% gate.

Run:
```bash
cd backend && .venv/Scripts/ruff check . && .venv/Scripts/ruff format --check .
```
Expected: `All checks passed!` and `N files already formatted`.

- [ ] **Step 6: Final full local verification — frontend**

Run:
```bash
cd frontend && npm run lint && npx tsc --noEmit && npm test && npm run build
```
Expected: no lint errors; no `tsc` output; `Test Files 2 passed`; the build's route table lists `/terms`, `/privacy` and `/refunds` as static routes and ends with no errors.

- [ ] **Step 7: Final full local verification — the app actually boots**

Run, in two terminals:
```bash
cd backend && .venv/Scripts/alembic upgrade head && .venv/Scripts/python -m uvicorn app.main:app --port 8000
```
```bash
cd frontend && npm run dev
```
Then: open <http://localhost:3000/terms> (renders), and run
`curl -i http://localhost:3000/api/health` — expected `200`, `{"status":"ok","env":"dev"}`
and an `X-Request-ID` header, proving the proxy, the middleware stack and the backend all
line up. Stop both with Ctrl-C.

- [ ] **Step 8: Commit and push**

```bash
git add .github/workflows/ci.yml README.md
git commit -m "docs: deploy runbook, environment reference and production smoke-test checklist" -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
git push
```
Then confirm the Actions tab shows both the `backend` and `frontend` jobs green. If there is
no GitHub remote yet, Steps 5–7 are the checkpoint.

---

## Stage 8 exit checklist (from `docs/PLAN.md` §6)

- [ ] Sentry is initialised on the backend when `SENTRY_DSN` is set and completely off when it is not (Task 4), and on the frontend under `NEXT_PUBLIC_SENTRY_DSN` (Task 5).
- [ ] Security headers on every response; HSTS in prod only (Task 2).
- [ ] CORS locked to the frontend origin, wildcard refused at boot in prod (Task 3).
- [ ] Request bodies over `MAX_REQUEST_MB` get 413 (Task 3).
- [ ] Structured JSON logging with a per-request id (Task 2).
- [ ] Supabase Postgres with backups on, connected through the session pooler with a bounded pool (Task 7 + README Deploy §1).
- [ ] Backend on Railway, frontend on Vercel, files in a private Supabase Storage bucket (Tasks 6, 8 + README Deploy §3–4).
- [ ] Seeded demo client, idempotent (Task 9).
- [ ] Smoke-test checklist in the README (Task 11).
- [ ] Terms, Privacy and Refund pages exist and are linked from the footer and the billing page (Task 10).
- [ ] **Done when:** the full flow works in production — signup → upload → admin approve → dashboard → PDF → invoice → manual payment confirmed (README "Smoke-test checklist", run by the owner).

---

## Decisions

Recorded here because this plan made them; nothing in `docs/PLAN.md` or `INTERFACES.md` fixed them.

1. **Railway, not Render.** `docs/PLAN.md` §6 allows either. Railway's `startCommand` runs on the web container, so `alembic upgrade head && uvicorn ...` is one line in both `Procfile` and `railway.toml`; Render needs a separate `preDeployCommand` inside a `render.yaml` blueprint, which is a second file and a second source of truth. Railway also has a region close to the Supabase Mumbai project. No `render.yaml` is created.
2. **No `frontend/vercel.json`.** Vercel auto-detects Next.js, and the only routing rule (`/api/*` → `BACKEND_URL`) already lives in `next.config.ts` where it also works under `next dev`. A `vercel.json` copy would be a second definition that can silently drift.
3. **Python pin is `backend/runtime.txt` = `python-3.11.9`**, not `.python-version`. `runtime.txt` is read identically by Railway's Nixpacks, Render and Heroku, so it survives a host change; `.9` matches the owner's local interpreter (`docs/PLAN.md` §0).
4. **Supabase Storage download uses `GET /storage/v1/object/{bucket}/{key}`**, not the `/object/authenticated/{bucket}/{key}` alias. Both accept the service-role bearer token; the plain form is the same path used for upload and delete, which keeps `_path()` to one line and the mock-transport assertions unambiguous. The `authenticated/` alias exists for end-user JWTs, which this backend never holds.
5. **Uploads use `POST` with `x-upsert: true`** rather than `PUT`. Re-running the seed script or retrying an upload then overwrites instead of failing, which is what makes `scripts/seed_demo.py` safely idempotent.
6. **`SupabaseStorage.save()` returns the key it was given**, matching what `LocalStorage` must also satisfy (Task 6 Step 2 adds a round-trip test for both). `AdDataUpload.file_path` therefore keeps holding a storage key, and swapping backends needs no data migration.
7. **`StorageError`** is added to `services/storage.py` — a small addition to the `INTERFACES.md` Stage 8 block, recorded there in Task 6 Step 8. Nothing existing is renamed.
8. **`CorsMisconfiguredError` is raised at startup** rather than logged. A wildcard CORS policy on a cookie-authenticated API is a security failure, and browsers reject `*` with credentials anyway, so failing the boot is both safer and more honest than a warning nobody reads.
9. **`cors_origins` is parsed from a comma-separated env var** using `pydantic_settings.NoDecode` plus a `mode="before"` validator. The alternative — pydantic-settings' default JSON decoding — would force operators to type `["https://..."]` into a Railway variable box, which is an easy and silent mistake.
10. **`instrumentation-client.ts` is added alongside `sentry.client.config.ts`.** Next.js 15.3+ loads browser instrumentation from `instrumentation-client.ts`; the file is a single `import "./sentry.client.config";`, so the three filenames named in the Stage 8 contract stay authoritative and the config has one home.
11. **`traces_sample_rate` / `tracesSampleRate` are 0 on both sides.** Stage 8 is about knowing when something breaks, not performance tracing. Turning tracing on later is a one-line change once there is traffic worth sampling.
12. **`numReplicas = 1` on Railway.** Analysis runs in an in-process `BackgroundTasks` (`docs/PLAN.md` §0, no Celery for the MVP), so a second replica could not see a run queued on the first. Scaling past one replica is the signal to add the queue.
13. **Migrations run in the start command, not the build.** The build has no `DATABASE_URL`; the start command does, and Alembic is a no-op when the schema is already at head.
14. **`python -m scripts.seed_demo`, with `backend/scripts/__init__.py`.** Making `scripts` a package lets the test import `main()` directly instead of exec'ing a file path, and avoids a `sys.path` hack that ruff would flag as `E402`. `python scripts/create_admin.py` from Stage 2 keeps working unchanged.
15. **The demo admin is `admin@example.com`, created with `create_admin`** (never via signup — `docs/PLAN.md` §5). Both demo accounts share `DEMO_PASSWORD`, and the script refuses to run without it rather than defaulting to something guessable.
16. **Policy copy is skeleton text with `TODO-OWNER` markers**, not lorem ipsum and not invented legal terms. Every clause that needs a real decision (dates, fee numbers, retention, liability, governing law) is marked; a test asserts `TODO-OWNER` is present, so the day the owner finishes the copy that test fails and forces the marker's removal.

---

## Self-review notes

- **Spec coverage, `docs/PLAN.md` §6 Stage 8, bullet by bullet.** "Sentry (backend and frontend)" → Tasks 4, 5. "security headers" → Task 2. "CORS locked to the frontend origin" → Task 3. "request size limits" → Task 3. "structured logging" → Task 2. "Supabase Postgres (backups on)" → Task 7 (pooling) + README Deploy §1 step 3 (backups). "backend on Railway or Render" → Task 8 (Railway, Decision 1). "frontend on Vercel" → Task 5/8 env examples + README Deploy §4. "S3-compatible file storage" → Task 6 (Supabase Storage, §7 #3's named choice). "Seeded demo client for sales demos" → Task 9. "Smoke-test checklist in the README" → Task 11 Step 4. "Terms, Privacy and Refund policy pages (you supply the wording)" → Task 10, with `TODO-OWNER` as the supplied-by-owner marker. "Done when: the full flow works in production" → the smoke-test checklist mirrors the bullet's exact sequence.
- **Spec coverage, other sections.** §0 (Windows, no Docker): every command is Git Bash with `.venv/Scripts/...`, and no Docker appears anywhere. §7 #3: Mumbai `ap-south-1`, Free dev / Pro prod, plain Postgres through SQLAlchemy and Alembic, private Storage buckets, service key backend-only — all in Global Constraints, Task 6 and README Deploy §1. §8 risks: the audit-log and config-snapshot mitigations are Stage 6/1 work already done; this stage adds the deploy-time half (backups on, private buckets, a smoke test that checks tenant isolation and TID reuse). §9 is explicitly out of scope and is named as such in the header.
- **`INTERFACES.md` Stage 8 block, name by name.** `sentry_dsn`, `cors_origins`, `max_request_mb`, `supabase_url`, `supabase_service_key`, `storage_bucket` → Task 1, spelled exactly. `app/core/middleware.py` with "security headers, request-size limit, request-id + structured JSON logging" → Tasks 2–3. `SupabaseStorage(StorageBackend)` in `services/storage.py` → Task 6. "Deploy files: backend/Procfile (uvicorn), backend/railway.toml or render.yaml, frontend on Vercel (BACKEND_URL env), .env.production examples" → Tasks 5 and 8. `scripts/seed_demo.py: demo client + sample upload + approved run` → Task 9. "Frontend routes: /terms, /privacy, /refunds … placeholders marked TODO-OWNER are allowed ONLY for legal copy" → Task 10. "README: smoke-test checklist" → Task 11. The one addition is `StorageError`, flagged in Decision 7 and written back into `INTERFACES.md` by Task 6 Step 8.
- **Type and name consistency across tasks.** `REQUEST_ID_HEADER` is defined once in Task 2 and imported by Tasks 2, 3 and the CORS `expose_headers`. `configure_logging`, `SecurityHeadersMiddleware`, `RequestContextMiddleware` (Task 2) and `RequestSizeLimitMiddleware` (Task 3) are all registered in the single `create_app()` shown in full in Task 3 Step 4, then extended by exactly one line (`_init_sentry(settings)`) in Task 4 Step 5 — no other task edits that function. `StorageError` is raised by both `SupabaseStorage` and `get_storage()` and asserted in both places. `Settings.storage_backend` / `storage_root` / `max_upload_mb` are consumed but never redefined (they are Stage 3's). `main() -> int` in Task 9 is the same symbol the Task 9 tests import and the README invokes. `PolicyLayout` takes `{ title, updated, children }` in Task 10 Step 5 and is called with exactly those props by all three pages in Step 6.
- **Placeholder scan.** The only `TODO-OWNER` strings are inside the three policy pages, which the Global Constraints and `INTERFACES.md` both license. `<angle-bracket>` values appear only inside `.env.*.example` files, which is what an example file is for. No "TBD", no "add error handling", no "similar to Task N" — the `create_app()` body, the middleware classes and the seed script are each written out in full at the point of use.
- **Deliberate non-goals.** No rate-limit changes (Stage 2 owns slowapi). No Content-Security-Policy header: the API serves JSON only, and the pages are served by Vercel where a CSP belongs with the frontend's script inventory — adding a half-guessed CSP here would break the R3F hero from Stage 4. No `render.yaml`, no `vercel.json`, no Docker, no queue, no payment gateway.
