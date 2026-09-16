# Cross-Stage Interface Contract

Every implementation plan under `docs/superpowers/plans/` uses these exact names, paths and
signatures. A plan may add to this list (and must say so in its header) but never rename
what is here. Spec authority: `docs/PLAN.md`.

## Already built (Stage 0, branch `stage-0-scaffold`)

| Thing | Where | Signature / shape |
|---|---|---|
| Settings | `backend/app/core/settings.py` | `Settings(env: "dev"\|"test"\|"prod", database_url: str, secret_key: str)`; `get_settings()` lru-cached |
| DB | `backend/app/core/db.py` | `Base` (naming convention on metadata), `make_engine(url)`, `get_engine()`, `get_session()` FastAPI dependency yielding `Session` |
| Types | `backend/app/models/_types.py` | `JSONVariant`, `Money = Numeric(14,2)`, `utcnow()` |
| Models | `backend/app/models/*.py`, re-exported from `app.models` | `User, Client, AdDataUpload, AnalysisRun, WasteReport, SegmentMetric, Recommendation, Invoice, PaymentMethod, Payment, AuditLog` — columns exactly as `docs/PLAN.md` §4 |
| App factory | `backend/app/main.py` | `create_app() -> FastAPI`; routers are included inside it; `GET /api/health` |
| Test fixtures | `backend/tests/conftest.py` | `client` (TestClient over `create_app()`), `session` (in-memory SQLite, all tables) |
| Migrations | `backend/alembic/` | `alembic upgrade head`; new tables/columns need a new revision |
| Frontend | `frontend/` (Next.js 16, App Router, `src/`, Tailwind v4) | tokens `--color-ink/surface/teal/coral/paper/slate`, fonts `--font-display` (Space Grotesk) / `--font-body` (Inter); `/api/*` rewritten to `BACKEND_URL` |

Enum string values (VARCHAR, non-native): `User.role` ∈ client/admin · `AdDataUpload.status` ∈ uploaded/validated/failed · `AnalysisRun.status` ∈ queued/running/done/failed · `AnalysisRun.review_status` ∈ pending/approved/rejected · `Invoice.status` ∈ draft/issued/payment_submitted/paid/void · `PaymentMethod.type` / `Payment.method_type` ∈ jazzcash/easypaisa/nayapay/raast/bank_iban · `Payment.status` ∈ pending/confirmed/rejected.

## Stage 1 — pipeline (`backend/app/pipeline/`, pure; no DB/web imports)

```python
PipelineConfig                      # frozen dataclass; .from_overrides(dict) ; .to_dict()
DIMENSIONS = ("placement", "age_group", "time_slot")
load_csv(source, config=None) -> LoadResult(df, errors: list[RowIssue], warnings, row_count, date_range, ok)
RowIssue(row: int|None, column: str|None, message: str)
analyze_all_dimensions(df, config) -> dict[str, DimensionResult]
DimensionResult(dimension, benchmark_cpa, total_spend, total_wasted_spend, segments: list[SegmentMetrics], flagged)
SegmentMetrics(segment, spend, impressions, clicks, conversions, revenue, cpa, ctr, cvr, roas,
               is_significant, is_flagged, wasted_spend, flag_reason)
build_recommendations(results, config) -> list[Recommendation(dimension, segment_name, current_spend, recommended_cut, reason)]
headline_waste(results) -> float
calculate_fee(base_fee: Decimal, performance_fee_pct: Decimal, confirmed_recovered_waste: Decimal, cap=None) -> FeeBreakdown
generate_dataset(days, seed, waste) -> DataFrame ; write_sample_csv(path, **kw)
```

## Stage 2 — auth

```python
# backend/app/core/security.py
hash_password(plain: str) -> str                      # pwdlib Argon2
verify_password(plain: str, hashed: str) -> bool
create_access_token(user_id: int, role: str) -> str   # PyJWT HS256, exp = now + ACCESS_TOKEN_MINUTES
create_refresh_token(user_id: int) -> str             # exp = now + REFRESH_TOKEN_DAYS, claim "typ": "refresh"
decode_token(token: str) -> TokenPayload(sub: int, role: str | None, typ: "access"|"refresh", exp: int)  # raises InvalidTokenError
# Settings gains: access_token_minutes: int = 15, refresh_token_days: int = 7, cookie_secure: bool (True when env == "prod")
# Cookies: "access_token", "refresh_token"; httpOnly; SameSite=Lax; Secure=cookie_secure; path "/"

# backend/app/core/deps.py
get_current_user(request: Request, session: Session = Depends(get_session)) -> User   # 401 if missing/invalid/inactive
require_admin(user: User = Depends(get_current_user)) -> User                          # 403 unless role == "admin"
require_client(user: User = Depends(get_current_user), session=Depends(get_session)) -> Client  # 403 unless role == "client"; loads the Client row
CurrentClient = Annotated[Client, Depends(require_client)]
CurrentAdmin  = Annotated[User, Depends(require_admin)]

# backend/app/schemas/auth.py
SignupRequest(email: EmailStr, password: str(min 8), business_name: str(1..200))
LoginRequest(email: EmailStr, password: str)
UserOut(id, email, role, created_at) ; MeOut(user: UserOut, client: ClientOut | None)
ClientOut(id, business_name, base_fee: Decimal, performance_fee_pct: Decimal)

# backend/app/services/auth.py
signup_client(session, email, password, business_name) -> User        # creates User(role=client) + Client(base_fee, performance_fee_pct from PipelineConfig defaults); raises EmailTakenError
authenticate(session, email, password) -> User | None
create_admin(session, email, password) -> User                        # used only by scripts/create_admin.py

# backend/app/routers/auth.py  (prefix /api/auth)
POST /signup -> 201 MeOut + cookies · POST /login -> 200 MeOut + cookies (slowapi 5/minute) ·
POST /logout -> 204 clears cookies · POST /refresh -> 200 rotates both cookies · GET /me -> MeOut
# Errors: 401 {"detail": "invalid credentials"}; 409 {"detail": "email already registered"}; 422 pydantic
# Rate limiting: slowapi Limiter keyed by remote address, attached in create_app(); exceeded -> 429
# scripts/create_admin.py  --email --password
```

## Stage 3 — uploads, analysis runs, reports

```python
# backend/app/services/storage.py
class StorageBackend(Protocol): save(key: str, data: bytes) -> str; read(key: str) -> bytes; delete(key: str) -> None
LocalStorage(root: Path)               # dev/test; keys like "uploads/{client_id}/{sha256}.csv", "proofs/{client_id}/{payment_id}.{ext}"
get_storage() -> StorageBackend        # from Settings.storage_backend ("local" now; "supabase" in Stage 8) and storage_root
# Settings gains: storage_backend: str = "local", storage_root: str = "./storage", max_upload_mb: int = 20

# backend/app/services/upload.py
create_upload(session, client: Client, filename: str, data: bytes) -> AdDataUpload
#   409 DuplicateUploadError if same sha256 for this client; runs load_csv; status validated|failed; validation_report = {"errors": [...], "warnings": [...]} (RowIssue as dicts)
list_uploads(session, client_id) -> list[AdDataUpload] ; get_upload(session, client_id, upload_id) -> AdDataUpload  # 404 NotFound if other tenant
template_csv() -> bytes                # header row + 3 example rows

# backend/app/services/analysis.py
create_run(session, client: Client, upload_id: int) -> AnalysisRun                  # status queued; config_snapshot = PipelineConfig.from_overrides(client.config_overrides).to_dict()
execute_run(run_id: int) -> None                                                     # background task; opens its own session; loads CSV from storage; analyze → persist WasteReport(1/dimension) + SegmentMetric + Recommendation; sets headline_waste, status done|failed (+error_message)
get_run(session, client_id, run_id) -> AnalysisRun                                   # 404 cross-tenant
get_report(session, client_id, run_id) -> ReportOut                                  # 404 unless run.status == done AND review_status == approved (clients only see approved)
latest_report(session, client_id) -> ReportOut | None

# backend/app/schemas/reports.py
SegmentOut(segment, spend, impressions, clicks, conversions, revenue, cpa, ctr, cvr, roas, is_significant, is_flagged, wasted_spend, flag_reason)
DimensionOut(dimension, benchmark_cpa, total_spend, total_wasted_spend, segments: list[SegmentOut])
RecommendationOut(id, dimension, segment_name, current_spend, recommended_cut, reason)
ReportOut(run_id, upload_id, generated_at, date_range_start, date_range_end, total_spend, headline_waste, recovery_pct, dimensions: list[DimensionOut], recommendations: list[RecommendationOut], config_snapshot: dict)
#   recovery_pct = headline_waste / total_spend * 100 (0 when total_spend == 0)
UploadOut(id, uploaded_at, original_filename, row_count, date_range_start, date_range_end, status, validation_report)
RunOut(id, upload_id, status, review_status, headline_waste, error_message, created_at)

# Routers: /api/uploads (POST multipart "file", GET list, GET /{id}, GET /template.csv)
#          /api/analyze/{upload_id} -> 202 RunOut ; /api/runs/{id} -> RunOut
#          /api/reports/latest ; /api/reports/{run_id}
# All client routes depend on CurrentClient and pass client.id into every service call; never accept client_id from the request.
```

## Stage 4 — client dashboard (frontend)

```ts
// src/lib/api.ts
apiFetch<T>(path: string, init?: RequestInit): Promise<T>   // credentials: "include"; throws ApiError(status, detail)
// src/lib/format.ts
formatPKR(n: number): string          // "Rs. 84,000"  ; formatPct(n): "12.4%"
// src/lib/types.ts — TS mirrors of ReportOut, DimensionOut, SegmentOut, RecommendationOut, UploadOut, RunOut, MeOut, InvoiceOut, PaymentMethodOut
// Routes: /login, /signup, /dashboard (summary + hero), /dashboard/upload, /dashboard/reports/[runId], /dashboard/billing
// Components: components/hero/FlowStatic.tsx (SVG), components/hero/FlowParticles.tsx (R3F, dynamic ssr:false), components/hero/Hero.tsx (chooses by prefers-reduced-motion),
//   components/tables/SegmentTable.tsx, components/recommendations/RecommendationList.tsx (Framer Motion expand), components/ui/*
// Auth guard: server component reads cookies and calls GET /api/auth/me; redirect to /login on 401
```

## Stage 5 — PDF

```python
# backend/app/services/pdf.py  (ReportLab; charts drawn with reportlab.graphics — no matplotlib)
build_report_pdf(report: ReportOut, business_name: str) -> bytes
# GET /api/reports/{run_id}/pdf -> application/pdf, Content-Disposition attachment; approved runs only (same rule as get_report)
```

## Stage 6 — admin

```python
# backend/app/services/audit.py
record(session, actor_user_id: int | None, action: str, entity_type: str, entity_id: int, before: dict | None, after: dict | None) -> AuditLog
# actions: "run.approve", "run.reject", "client.update", "invoice.draft", "invoice.confirm", "invoice.issue", "invoice.void", "payment.confirm", "payment.reject", "payment_method.create", "payment_method.update"

# backend/app/services/admin.py
list_clients(session) ; get_client(session, client_id) ; update_client(session, actor, client_id, patch: ClientPatch)   # base_fee, performance_fee_pct, config_overrides (validated via PipelineConfig.from_overrides)
list_runs(session, review_status: str | None) ; approve_run(session, actor, run_id, note) ; reject_run(session, actor, run_id, note)

# backend/app/services/billing.py
suggest_recovered_waste(session, client_id, period_start, period_end) -> Decimal
#   = Σ over segments flagged in the latest approved run BEFORE period_start of max(0, waste_then − waste_now) using the latest approved run INSIDE the period; 0 if either run is missing
draft_invoice(session, actor, client_id, period_start, period_end) -> Invoice       # status draft; base_fee from client; suggested_recovered_waste; performance_fee via calculate_fee; invoice_number "INV-{YYYY}-{NNNN}" sequential
confirm_invoice(session, actor, invoice_id, confirmed_recovered_waste: Decimal) -> Invoice   # recomputes performance_fee + total; status stays draft
issue_invoice(session, actor, invoice_id, due_date) -> Invoice                       # draft -> issued, sets issued_at
void_invoice(session, actor, invoice_id, note) -> Invoice
# Routers: /api/admin/... exactly as docs/PLAN.md §5; all depend on CurrentAdmin. Frontend: /admin, /admin/clients/[id], /admin/runs, /admin/invoices, /admin/audit
```

## Stage 7 — manual payments

```python
# backend/app/payments/base.py
PaymentInstruction(method_type, account_title, account_identifier, instructions)
class PaymentProvider(Protocol):
    name: str
    instructions_for(session, invoice: Invoice) -> list[PaymentInstruction]
    submit(session, client: Client, invoice: Invoice, submission: PaymentSubmission, proof: bytes | None, proof_ext: str | None) -> Payment
# backend/app/payments/manual.py : ManualProvider (name "manual") — instructions from active PaymentMethod rows ordered by sort_order; submit() creates Payment(status pending), 409 on duplicate (method_type, transaction_ref), invoice.status -> payment_submitted
get_payment_provider() -> PaymentProvider    # Settings.payment_provider = "manual"

# backend/app/services/payments.py
confirm_payment(session, actor, payment_id, note) -> Payment   # status confirmed; invoice.amount_paid += amount; invoice.status = paid when amount_paid >= total (else issued); audit
reject_payment(session, actor, payment_id, note) -> Payment    # status rejected; invoice.status back to issued if no other pending payments
list_pending_payments(session) ; list_invoices(session, client_id) ; get_invoice(session, client_id, invoice_id)
build_invoice_pdf(invoice: Invoice, client: Client, instructions: list[PaymentInstruction]) -> bytes
# schemas: PaymentSubmission(method_type, transaction_ref: str(1..80), amount: Decimal > 0, paid_at: date) ; PaymentOut ; InvoiceOut(..., payments: list[PaymentOut], instructions: list[PaymentInstruction]) ; PaymentMethodOut/PaymentMethodIn
# Routers: /api/billing/invoices, /api/billing/invoices/{id}, /api/billing/invoices/{id}/pdf, /api/billing/payment-methods, POST /api/billing/invoices/{id}/payments (multipart: fields + optional "proof" image/pdf ≤ 5 MB)
#          /api/admin/payments?status=pending, POST /api/admin/payments/{id}/confirm|reject, GET/POST/PATCH /api/admin/payment-methods
# Frontend: /dashboard/billing (invoice list, detail, submit-payment form), /admin/payments, /admin/payment-methods
```

## Stage 8 — hardening & deploy

```
Settings gains: sentry_dsn: str | None, cors_origins: list[str], max_request_mb: int = 25, supabase_url, supabase_service_key, storage_bucket
app/core/middleware.py: security headers, request-size limit, request-id + structured JSON logging
SupabaseStorage(StorageBackend) in services/storage.py (Supabase Storage REST, service key, private bucket)
Deploy files: backend/Procfile (uvicorn), backend/railway.toml or render.yaml, frontend on Vercel (BACKEND_URL env), .env.production examples
scripts/seed_demo.py: demo client + sample upload + approved run
Frontend routes: /terms, /privacy, /refunds (content supplied by owner; placeholders marked TODO-OWNER are allowed ONLY for legal copy)
README: smoke-test checklist
```

## Test-fixture contract (backend, binding for Stages 2–8)

One database-wiring mechanism only: the **bound engine**. `tests/conftest.py` defines
`bound_engine` — an in-memory SQLite engine on `StaticPool` with `Base.metadata.create_all`
applied, monkeypatched into `app.core.db` as the module-level engine/session factory so that
BOTH the `get_session` dependency AND `session_scope()` (background tasks) hit the same DB.
There is no separate dependency-override engine.

```
tests/conftest.py            client (Stage 0, health only) · session (Stage 0, ORM-only tests) · bound_engine
tests/api/conftest.py        api_env (autouse: bound_engine + tmp storage root + test settings)
                             db: Session                       — bound to bound_engine
                             api: TestClient                   — create_app() on the bound engine, NOT logged in
                             client_a, client_b: TestClient    — logged-in tenants (signed up via POST /api/auth/signup)
                             client_a_row, client_b_row: Client
                             admin_client: TestClient          — logged in as an admin created via services.auth.create_admin
                             rate_limited_client: TestClient   — the only fixture with slowapi enabled (Stage 2)
tests/api/helpers.py         TEST_PASSWORD = "correct horse battery staple"
                             login_as(api: TestClient, user: User) -> None        # POST /api/auth/login with TEST_PASSWORD
                             make_client(db, email, business_name="Biz") -> Client # User(role=client, TEST_PASSWORD hash) + Client
                             make_admin(db, email="admin@example.com") -> User
                             make_upload(db, client, *, status="validated") -> AdDataUpload
                             make_run(db, client, upload=None, *, status="done", review_status="pending") -> AnalysisRun
                             make_approved_run(db, client, *, with_report=True) -> AnalysisRun   # + WasteReport/SegmentMetric/Recommendation rows with the Stage 1 optimizer test numbers
                             make_invoice(db, client, *, status="issued", total=Decimal("19600.00")) -> Invoice
                             make_method(db, type="jazzcash", identifier="03001234567") -> PaymentMethod
```
Rules: no plan defines a second `login_as`, `db`, or `client_a`; a stage that needs a new helper
ADDS it to `tests/api/helpers.py` under these naming patterns and declares it in its header.
`POST /api/uploads` on a rejected file answers `422 {"detail": {"status": "failed", "upload_id": int, "errors": RowIssue[], "warnings": RowIssue[]}}`.

Additions made during plan reconciliation (2026-09-16), binding: `user_for(db, client) -> User` in `tests/api/helpers.py` (models declare no relationships); `admin_row: User` fixture mirroring `client_a_row`; widened keyword args — `make_client(db, email="client@example.com", business_name="Biz", *, is_active, base_fee, performance_fee_pct, config_overrides)`, `make_run(..., *, status, review_status, created_at, headline_waste, segments)`, `make_approved_run(db, client, *, with_report=True, status="done", review_status="approved")`. Tests call `db.expire_all()` before reading rows back after an HTTP request.

Stage 0 close-out additions (2026-09-16, binding): `app.core.db.configure_engine(engine)` / `reset_engine()` are the public hooks for tests — the `bound_engine` fixture MUST call `configure_engine(engine)` (and `reset_engine()` on teardown) instead of poking `_engine`/`_session_factory`, and MUST register the `PRAGMA foreign_keys=ON` connect listener exactly as `tests/conftest.py`'s `session` fixture does. `pytest` is runnable bare from `backend/` (`pythonpath = ["."]`, `tests/__init__.py` exists). Enum values are enforced with Pydantic `Literal` types at every write path; DB-level CHECK constraints are a Stage 8 backlog item.
