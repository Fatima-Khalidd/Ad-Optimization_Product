# Ad Spend Optimization — frontend

Next.js app for the Ad Spend Optimization client dashboard and admin panel. Talks to the
backend through `/api/*`, which is proxied to `BACKEND_URL`.

## Run locally

```bash
npm install
npm run dev
```

Set `BACKEND_URL` in `.env` (e.g. `BACKEND_URL=http://127.0.0.1:8000`) so `/api/*` requests
proxy to the FastAPI backend. Open http://localhost:3000.

## Checks

```bash
npm run lint
npx tsc --noEmit
npm run build
```

## Notes

- Design tokens (colors, spacing, etc.) live in `src/app/globals.css`.
- Fonts are Space Grotesk (display) and Inter (body), loaded via `next/font`.
