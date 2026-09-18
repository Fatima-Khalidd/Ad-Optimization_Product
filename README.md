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
.venv\Scripts\activate          # Windows
pip install -r requirements-dev.txt
copy .env.example .env          # then edit DATABASE_URL
alembic upgrade head
uvicorn app.main:app --reload
```
Health check: http://127.0.0.1:8000/api/health

### Frontend

```bash
cd frontend
npm install
npm run dev
```
Open http://localhost:3000 — `/api/*` is proxied to the backend.

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
cd backend && pytest
cd frontend && npm run lint && npx tsc --noEmit && npm test && npm run build
```

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
