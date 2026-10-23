# Ad Spend Optimization

Detects wasted Meta/Google ad spend for small businesses in Pakistan and turns it into
plain-language budget recommendations. Design doc: `docs/PLAN.md`. Build plans:
`docs/superpowers/plans/`.

## Layout

- `backend/` — FastAPI + SQLAlchemy + the analysis pipeline (Python 3.11)
- `frontend/` — Next.js + Tailwind (Node 24)
- `docs/` — product plan and implementation plans
- `docker-compose.yml`, `*/Dockerfile` — the containerised stack
- `terraform/` — AWS ALB + Auto Scaling Group
- `scripts/` — bootstrap on EC2, Linux administration and volume-persistence demos
- `tests/selenium/` — end-to-end tests against a deployed URL

## Containerised deployment (DevOps)

Everything under "Run locally" below is the everyday workflow — two processes on your
laptop, no Docker. The containerised stack is documented separately, one file per concern:

- [`docs/DEVOPS.md`](docs/DEVOPS.md) — index: task mapping, quick start, ports, decisions, troubleshooting
- [`docs/devops-architecture.md`](docs/devops-architecture.md) — which service runs in which container and how they talk
- [`docs/devops-aws-deploy.md`](docs/devops-aws-deploy.md) — ALB + Auto Scaling, step by step, with the live demos
- [`docs/devops-viva-prep.md`](docs/devops-viva-prep.md) — questions by assessment criterion, with answers
- [`docs/devops-evidence-checklist.md`](docs/devops-evidence-checklist.md) — what to screenshot, per task

Bring the whole stack up in one command:

```bash
cp .env.example .env       # then set POSTGRES_PASSWORD, SECRET_KEY, DEMO_PASSWORD
docker compose up -d --build
docker compose --profile seed run --rm seed
open http://localhost:3000 # demo@example.com / your DEMO_PASSWORD
```

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

### Admin user (Stage 2)

Admins are never created through signup. Seed one:

```bash
cd backend
.venv/Scripts/python -m scripts.create_admin --email you@example.com
```

The password is prompted for (not echoed) so it stays out of your shell history; `--password`
exists for scripted use. The script exits 2 on a duplicate email, an invalid email, or a
password shorter than 8 characters, and writes nothing in those cases.

### Auth API

| Method | Path | Success |
|---|---|---|
| POST | `/api/auth/signup` | 201 — creates a client account and signs it in |
| POST | `/api/auth/login` | 200 |
| POST | `/api/auth/logout` | 204 |
| POST | `/api/auth/refresh` | 200 — rotates both cookies |
| GET | `/api/auth/me` | 200 — `client` is `null` for an admin |

Auth uses `httpOnly` cookies (`access_token` ~15 min, `refresh_token` ~7 days), so the frontend
never handles a token in JavaScript. Lifetimes and `COOKIE_SECURE` are set in `backend/.env`;
`COOKIE_SECURE` is forced on whenever `ENV=prod`. Login is limited to 5 attempts per minute per
IP address (429 after that). Failures are deliberately indistinguishable: a wrong password, an
unknown email and a deactivated account all return `401 {"detail": "invalid credentials"}`; a
duplicate signup returns `409 {"detail": "email already registered"}`.

### Uploads & analysis (Stage 3)

All routes below except the template download need the client session cookies from
`POST /api/auth/login`.

```bash
curl -b cookies.txt -F "file=@august.csv" http://localhost:8000/api/uploads   # 201, or 422 + row errors
curl -b cookies.txt -X POST http://localhost:8000/api/analyze/1               # 202 + run id
curl -b cookies.txt http://localhost:8000/api/runs/1                          # queued|running|done|failed
curl -b cookies.txt http://localhost:8000/api/reports/1                       # 200 when analysis is done (default)
```

`GET /api/uploads/template.csv` is public (no session cookie) - it contains no tenant data:

```bash
curl -O http://localhost:8000/api/uploads/template.csv                       # blank template
```

Uploaded CSVs are written through the storage interface (`STORAGE_ROOT`, default
`./storage`). Files over `MAX_UPLOAD_MB` are rejected with 413, and re-uploading identical
bytes with 409. By default a report becomes visible to its owner when its run is `done`;
set `AUTO_APPROVE_ANALYSES=false` if your operation requires admin review.

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
| `AUTO_APPROVE_ANALYSES` | backend | Defaults to `true`; completed reports become available to their owner without admin review. Set `false` to require review |
| `NEW_CLIENT_BASE_FEE`, `NEW_CLIENT_PERFORMANCE_FEE_PCT` | backend | Optional defaults for separately issued manual invoices; default to zero, not AppSumo plan or license settings |
| `PKR_PER_USD` | backend | Invoices are in USD (a flat $65/month by default). If an admin sets a performance fee for a client, it is charged on rupee recovered waste converted at this rate (default `276`), frozen onto each invoice when drafted |
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

### Admin panel (Stage 6)

Create an operator account, then sign in at `/login` and open `/admin`:

```bash
cd backend
.venv/Scripts/python -m scripts.create_admin --email you@example.com
```

- `/admin/runs` — analysis queue. Reports are auto-approved after successful analysis by default;
  set `AUTO_APPROVE_ANALYSES=false` to require manual approval.
- `/admin/clients/<id>` — base fee, performance fee %, and per-client `PipelineConfig` overrides
  (unknown keys are refused with 422).
- `/admin/invoices` — draft for a client and period, confirm the recovered-waste figure, then
  issue or void. The suggestion compares the segments flagged before the period against the
  same segments inside it, **per dimension, and takes the largest single dimension — never the
  sum** (`docs/PLAN.md` §1 #5): one saving shows up in the placement, age-group and time-slot
  breakdowns at once, so adding them would bill the client about three times over. The admin
  always confirms the final figure, and a drafted invoice's base fee and PKR→USD rate are frozen at draft time.
- `/admin/audit` — every approve, reject, client update and invoice action, with before/after JSON.

### Analysis pipeline (Stage 1)

Run the analysis on any CSV that matches `backend/tests/fixtures/minimal_valid.csv`'s columns:

```bash
cd backend
.venv/Scripts/python -m scripts.generate_sample_data        # writes tests/fixtures/sample_30d.csv
.venv/Scripts/python -m app.pipeline.run tests/fixtures/sample_30d.csv
.venv/Scripts/python -m app.pipeline.run my.csv --overrides '{"waste_multiplier": 2}'
```

All thresholds live in `backend/app/pipeline/config.py`.

Exit codes:
- `0`: Success
- `2`: Validation failure (missing file, bad overrides, or invalid CSV format)

### Client dashboard (Stage 4)

```bash
cd backend && .venv/Scripts/uvicorn app.main:app --port 8000   # terminal 1
cd frontend && npm run dev                                     # terminal 2
```

Open http://localhost:3000. `/dashboard/*` is behind a server-side auth guard that
forwards your cookies to `GET /api/auth/me`.

```bash
cd frontend
npm test            # Vitest + React Testing Library
npm run test:watch
```

The hero animation plays once on load and stops. Set
**DevTools → Rendering → Emulate prefers-reduced-motion: reduce** to see the
static SVG fallback instead.

### PDF report (Stage 5)

`GET /api/reports/{run_id}/pdf` returns `application/pdf` as an attachment named
`ad-waste-report-{run_id}.pdf`. It renders the same `ReportOut` the dashboard shows — cover
summary, one section per dimension (chart + segment table), numbered recommendations, and a
methodology footnote listing the run's saved config.

It answers **404** unless the run is `status = done` **and** `review_status = approved`, and for
another client's run. Rendering is ReportLab only (built-in Helvetica, `reportlab.graphics`
charts): there are no fonts or image tools to install on a deploy host.

## Billing (manual payments)

Money is never moved by this app. Clients pay from their own wallet or bank app and report the
transaction ID; **only an admin marks a payment as received**.

1. `/admin/payment-methods` — add the JazzCash / Easypaisa / NayaPay / Raast / bank accounts once.
   `sort_order` decides the order clients see; hiding an account keeps its history.
2. `/admin/invoices` (Stage 6) — draft the month, confirm the recovered waste, issue the invoice.
3. `/dashboard/billing` — the client sees the invoice and its PDF, pays, then submits the method,
   transaction ID, amount, date and an optional screenshot (PNG/JPEG/PDF, max 5 MB).
4. `/admin/payments` — the pending queue. Open the proof, then Confirm, or Reject with a reason the
   client will read. A transaction ID can never be reused for the same method. Only an admin can
   fetch a payment's proof file; a client cannot download their own upload back.
5. Confirmed payments add up: the invoice becomes **paid** only once they cover the total. Partial
   payments are normal and the balance stays visible on both sides.

Invoices past their due date and not yet paid are flagged **Overdue** in the admin queue and on the
client's billing page. Nothing is suspended automatically.

Switching to an automatic gateway later (`docs/PLAN.md` §9) means writing one new class that
implements `PaymentProvider` in `backend/app/payments/`, registering it in
`backend/app/payments/__init__.py`, and setting `PAYMENT_PROVIDER` — no route or UI rewrite.

## Deploy

Supabase Postgres + Storage (Mumbai `ap-south-1`); backend and frontend are two Vercel
projects from this one repository, both running in Mumbai (`bom1`).
Every step below is an **owner checkpoint** — it needs an account the repository does not have.
Work through them in order; each one ends with something you can verify.

### 1. Supabase production project

1. Create a new project: name `ad-optimizer-prod`, region **Mumbai (ap-south-1)**, plan **Pro**.
2. Save the database password somewhere safe — it appears once.
3. Settings → Database → confirm **Daily backups** are enabled (included with Pro). Leave
   Point-in-Time Recovery off for now.
4. Settings → Database → Connection string → **Transaction pooler** (port `6543`). Copy it,
   then change the scheme from `postgresql://` to `postgresql+psycopg://`. That is your
   `DATABASE_URL`. Keep the **Session pooler** string (port `5432`) too, for migrations.
5. Storage → New bucket → name `ad-optimizer`, **Public bucket OFF**. The backend reaches it
   with the service key; nothing is ever served from a public URL.
6. Settings → API → copy the **Project URL** (`SUPABASE_URL`) and the **`service_role`** key
   (`SUPABASE_SERVICE_KEY`). The `service_role` key bypasses row-level security: it goes on
   the backend Vercel project only, never on the frontend project, never into a
   `NEXT_PUBLIC_*` variable.

Verify: the bucket list shows `ad-optimizer` with a padlock / "Private" label.

### 2. Sentry projects

1. Create two projects in Sentry: one **Python / FastAPI** (backend) and one **Next.js**
   (frontend).
2. Copy each project's DSN. Backend DSN → `SENTRY_DSN` on the backend project. Frontend DSN →
   `NEXT_PUBLIC_SENTRY_DSN` on the frontend project.
3. For source maps, create an org auth token with the `project:releases` scope →
   `SENTRY_AUTH_TOKEN` on the frontend project, plus `SENTRY_ORG` and `SENTRY_PROJECT` slugs.

Verify: both projects show "Waiting for events".

### 3. Redis for the login rate limit

Vercel runs several copies of the backend at once, each with its own memory, so the login
limiter's counters must live in a shared store.

1. Vercel → Marketplace → **Upstash** → create a Redis database in Mumbai (`ap-south-1`).
2. Copy its `rediss://` connection string. That is `RATE_LIMIT_STORAGE_URI`.

Without it the API still runs, but logs a warning at every cold start and the limit is
counted per instance.

### 4. Migrations and the first admin

Vercel has no start command, so migrations run from your machine **before** each deploy that
adds one. Use the **Session pooler** string from step 1:

```bash
cd backend
DATABASE_URL='postgresql+psycopg://...pooler.supabase.com:5432/postgres' alembic upgrade head
DATABASE_URL='...same...' ENV=prod SECRET_KEY='<the prod key>'   python scripts/create_admin.py --email you@example.com --password '<a long password>'
```

`scripts/seed_demo.py` is for the **dev Supabase project only** — it refuses to run
whenever `ENV=prod` (exit code 2), on purpose: a demo client with a shared, documented
password is a real hazard in production. Do not run it against the prod database. There is
no demo client in production; the admin account created above is the only account you need.

Verify: Supabase → Table Editor lists the app's tables and one row in `users`.

### 5. Lemon Squeezy (card payments in USD)

Optional — without it, clients pay by bank transfer and an admin confirms each payment.

1. Create a Lemon Squeezy account and store. Under Settings → Payouts, add your Pakistani bank
   account (a USD/ESFCA account at your bank keeps the dollars as dollars; a PKR account has
   them converted on arrival).
2. Create one product, "Invoice payment", with a single variant. Its price does not matter:
   every checkout overrides it with the invoice's balance. Price it **tax-exclusive**, so tax
   is added on top and the client's invoice is credited with the full amount.
3. Settings → API → create a key → `LEMONSQUEEZY_API_KEY`. The store id and the variant id
   (from the variant's URL) → `LEMONSQUEEZY_STORE_ID` and `LEMONSQUEEZY_VARIANT_ID`.
4. Settings → Webhooks → add `https://<backend-domain>/api/webhooks/lemonsqueezy`, event
   **order_created**, with a long random signing secret → `LEMONSQUEEZY_WEBHOOK_SECRET`.
5. Set `PUBLIC_APP_URL` to the frontend origin.

Verify (test mode): open an issued invoice, click **Pay by card**, pay with a test card, and
the invoice turns **Paid** within a minute with a "Card" payment in its history. Refunds are
issued in Lemon Squeezy; record them on the invoice by hand.

### 6. Vercel backend project

1. New Project → import this repository → **Root Directory: `backend`**. Framework preset:
   **Other**. Vercel picks up `backend/vercel.json`, `backend/api/index.py`,
   `backend/.python-version` and `backend/requirements.txt`.
2. Environment Variables → paste every variable from `backend/.env.production.example`,
   filled in. `CORS_ORIGINS` is not known yet; set it to `https://example.com` for now and
   fix it in step 8.
3. Deploy, then copy the production domain. That URL is your `BACKEND_URL`.

On Vercel the app detects `VERCEL=1` and switches itself to serverless behaviour: each
analysis runs inside the `POST /api/analyze` request (60 s limit, `vercel.json`), database
connections are not pooled per instance, and local file storage is refused at startup.
Request bodies are capped at 4.5 MB by Vercel, so uploads are capped at `MAX_UPLOAD_MB=3`.

Verify: `curl -i https://<backend-domain>/api/health` returns `200`,
`{"status":"ok","env":"prod"}`, and the response includes `Strict-Transport-Security`.
The project's Logs tab shows one JSON object per line.

### 7. Vercel frontend project

1. New Project → import the same repository → **Root Directory: `frontend`**. Framework
   preset: Next.js.
2. Environment Variables → paste everything from `frontend/.env.production.example`, with
   `BACKEND_URL` set to the backend domain from step 6.
3. Deploy, then copy the production domain.

Verify: the frontend domain loads the landing page, and `/terms`, `/privacy` and `/refunds`
all render.

### 8. Close the CORS loop

1. On the backend project, set `CORS_ORIGINS` to the exact frontend production origin, for
   example `https://ad-optimizer.vercel.app` — no trailing slash, no wildcard. Add the custom
   domain as a second comma-separated entry if you have one.
2. Redeploy the backend project.

Verify: signing in on the frontend domain works, and signing in with the admin email
reaches `/admin`. If the browser console shows a CORS error, the origin string does not
match exactly — check for a trailing slash or `www.`.

### 9. Smoke test

Run the checklist below. Stage 8 is not done until every line is ticked **in production**.

## Smoke-test checklist (production)

- [ ] **BLOCKING — commercial access is decided.** Signup is currently open and does not
      verify an AppSumo purchase, redeem a code, or enforce deal-specific access/usage
      limits. Do not advertise that a purchase automatically provisions or limits an
      account until the owner has chosen those rules and the matching entitlement flow
      has been implemented.
- [ ] **BLOCKING — legal copy matches the offer.** `/terms`, `/privacy` and `/refunds`
      are generic product policies, not legal advice. Have the owner review them against
      the final price, access duration, usage limits, marketplace refund process and
      governing law before launch.

Run the rest in one sitting, in this order, on the live Vercel domain. Use a real browser,
not curl — the point is to prove the cookie, CORS and storage paths work end to end.

- [ ] **Signup.** `/signup` with a fresh email creates a client account and lands on the
      dashboard. The dashboard shows the "no uploads yet" empty state. Confirm the
      open-signup behavior matches your purchase-verification plan before marketplace traffic.
- [ ] **Upload.** `/dashboard/upload` accepts `backend/tests/fixtures/sample_30d.csv`. The
      file is accepted, row count and date range are shown, and the run status moves from
      queued to done.
- [ ] **Automatic report availability.** Once the run is done, the client can open its
      report and PDF without admin approval. A still-running report must remain unavailable.
- [ ] **Dashboard.** The dashboard shows total spend,
      estimated waste and recovery %, the per-dimension breakdown tables with flagged rows
      in coral, and the recommendations list. Check it once at mobile width.
- [ ] **PDF.** `/api/reports/{run_id}/pdf` downloads, and the numbers on the cover match the
      dashboard exactly.
- [ ] **Optional manual invoicing.** Only if you intend to separately invoice a customer
      outside the marketplace purchase: draft and issue an invoice, submit a test payment,
      confirm it as admin, and verify duplicate transaction IDs are refused. This is not
      AppSumo checkout or deal-entitlement handling.
- [ ] **Tenant isolation.** Signed in as client A, opening client B's report or invoice URL
      returns 404, not 403 and not the data.
- [ ] **Files really are in Supabase.** The Supabase Storage bucket lists the uploaded CSV
      and the payment screenshot, and opening the object's public URL directly fails.
- [ ] **Errors reach Sentry.** Both Sentry projects have left "Waiting for events" (trigger
      one deliberately if needed, e.g. request a report id that does not exist).
- [ ] **Policy pages.** `/terms`, `/privacy` and `/refunds` load, and the footer links to all
      three from every page.
- [ ] **Security headers in prod.** `curl -I https://<backend-domain>/api/health` shows
      `Strict-Transport-Security`, `X-Content-Type-Options`, `X-Frame-Options`,
      `Referrer-Policy` and `Permissions-Policy`.
- [ ] **CORS is closed.** From a browser console on any other site,
      `fetch("https://<backend-domain>/api/auth/me", {credentials: "include"})` fails with a
      CORS error.
