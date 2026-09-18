# Ad Spend Optimization

Detects wasted Meta/Google ad spend for small businesses in Pakistan and turns it into
plain-language budget recommendations. Design doc: `docs/PLAN.md`. Build plans:
`docs/superpowers/plans/`.

## Layout

- `backend/` — FastAPI + SQLAlchemy + the analysis pipeline (Python 3.11)
- `frontend/` — Next.js + Tailwind (Node 24)
- `docs/` — product plan and implementation plans

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
curl -b cookies.txt http://localhost:8000/api/reports/1                       # 404 until an admin approves
```

`GET /api/uploads/template.csv` is public (no session cookie) - it contains no tenant data:

```bash
curl -O http://localhost:8000/api/uploads/template.csv                       # blank template
```

Uploaded CSVs are written through the storage interface (`STORAGE_ROOT`, default
`./storage`). Files over `MAX_UPLOAD_MB` are rejected with 413, and re-uploading identical
bytes with 409. A report becomes visible only once its run is `done` **and** an admin has
set `review_status = approved` (Stage 6).

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

### Admin panel (Stage 6)

Create an operator account, then sign in at `/login` and open `/admin`:

```bash
cd backend
.venv/Scripts/python -m scripts.create_admin --email you@example.com
```

- `/admin/runs` — approval queue. A client cannot see a report until its run is approved here.
- `/admin/clients/<id>` — base fee, performance fee %, and per-client `PipelineConfig` overrides
  (unknown keys are refused with 422).
- `/admin/invoices` — draft for a client and period, confirm the recovered-waste figure, then
  issue or void. The suggestion compares the segments flagged before the period against the
  same segments inside it, **per dimension, and takes the largest single dimension — never the
  sum** (`docs/PLAN.md` §1 #5): one saving shows up in the placement, age-group and time-slot
  breakdowns at once, so adding them would bill the client about three times over. The admin
  always confirms the final figure, and a drafted invoice's base fee is frozen at draft time.
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
