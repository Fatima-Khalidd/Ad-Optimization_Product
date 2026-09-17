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
