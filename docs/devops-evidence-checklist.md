# Evidence checklist — what to screenshot per task

10 marks in Section A are awarded for demonstrated artifacts, and "a working final
deployment without proper Docker evidence will receive partial marks only". Capture these
**as you go**, not the night before the viva — the AWS ones cost money and the container
ones need the stack up.

Naming: `evidence/01a-alb-targets.png`, `evidence/03b-docker-images.png` — the number
matches the task, so the examiner can flip through in order. Keep the terminal visible in
every shot (prompt + command + output); a cropped number with no command attached proves
nothing.

---

## Task 1 — AWS Load Balancer & Auto Scaling (2 marks)

| Shot | Command / screen | What must be legible |
| --- | --- | --- |
| 1a | `terraform -chdir=terraform plan` | `Plan: 17 to add` (18 if you set `ssh_cidrs`) and the resource list — ALB, target group, listener, launch template, ASG, policy, 2 SGs + 6 rules, IAM role/policy attachment/instance profile |
| 1b | `terraform -chdir=terraform apply` tail | `app_url`, `health_url`, `autoscaling_group_name` outputs |
| 1c | `aws elbv2 describe-target-health --target-group-arn $(terraform -chdir=terraform output -raw target_group_arn)` | **two** targets, both `state: "healthy"`, different `InstanceId` values |
| 1d | EC2 console → the two instances | Same ASG tag, different AZs, `running` |
| 1e | `bash scripts/verify-load-balancing.sh <alb-dns>` | The tally line: N requests, 2 distinct instances, both non-zero |
| 1f | ASG console → Activity tab | Scale-out event, or the `--desired-capacity 3` change from the deploy doc |
| 1g | After terminating an instance | New instance `in-service`, ALB back to 2 healthy targets, app still loads in the browser |
| 1h | `terraform -chdir=terraform destroy` → `Destroy complete` | Proof you are not leaving billable resources |

Browser shot of `http://<alb-dns>` showing the landing page is the "accessible through the
AWS Load Balancer" deliverable — take it too.

## Task 2 — Linux administration (1 mark)

Run `bash scripts/linux-admin-demo.sh` on the EC2 instance (Session Manager session, so
the hostname in the prompt is AWS evidence as well) and screenshot the blocks showing:

| Shot | Output that must be visible |
| --- | --- |
| 2a | `id`, `pwd`, `ls -ld` of the demo root |
| 2b | `mkdir -p` then `stat -c '%A %a %U %G %n'` on the created directories — `drwxr-x---` 750, `drwxrwsr-x` 2775 |
| 2c | The file modes block — `-rw-r-----` 640, `-rw-------` 600, `-rw-r--r--` 644 |
| 2d | The `umask 077` / `umask 022` comparison — same `touch`, different resulting modes |
| 2e | `find . -type f ! -perm -004` result, and the setgid proof (a file created inside the 2775 dir inherits the group) |

If the examiner wants it live rather than scripted: `mkdir -p /tmp/demo/logs && chmod 750
/tmp/demo/logs && chmod 640 /tmp/demo/logs/app.log && stat -c '%A %n' /tmp/demo/logs/app.log`.

## Task 3 — Docker install, Dockerfile, image, container (2 marks)

| Shot | Command | What must be legible |
| --- | --- | --- |
| 3a | `docker --version && docker compose version` | Versions |
| 3b | `systemctl is-active docker` (EC2 or the Ubuntu VM) | `active` — the install actually runs. This is the command that only makes sense on a Linux host; on Docker Desktop the daemon is inside a VM and `systemctl docker` does not exist on Windows |
| 3c | `docker build -t adopt-backend:local --target runtime backend/` | Layer progress, then `naming to docker.io/library/adopt-backend:local` |
| 3d | `docker images` | `adopt-backend:local`, `adopt-frontend:local`, sizes |
| 3e | `docker history adopt-backend:local` | The layer list — this is the multi-stage/caching answer made visible |
| 3f | `docker run -d --name adopt-demo -e ENV=dev -e ... adopt-backend:local` then `docker ps` | Container `Up (healthy)` |
| 3g | `docker exec adopt-demo id` | `uid=1001(appuser)` — non-root proof |
| 3h | `docker logs --tail 20 adopt-demo` | uvicorn startup + `GET /api/health 200` |
| 3i | The Dockerfiles themselves | `FROM python:3.11-slim AS base` / `AS runtime`, `USER appuser`, `HEALTHCHECK`, `CMD` |

Clean up with `docker rm -f adopt-demo` so it doesn't confuse the Compose shot.

## Task 4 — Docker volumes & persistence (1 mark)

| Shot | Command | What must be legible |
| --- | --- | --- |
| 4a | `docker volume ls` + `docker volume inspect adopt-pgdata` | Volume present, `DRIVER local`, mountpoint under `/var/lib/docker/volumes/` |
| 4b | `bash scripts/demo-volume-persistence.sh` **before** recreation | Row count in `users`, probe file content |
| 4c | The same script after `docker rm -f` and recreate | **Identical** row count and file content — this is the whole mark |
| 4d | `grep -A3 '^volumes:' docker-compose.yml` | `pgdata:/var/lib/postgresql/data`, `redisdata:/data`, `appstorage:/app/backend/storage` |

Also know the counter-example without running it: `docker compose down -v` deletes them.
The script prints that line and deliberately does not execute it.

## Task 5 — Docker Compose, ≥2 containers (2 marks)

| Shot | Command | What must be legible |
| --- | --- | --- |
| 5a | `docker compose config` (trimmed) | Services, `x-backend-env` resolved, no `${VAR:?}` left raw |
| 5b | `docker compose up -d --build` | The build order and `Started`/`Healthy` lines |
| 5c | `docker compose ps` | **Five** containers running: db, redis, backend, frontend + migrate `Exited (0)` |
| 5d | `docker network inspect ad-optimization_data` | `Internal: true`, containers attached |
| 5e | `curl -s http://localhost:3000/api/health` | JSON from the backend **through** the frontend proxy |
| 5f | Browser at `http://localhost:3000`, logged in as `demo@example.com` | The populated dashboard |
| 5g | `docker compose logs backend --tail 30` | Requests arriving from the frontend container |

The "communication" part of this criterion is 5e/5d: service-name DNS (`http://backend:8000`),
health-gated `depends_on`, and an internal network for the database.

## Task 6 — Selenium (2 marks)

| Shot | Command | What must be legible |
| --- | --- | --- |
| 6a | `pytest tests/selenium -v` | Five collected tests, `5 passed`, the duration |
| 6b | The failure-mode shot (optional but strong) | Temporarily point `APP_BASE_URL` at a wrong port → shows the explicit-wait timeout, then revert |
| 6c | `docker compose --profile selenium up selenium` | The same run inside the container against `chrome:4444` |
| 6d | `APP_BASE_URL="http://<alb-dns>" pytest tests/selenium -v -k login` | The element assertion passing **against AWS** — this is the one that ties Task 1 and Task 6 together |
| 6e | `tests/selenium/test_application.py` | The `data-testid="hero-band"` locator and `assert` |

Screenshot the specific element assertion, not just the green bar: the criterion says
"verify a web element".

---

## Pre-flight the morning of the viva

```bash
docker compose up -d --build
docker compose ps                       # 4 running + migrate exited
curl -s localhost:3000/api/health       # {"status":"ok","env":"dev",...}
docker compose --profile seed run --rm seed
pytest tests/selenium -v                # 5 passed
docker volume ls                        # adopt-pgdata, adopt-redisdata, adopt-appstorage
```

If AWS is still up, `bash scripts/verify-load-balancing.sh <alb-dns>` and have the ALB URL
open in a browser tab. If you destroyed it, bring the local stack instead and say so —
partial marks on Task 1 beat a live stack you forgot to shut down.

## Deliverables from the exam paper, mapped

| Required deliverable | Where it is |
| --- | --- |
| Working app accessible through the AWS LB | `terraform output app_url` + shot 1 browser |
| A Dockerfile | `backend/Dockerfile`, `frontend/Dockerfile` (shot 3i) |
| A Compose YAML | `docker-compose.yml` (shot 5a) |
| Docker persistent volumes | `adopt-pgdata` / `adopt-redisdata` / `adopt-appstorage` (shot 4) |
| Basic Linux admin commands | `scripts/linux-admin-demo.sh` (shot 2) |
| Successfully executed Selenium script | `pytest tests/selenium -v` (shot 6a) |
