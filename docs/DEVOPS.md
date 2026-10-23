# DevOps deployment guide — CSC418 Mid-Term Lab

This is the exam-facing index. The application itself is documented in `README.md`; this
file covers containers, volumes, Linux administration, load balancing and testing.

* [Architecture](devops-architecture.md) — what runs in which container and how they talk
* [Windows Docker host](devops-windows-docker-host.md) — what to do if Docker Desktop will not install on your build
* [AWS deployment](devops-aws-deploy.md) — ALB + Auto Scaling Group, step by step
* [Viva preparation](devops-viva-prep.md) — questions by assessment criterion, with answers
* [Evidence checklist](devops-evidence-checklist.md) — what to screenshot, per task

---

## Section A mapping

| # | Task | Marks | Files | Command | What you show |
| --- | --- | --- | --- | --- | --- |
| 1 | AWS Load Balancer + Auto Scaling | 2 | `terraform/` | `terraform -chdir=terraform apply`, then `bash scripts/verify-load-balancing.sh <alb-dns>` | Two healthy targets, requests split across instance ids, group scales on CPU |
| 2 | Linux administration | 1 | `scripts/linux-admin-demo.sh` | `bash scripts/linux-admin-demo.sh` | `mkdir -p`, `chmod 640/600/2775`, `chown`, `umask`, `find -perm` |
| 3 | Docker install + image + container | 2 | `backend/Dockerfile`, `frontend/Dockerfile`, `scripts/bootstrap-ec2.sh` | `docker build -t adopt-backend:local --target runtime backend/` then `docker run` | `docker images`, inspect layers, running container |
| 4 | Docker volumes | 1 | `docker-compose.yml` (`pgdata`, `redisdata`, `appstorage`) | `bash scripts/demo-volume-persistence.sh` | Row count and probe file identical after `docker rm -f` and recreate |
| 5 | Docker Compose (≥2 containers) | 2 | `docker-compose.yml`, `.env.example` | `docker compose up -d --build` | `docker compose ps` with 5 containers, `docker compose logs backend` |
| 6 | Selenium | 2 | `tests/selenium/` | `pytest tests/selenium -v` | Passes against the deployed ALB URL, element verified |

Section B is the viva on 28 October 2026 — 15 marks over the same six topics (3/2/3/2/3/2).
Questions and answers by criterion are in [devops-viva-prep.md](devops-viva-prep.md);
what to screenshot for Section A is in
[devops-evidence-checklist.md](devops-evidence-checklist.md).

> Task 1 needs these files **committed and pushed** first: every EC2 instance clones
> `var.repo_url`/`var.branch` at boot and runs `scripts/bootstrap-ec2.sh` from that
> checkout, so anything unpushed simply does not exist on the instance. This work lives on
> the `devops-lab` branch — set `branch = "devops-lab"` in `terraform/terraform.tfvars`.

---

## Quick start (one laptop)

Needs a Linux Docker host with ~4 GB free to the daemon — Docker Desktop, or an Ubuntu VM
as in [devops-windows-docker-host.md](devops-windows-docker-host.md) if your Windows build
is below 19045 and the Desktop installer refuses. Expect ~15 minutes for the first build
(pandas/numpy and the Next.js build).

```bash
cp .env.example .env       # then set POSTGRES_PASSWORD, SECRET_KEY, DEMO_PASSWORD
docker compose up -d --build
docker compose ps
docker compose --profile seed run --rm seed
open http://localhost:3000  # sign in with demo@example.com / your DEMO_PASSWORD
```

Check each hop independently:

```bash
curl -s http://localhost:3000/api/health        # frontend proxy -> backend -> Postgres
curl -s http://127.0.0.1:8000/api/health        # backend direct
docker compose exec db psql -U adoptimizer -d adoptimizer -c 'select count(*) from users;'
```

Run the existing backend test suite inside the image:

```bash
docker compose --profile test run --rm test
```

Tear down but keep the data (`--volumes` deletes the demo client):

```bash
docker compose down
```

---

## Ports

| Port | Where | Notes |
| --- | --- | --- |
| 3000 | frontend container → host | The URL to open, and the ALB target |
| 8000 | backend container → host | Bound to `127.0.0.1` locally; `0.0.0.0` on EC2, reachable only from the ALB's security group |
| 4444 | chrome container → host | Selenium grid, `selenium` profile only |
| 5432 / 6379 | `data` network only | Never published — that network is `internal: true` |

---

## Five decisions worth being able to defend

1. **The stack runs with `ENV=dev`, not `prod`.** `backend/app/core/settings.py` forces
   `COOKIE_SECURE = true` whenever `ENV=prod`, and a Secure cookie is never returned over
   plain HTTP. The lab has no domain and no ACM certificate, so prod-mode auth would fail
   at the load balancer. Dev still uses the real Postgres container; only the cookie flag
   and the CORS startup check differ.
2. **Migrations are a one-shot service, not a line in the entrypoint.** An Auto Scaling
   Group can start two instances at once; if each runs `alembic upgrade head`, they race.
   `migrate` exits 0 and `backend` waits on `service_completed_successfully`.
3. **One uvicorn worker per container.** The login rate limiter keeps counters in process
   memory unless Redis is configured, so extra workers would multiply the limit. Scale-out
   happens at the ASG instead — that is what the load balancer is for.
4. **Both tiers have healthchecks, and the frontend's check goes through the proxy.**
   `wget http://127.0.0.1:3000/api/health` only passes when the rewrite to the backend
   container resolves, so a frontend marked healthy proves both tiers work. The ALB probes
   the same path.
5. **Data lives on named volumes, not the container filesystem.** Postgres writes to
   `adopt-pgdata` and uploads to `adopt-appstorage`, so `docker rm -f` loses nothing. On
   EC2 this matters twice over: an instance that is replaced boots with an empty disk.

---

## Troubleshooting

| Symptom | Cause | Fix |
| --- | --- | --- |
| `copy .env.example to .env first` | The `${VAR:?}` guards in `docker-compose.yml` | `cp .env.example .env` |
| `prod requires a non-default SECRET_KEY and a non-sqlite DATABASE_URL` | `ENV=prod` with defaults | Use `ENV=dev` (see decision 1) |
| `serverless functions have no persistent disk` | `VERCEL=1` leaked into the environment, or `SERVERLESS=true` with `STORAGE_BACKEND=local` | Unset it; containers are not serverless |
| Login redirects back to `/login` | Cookie dropped: HTTP with `COOKIE_SECURE=true`, or clock skew | Confirm `ENV=dev`; check `docker compose logs backend` for a 401 |
| `429 too many requests` on login | 5 attempts/minute rate limit | Wait a minute — this is the limiter working |
| `backend` unhealthy, `migrate` exited 1 | Postgres still warming, or password mismatch | `docker compose logs db`; recreate `pgdata` with `docker compose down -v` if you changed `POSTGRES_PASSWORD` |
| Next build killed during `docker compose build` | Not enough memory for the frontend build | Give Docker Desktop ≥4 GB, or use `t3.medium` on AWS (the launch template adds 2 GB swap) |
| Uploaded CSV missing after recreation | Volumes deleted with `down -v` | Re-run `docker compose --profile seed run seed` |

---

## Cost and teardown

Two `t3.medium` instances plus an ALB is roughly **$0.25/hour**. Take the screenshots, then:

```bash
terraform -chdir=terraform destroy
docker compose down          # add -v only if you want the volumes gone too
```

Destroy the AWS stack the same day you demo it (`terraform/README.md` has the checklist).
