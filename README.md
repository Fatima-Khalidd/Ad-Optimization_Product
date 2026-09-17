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
.venv/Scripts/python scripts/create_admin.py --email you@example.com --password change-me-now
```

Auth uses `httpOnly` cookies (`access_token` ~15 min, `refresh_token` ~7 days). Lifetimes and
`COOKIE_SECURE` are set in `backend/.env`; `COOKIE_SECURE` is forced on whenever `ENV=prod`.
Login is limited to 5 attempts per minute per IP address.

### Tests

```bash
cd backend && pytest
cd frontend && npm run lint && npx tsc --noEmit && npm run build
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
