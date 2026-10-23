# Architecture

The paper's expected picture is "two EC2 application instances behind a Load Balancer,
managed by an Auto Scaling Group, with containerized web and database services, tested by
Selenium." Here is that, for this product.

```mermaid
flowchart LR
    U[Browser / Selenium] -->|HTTP :80| ALB[Application Load Balancer<br/>targets :3000, health /api/health]
    ALB --> I1
    ALB --> I2
    subgraph I1[EC2 instance A - t3.medium]
        F1[frontend :3000] -->|rewrite /api/*| B1[backend :8000]
        B1 --> R1[redis]
        B1 --> D1[(postgres<br/>adopt-pgdata)]
    end
    subgraph I2[EC2 instance B - t3.medium]
        F2[frontend :3000] -->|rewrite /api/*| B2[backend :8000]
        B2 --> R2[redis]
        B2 --> D2[(postgres<br/>adopt-pgdata)]
    end
```

The laptop demo is the same diagram with one instance and no ALB: `docker compose up`
brings up `frontend`, `backend`, `db`, `redis` and the one-shot `migrate`.

### Why Postgres is per instance here, and what production does instead

Read this before the viva, because it is the obvious follow-up question.

Each Compose stack starts its own Postgres on the `data` network, so an Auto Scaling Group
of two instances means two databases. That is acceptable **for this lab** for a specific
reason: `scripts/bootstrap-ec2.sh` runs `seed_demo` on every instance at boot, so both
nodes contain the same demo client, the same upload and the same approved report. Signing
in through the load balancer therefore works whichever node answers, which is what the
demonstration needs.

It is not what you would run for real: a *new* upload written to node A is invisible to
node B, and a scale-in would delete that node's volume with it. Production puts the
database outside the instances — RDS, or one dedicated host — and points every node at it.
Nothing in the application changes, because `backend/app/core/settings.py` already reads a
single `DATABASE_URL`; that is exactly why the connection string is an environment variable
rather than a constant:

```bash
# production shape: app containers only, one shared database
export DATABASE_URL="postgresql+psycopg://user:pass@rds-endpoint:5432/adoptimizer"
docker compose up -d --no-deps backend frontend
```

The same reasoning applies to `STORAGE_BACKEND=local`: the settings file rejects
`local` storage on serverless because there is no durable disk, which is the container
version of the same problem. Supabase storage is already implemented for that case.

## Services

| Service | Image / build | Listens | Network(s) | Volume | Healthcheck |
| --- | --- | --- | --- | --- | --- |
| `frontend` | `frontend/Dockerfile` → `adopt-frontend:local` | 3000 | `app` | — | `wget /api/health` (proxies to the API) |
| `backend` | `backend/Dockerfile` target `runtime` → `adopt-backend:local` | 8000 | `app`, `data` | `adopt-appstorage` → `/app/backend/storage` | python urllib on `/api/health` |
| `db` | `postgres:16-alpine` | 5432 | `data` (internal) | `adopt-pgdata` | `pg_isready` |
| `redis` | `redis:7-alpine` | 6379 | `data` (internal) | `adopt-redisdata` | `redis-cli ping` |
| `migrate` | same image as `backend`, `restart: "no"` | — | `data` | — | exits 0 on success |
| `seed`, `test`, `chrome`, `selenium` | opt-in Compose profiles | — | — | — | run to completion |

Two networks, so nothing that should not be reachable is:

* `app` — browser-facing containers (`frontend`, `backend`, `chrome`, `selenium`).
* `data` — `internal: true`. Postgres and Redis sit here and have no route to the host or
  the internet; only `backend` bridges the two networks.

## One request, end to end

1. Browser asks the ALB for `/dashboard`. The listener forwards to a healthy target on
   port 3000 — the frontend container.
2. The Next.js server component calls `serverFetch("/api/reports/latest")`, which reads
   `BACKEND_URL` and hits `http://backend:8000`, forwarding the client's cookies. Docker
   DNS resolves `backend` to that container on the shared network.
3. FastAPI validates the JWT cookie, opens a pooled psycopg connection to `db:5432`, and
   returns the approved report rows.
4. The response walks back through the same hops. The ALB records the target as healthy
   because `GET /api/health` returned 200 — which only happens if steps 2 and 3 both worked.

Login differs in one place: the browser posts to `/api/auth/login`, which is the rewrite
rule (not a server component), so Next proxies it to the API. The API sets `access_token`
and `refresh_token` cookies, and slowapi counts the attempt in Redis so five failures in a
minute return 429.

## Where state lives

| State | Home | Survives container recreation | Survives `down -v` |
| --- | --- | --- | --- |
| Users, clients, analysis runs, invoices | `adopt-pgdata` (Postgres data dir) | Yes | No |
| Uploaded CSVs, generated PDFs | `adopt-appstorage` (container `/app/backend/storage`) | Yes | No |
| Login rate-limit counters | Redis `adopt-redisdata`, or process memory | Redis: yes. Memory: no | No |
| Access tokens | The client's cookies | n/a | n/a |
| Application code | The image layer, read-only | Yes — rebuilt from the repo at boot | Yes |

On EC2 the third row is the honest caveat: each instance runs its own Redis, so per-node
counting is still per-node. One ElastiCache endpoint set through
`terraform/variables.tf -> rate_limit_storage_uri` makes it global. Locally, one Redis
serves the whole stack, so the limit is real.

## Images

`backend/Dockerfile` has three targets over one dependency layer:

* `base` — `python:3.11-slim`, `pip install -r requirements.txt` (3.11 to match CI)
* `runtime` — non-root `appuser` (uid 1001), env defaults, healthcheck, `uvicorn`
* `test` — adds `requirements-dev.txt` and runs the existing pytest suite

`frontend/Dockerfile` uses `deps → build → runtime` with `output: "standalone"` in
`next.config.ts` (gated behind `NEXT_STANDALONE_OUTPUT=1`, which only the Docker build
stage sets, so the live Vercel deployment keeps its original build output), so the runtime
image copies `.next/standalone`, `.next/static` and
`public` — no `node_modules`, no build toolchain, running as `node`.
