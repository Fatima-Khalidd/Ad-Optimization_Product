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
