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

### Tests

```bash
cd backend && pytest
cd frontend && npm run lint && npx tsc --noEmit && npm run build
```
