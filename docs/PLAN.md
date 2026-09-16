# Ad Spend Optimization — Build Plan

Source spec: `Product_Plan_And_Build_Prompt.pdf`. This plan follows the spec's stack and build order.
It adds the details the spec leaves open and fixes a few spec issues that would cause wrong numbers or billing disputes.

Each stage ends with a **checkpoint**: you review and test it, and nothing moves to the next stage until you approve.

Step-by-step implementation plans (Superpowers `writing-plans` format, one per stage) live in `docs/superpowers/plans/`: `INTERFACES.md` (the cross-stage contract every plan follows), then Stage 0 `2026-09-15-stage-0-scaffold-and-models.md`, Stage 1 `2026-09-15-stage-1-analysis-pipeline.md`, Stage 2 `2026-09-16-stage-2-auth.md`, Stage 3 `2026-09-16-stage-3-upload-and-analysis-api.md`, Stage 4 `2026-09-16-stage-4-client-dashboard.md`, Stage 5 `2026-09-16-stage-5-pdf-report.md`, Stage 6 `2026-09-16-stage-6-admin-panel.md`, Stage 7 `2026-09-16-stage-7-manual-billing.md`, Stage 8 `2026-09-16-stage-8-hardening-and-deploy.md`. Build status: Stage 0 Tasks 1–6 are implemented and reviewed on branch `stage-0-scaffold` (Task 7 frontend left uncommitted, Task 8 CI not started).

---

## 0. Your machine (checked 2026-09-10)

| Tool | Status | What it means for the plan |
|---|---|---|
| Python 3.11.9 | installed | Backend target: Python 3.11 |
| Node 24 / npm 11 | installed | Frontend: Next.js (latest stable), TypeScript |
| git | installed | Run `git init` in Stage 0 |
| Docker | **missing** | No docker-compose. Run services natively or in the cloud |
| PostgreSQL | **missing** | **Decided: Supabase** (hosted Postgres, nothing to install). Two projects in the Mumbai (`ap-south-1`) region: `dev` on the Free plan and `prod` on Pro |
| Redis | **missing** | No Celery for the MVP. Use FastAPI `BackgroundTasks`, and add a queue later if needed |

---

## 1. Changes to the spec (and why)

1. **Waste must not be added up across dimensions.** The same rupee shows up in the placement, age_group and time_slot breakdowns at once. Summing the three counts it three times, and that inflates the performance fee. The headline "total estimated waste" will be the **largest single-dimension total**, with every dimension shown separately.
2. **Benchmark against the account average, not the best segment.** The spec compares each segment to the best segment's CPA. A small segment with 2 conversions at a low CPA would make everything else look wasteful. Default benchmark: the dimension's overall CPA across significant segments. "Best significant segment" stays available as a config option (`BENCHMARK_MODE`).
3. **Real ad exports don't fit a single flat CSV.** Meta limits which breakdowns you can combine in one export: time-of-day usually can't be combined with age or placement. The loader will accept rows where some dimensions are blank, and each dimension is analyzed only on rows that have it. Stage 3 also adds a downloadable template CSV. Header mapping for real Meta/Google export columns is also planned for Stage 3.
4. **New tables in the data model:**
   - `analysis_runs`: one per upload analysis, holding a **config snapshot**. The admin approves the run, not three separate per-dimension reports.
   - `segment_metrics`: the per-segment numbers behind the breakdown table.
   - `payment_methods` and `payments`: the accounts clients pay into (JazzCash, Easypaisa, NayaPay, bank via Raast), and each payment a client reports with its transaction ID. No subscriptions or webhooks in the MVP (see Stage 7).
   - `audit_log`: records every approval and fee confirmation, so disputes can be settled.
5. **"Recovered waste" needs a definition.** A recommended cut is not recovered money. Proposed definition: waste on previously flagged segments in the baseline period, minus waste on those same segments in the current period. The system calculates a **suggested** amount and the admin confirms or edits it before it reaches an invoice.
6. **Money is stored as `NUMERIC(14,2)` PKR and fees are calculated with `Decimal`.** No floats go into invoices. pandas floats are fine inside the analysis, then values are rounded at the boundary.
7. **PDFs use ReportLab, not WeasyPrint.** WeasyPrint needs GTK on Windows, which is painful to install. ReportLab is pure Python. Charts in the PDF are drawn with `reportlab.graphics` (no matplotlib dependency).
8. **The frontend proxies `/api/*` to FastAPI through Next.js rewrites.** Auth cookies then stay first-party even when Vercel and Railway are on different domains.
9. **Files go behind a storage interface.** Local `./storage` in dev, S3-compatible storage in prod (Supabase Storage or Cloudflare R2). Railway and Render disks are wiped on redeploy.

---

## 2. Repository layout

```
ad-optimizer-project/
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI app, routers, middleware
│   │   ├── core/                   # settings (env), db session, security (JWT, hashing), errors, rate limiting
│   │   ├── models/                 # SQLAlchemy models
│   │   ├── schemas/                # Pydantic request/response models
│   │   ├── routers/                # auth, uploads, analysis, reports, admin, billing, webhooks
│   │   ├── services/               # upload, analysis, report, pdf, billing, storage, audit
│   │   ├── payments/               # PaymentProvider interface: ManualProvider now, an automatic gateway later
│   │   └── pipeline/               # PURE analysis logic: no DB, no web imports
│   │       ├── config.py
│   │       ├── loader.py
│   │       ├── analyzer.py
│   │       ├── optimizer.py
│   │       └── data_generator.py   # synthetic CSVs with known, injected waste
│   ├── alembic/                    # migrations
│   ├── scripts/                    # create_admin.py, generate_sample_data.py
│   ├── tests/
│   │   ├── pipeline/               # unit + golden tests (highest priority)
│   │   ├── api/                    # endpoint + tenant-isolation tests
│   │   └── fixtures/               # test CSVs
│   ├── requirements.txt / requirements-dev.txt
│   ├── pyproject.toml              # ruff + pytest config
│   └── .env.example
├── frontend/
│   ├── src/app/
│   │   ├── (auth)/login, signup
│   │   ├── dashboard/              # summary + hero, upload, reports/[id], billing
│   │   └── admin/                  # clients, runs (approval queue), invoices, settings
│   ├── src/components/             # hero/, tables/, recommendations/, ui/
│   ├── src/lib/                    # api client, auth helpers, PKR formatting
│   └── package.json
├── .github/workflows/ci.yml        # pytest + ruff + frontend lint/typecheck/build
├── docs/PLAN.md
└── README.md
```

---

## 3. Analysis methodology (Stage 1 builds this)

All thresholds live in `pipeline/config.py` as defaults. The admin can override them per client (stored in the DB). **Every run saves the effective config**, so any report can be reproduced exactly.

### loader.py
- Required columns: `date, campaign_id, placement, age_group, gender, device, time_slot, spend, impressions, clicks, conversions, revenue`.
- Hard errors (reject the file): missing columns, unparseable dates or numbers, negative values, `clicks > impressions`, empty file, file larger than `MAX_UPLOAD_MB`, more than `MAX_ROWS` rows.
- Warnings (accept, but report): `conversions > clicks` (view-through conversions make this legitimate), duplicate rows, unknown category values.
- Normalizes category strings (trim, lowercase, alias map). `time_slot` accepts hour `0–23` and is bucketed using `TIME_SLOT_BUCKETS` from config.
- Returns a clean DataFrame and a validation report with row numbers, so the UI can show exactly what is wrong.

### analyzer.py — per dimension
1. `groupby(dimension)` → spend, impressions, clicks, conversions, revenue, CPA, CTR, CVR, ROAS.
2. **Significant** segment: `spend ≥ MIN_SPEND` and `clicks ≥ MIN_CLICKS`. Segments that aren't significant are shown but never flagged.
3. **Benchmark CPA** (`BENCHMARK_MODE`):
   - `account_avg` (default): total spend ÷ total conversions across significant segments **that have at least one conversion**. Zero-conversion segments are excluded from the benchmark (they say nothing about what a conversion normally costs, and including their spend would raise the benchmark and hide real waste); they are still flagged separately by rule 4.
   - `best`: lowest CPA among significant segments with at least `MIN_CONVERSIONS_FOR_BEST` conversions.
4. **Flag** a segment when `CPA > WASTE_MULTIPLIER × benchmark`, or when it has zero conversions and `spend ≥ MIN_SPEND_ZERO_CONV`.
5. **Wasted spend** for a flagged segment = `spend − conversions × benchmark_CPA`, floored at 0. This is the spend beyond what those conversions should have cost. A zero-conversion segment counts its entire spend as waste.

### optimizer.py
- `build_recommendations()`: `recommended_cut = min(wasted_spend, MAX_CUT_PCT × segment_spend)`. Each recommendation carries a plain-language reason built from the real numbers, for example: *"Audience Network spent Rs. 84,000 at Rs. 2,100 per conversion — 2.6× your average of Rs. 800. Cut Rs. 50,400 (60%)."*
- `headline_waste()`: the largest per-dimension waste total (see §1.1).
- `calculate_fee(base_fee, performance_fee_pct, confirmed_recovered_waste, cap=None)`: uses `Decimal` and returns a line-item breakdown.

### Test strategy
- `data_generator.py` produces CSVs with **known** injected waste (for example, one placement at 3× the average CPA). Golden tests assert that the analyzer finds exactly those segments and the expected rupee amounts.
- Edge-case fixtures: zero conversions everywhere, a single segment, all segments below significance, a dimension present on only some rows, very large files.
- Coverage target for `pipeline/`: ≥ 90%.

---

## 4. Data model

| Table | Columns |
|---|---|
| users | id, email (unique), password_hash, role (`client`/`admin`), is_active, created_at |
| clients | id, user_id, business_name, contact_info, pricing_model, base_fee, performance_fee_pct, config_overrides (JSONB), created_at |
| ad_data_uploads | id, client_id, uploaded_at, original_filename, file_path, file_sha256, row_count, date_range_start, date_range_end, status (`uploaded/validated/failed`), validation_report (JSONB) |
| analysis_runs | id, client_id, upload_id, config_snapshot (JSONB), status (`queued/running/done/failed`), review_status (`pending/approved/rejected`), headline_waste, reviewed_by, reviewed_at, review_note, created_at |
| waste_reports | id, run_id, client_id, upload_id, dimension, total_spend, total_wasted_spend, benchmark_cpa, generated_at |
| segment_metrics | id, report_id, segment_value, spend, impressions, clicks, conversions, revenue, cpa, is_significant, is_flagged, wasted_spend |
| recommendations | id, report_id, dimension, segment_name, current_spend, recommended_cut, reason |
| invoices | id, invoice_number (unique, e.g. `INV-2026-0001`), client_id, period_start, period_end, due_date, base_fee, suggested_recovered_waste, confirmed_recovered_waste, performance_fee, total, amount_paid, status (`draft/issued/payment_submitted/paid/void`), confirmed_by, issued_at, created_at |
| payment_methods | id, type (`jazzcash/easypaisa/nayapay/raast/bank_iban`), account_title, account_identifier (wallet number, Raast ID or IBAN), instructions, is_active, sort_order |
| payments | id, invoice_id, client_id, method_type, transaction_ref, amount, paid_at, proof_file_path (optional screenshot), status (`pending/confirmed/rejected`), reviewed_by, reviewed_at, review_note, provider (`manual` now), created_at. **Unique `(method_type, transaction_ref)`** so one transaction ID can't be reused |
| audit_log | id, actor_user_id, action, entity_type, entity_id, before (JSONB), after (JSONB), created_at |

Indexes: `client_id` on every client-owned table, plus `(client_id, created_at)` and `(client_id, period_start)`.

**Tenant isolation:**
- Client-facing endpoints never take a `client_id` from the request. It comes from the JWT through a dependency.
- Every service function requires `client_id` and filters by it in SQL.
- Another client's record returns **404** (not 403), so IDs can't be probed.
- Clients only ever see runs with `review_status = approved`.
- Dedicated tests try to read client B's data as client A on every endpoint.

---

## 5. API surface

```
Auth        POST /api/auth/signup (client only) · POST /api/auth/login · POST /api/auth/logout
            POST /api/auth/refresh · GET /api/auth/me
Uploads     POST /api/uploads · GET /api/uploads · GET /api/uploads/{id} · GET /api/uploads/template.csv
Analysis    POST /api/analyze/{upload_id} → 202 + run_id · GET /api/runs/{id} (status polling)
Reports     GET /api/reports/latest · GET /api/reports/{run_id} · GET /api/reports/{run_id}/pdf
Billing     GET /api/billing/invoices · GET /api/billing/invoices/{id} · GET /api/billing/invoices/{id}/pdf
            GET /api/billing/payment-methods · POST /api/billing/invoices/{id}/payments (TID, amount, date, optional proof)
Admin       GET /api/admin/clients · GET/PATCH /api/admin/clients/{id} (fees, config overrides)
            GET /api/admin/runs?review_status=pending · POST /api/admin/runs/{id}/approve|reject
            POST /api/admin/invoices (drafts for a period) · POST /api/admin/invoices/{id}/confirm|issue|void
            GET /api/admin/payments?status=pending · POST /api/admin/payments/{id}/confirm|reject
            GET/POST/PATCH /api/admin/payment-methods
            GET /api/admin/audit-log
```

Auth details:
- Access JWT (about 15 minutes) and refresh token, both in `httpOnly; Secure; SameSite=Lax` cookies.
- Passwords hashed with argon2 via `pwdlib`.
- Login is rate-limited with `slowapi`.
- **Admins are created only with `scripts/create_admin.py`.** Signup can never create an admin.

---

## 6. Stages

Sizes are relative: S is small, M is medium, L is large. Each stage ends in a checkpoint for your review.

### Stage 0 — Scaffold & database models (S)
- `git init`, `.gitignore`, repo layout above, `.env.example` files, README skeleton.
- Backend: venv, FastAPI app with `/api/health`, settings via `pydantic-settings`, SQLAlchemy 2.0 models (§4), Alembic initial migration.
- Frontend: `create-next-app` (TypeScript, Tailwind, App Router), design tokens, Space Grotesk and Inter via `next/font`, `/api` rewrite to the backend.
- CI workflow: ruff, pytest, `next lint`, typecheck, build.
- **Done when:** `alembic upgrade head` creates all tables, both apps start, CI is green.

### Stage 1 — Analysis pipeline (M) ⭐ most important
- `config.py`, `loader.py`, `analyzer.py`, `optimizer.py`, `data_generator.py`, fixtures, tests (§3).
- A small CLI, `python -m app.pipeline.run sample.csv`, prints the report so you can check the numbers by hand.
- **Done when:** the golden tests pass, coverage is ≥ 90%, and you have hand-checked one sample report.

### Stage 2 — Auth (S)
- Signup, login, logout, refresh, `/me`, role dependencies (`require_client`, `require_admin`), admin seed script, rate limiting.
- **Done when:** tests cover a bad password, an expired token, a client calling an admin route, and signup attempting to set a role.

### Stage 3 — Upload & analysis endpoints (M)
- Streaming upload with size limit, SHA-256 duplicate detection, loader validation with a row-level error response, storage interface, template CSV.
- The analysis runs as a background task, and results are written to `analysis_runs`, `waste_reports`, `segment_metrics` and `recommendations`.
- **Done when:** a sample file goes from upload to a pending run with correct stored numbers, and the isolation tests pass.

### Stage 4 — Client dashboard UI (L)
1. App shell, login/signup pages, upload page (drag-drop, validation errors per row, run status).
2. Dashboard summary with an asymmetric layout:
   - The hero area takes about 60% of the first screen, with big Space Grotesk numbers beside it: total spend, estimated waste, recovery %.
   - Below it: breakdown tables with hairline dividers, one tab per dimension, flagged rows in Leak Coral.
   - A recommendations list that expands with Framer Motion to show the reasoning.
3. **Hero, step A:** a static SVG flow diagram driven by the real spend/waste ratio. It doubles as the `prefers-reduced-motion` fallback.
4. **Hero, step B:** a React Three Fiber particle stream (instanced points).
   - The teal/coral split matches the actual waste share.
   - The waste count-up is synced to the coral drip, and the animation plays once on load.
   - Lazy-loaded (`dynamic(..., { ssr: false })`) so the tables never wait on Three.js.
- Empty states: no uploads yet, or a run awaiting admin review.
- **Done when:** the dashboard renders real data, reduced motion shows the static version, and it works at mobile width.

### Stage 5 — PDF report (S)
- ReportLab report: cover summary, per-dimension tables, recommendations with reasons, config/benchmark footnote, and the date range.
- **Done when:** the PDF numbers match the dashboard exactly (tested), and it only works for approved runs.

### Stage 6 — Admin panel (M)
- Clients list and detail (fees, per-client threshold overrides).
- Approval queue: run numbers, flagged segments, config snapshot, approve or reject with a note.
- Invoice drafting: suggested recovered waste from the before/after comparison, which the admin can edit and confirm.
- Audit log view. No animation, dense tables.
- **Done when:** approve/reject and fee confirmation each write an audit entry, and clients see a run only after approval.

### Stage 7 — Billing with manual payments (M)
**Decided:** first clients pay by hand to your JazzCash, Easypaisa, NayaPay or bank account (Raast). No gateway, no NTN needed to launch.

How a billing month works:
1. **Admin sets up payment accounts once.** Wallet numbers, Raast ID or IBAN, and account title. These appear on every invoice.
2. **Admin generates invoices** for the month. One invoice per client covers the **base fee plus the confirmed performance fee**, after the month ends. The admin reviews the draft, then issues it.
3. **Client sees the invoice** on the billing page and as a PDF, with the amount, due date and the accounts to pay into.
4. **Client pays from their own app**, then submits the payment method, **transaction ID**, amount, date, and an optional screenshot. The invoice moves to "payment submitted".
5. **Admin checks their wallet or bank app**, then confirms or rejects with a reason. The client sees the reason and can submit again.
6. The invoice becomes **paid** once confirmed payments cover the total. Partial payments are allowed and tracked.

Rules:
- **Only the admin can mark money as received.** A client submission never marks an invoice paid on its own.
- A transaction ID can't be used twice (unique per method).
- Screenshots go to private storage, limited to images or PDF and a size cap.
- Amounts use `Decimal`.
- Every confirm, reject and void writes to `audit_log`.
- Overdue invoices (past the due date) are flagged in the admin panel. Nothing is suspended automatically in the MVP.
- Payment logic sits behind a `PaymentProvider` interface. `ManualProvider` is built now, so adding an automatic gateway later (see §9) is a new provider class, not a rewrite.

- **Done when:**
  - A full month runs end-to-end: generate → issue → client submits TID → admin confirms → invoice paid.
  - A reused TID is refused.
  - A client can't see or pay another client's invoice.
  - A partial payment leaves the invoice unpaid.

### Stage 8 — Hardening & deploy (M)
- Sentry (backend and frontend), security headers, CORS locked to the frontend origin, request size limits, structured logging.
- Deploy: Supabase Postgres (backups on), backend on Railway or Render, frontend on Vercel, S3-compatible file storage.
- Seeded demo client for sales demos. Smoke-test checklist in the README.
- Terms, Privacy and Refund policy pages (you supply the wording). Clients expect them, and every gateway requires them later.
- **Done when:** the full flow works in production (signup → upload → admin approve → dashboard → PDF → invoice → manual payment confirmed).

---

## 7. Decisions needed before or during the build

| # | Decision | Status |
|---|---|---|
| 1 | Waste benchmark | ✅ `account_avg` (configurable to `best`) |
| 2 | How recovered waste is measured for the performance fee | ✅ Before/after on previously flagged segments, admin-confirmed |
| 3 | Database | ✅ Supabase in Mumbai (`ap-south-1`): Free plan for dev, Pro for prod. Used as **plain Postgres** through SQLAlchemy and Alembic, with our own JWT auth instead of Supabase Auth, so we could move hosts later. Supabase Storage (private buckets) holds uploaded CSVs and PDFs. The backend connects directly or through the session-mode pooler. |
| 4 | Actual pricing numbers (base fee, performance %, cap) | ⏳ Placeholders in config until you decide |
| 5 | Payment provider | ✅ MVP: manual payments to JazzCash, Easypaisa, NayaPay or bank (Raast), with the client submitting a transaction ID and the admin confirming. Later: one automatic gateway (see §9) |
| 6 | PDF library | ✅ ReportLab |

**Supabase notes:**
- Free projects pause after about a week of inactivity, which is fine for dev.
- Prod needs Pro, which stays on and includes daily backups.
- Point-in-time recovery is a paid add-on; skip it until there are paying clients.
- The service-role key is used only on the backend, never in the frontend.

## 8. Risks to watch

- **Wrong numbers mean billing disputes.** Mitigations: golden tests, a config snapshot per run, admin approval, an audit log.
- **Real exports vary.** Mitigations: a template CSV now, column mapping later; test against a real Meta export early in Stage 3 if you can get one.
- **Hero animation eating time.** The static version ships first; the animation can be polished after the rest works.
- **Personal wallet limits.** Personal JazzCash and Easypaisa accounts have monthly receiving limits (one 2026 guide says about Rs. 400,000 for JazzCash before full verification). Mitigations: list a bank account (Raast or IBAN) as the main method, and move to a business account as revenue grows.
- **Manual checking doesn't scale.** At roughly 10–15 clients, confirming payments by hand gets slow. That's the signal to add the automatic gateway (§9).

---

## 9. After the MVP: automatic payments

Start when you have paying clients and the paperwork is ready:
1. **Paperwork:**
   - A sole-proprietor NTN from FBR IRIS (free, about 3–7 days).
   - A business bank account and its bank maintenance certificate.
   - The policy pages from Stage 8.
2. **Pick one gateway:**
   - **NayaPay Business (Arc checkout):** a website checkout, with a default monthly incoming limit of Rs. 20 lakh.
   - Or **one gateway covering cards and wallets together:** Safepay, or PayPro for 1Link bank-app invoices.
3. **Build it as a second `PaymentProvider`:**
   - Invoices get a **"Pay online"** button next to the manual instructions.
   - Add a `payment_events` table (a webhook log with unique event IDs, so each event is processed only once).
   - Mark invoices paid **only from a signature-verified webhook**, never from redirect URL parameters.
   - Test on the provider's sandbox first.
4. Manual payments stay available as an option.
