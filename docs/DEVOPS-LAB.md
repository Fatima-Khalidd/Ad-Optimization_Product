# DevOps lab deployment — Ad Spend Optimization on AWS EC2

This document describes how the product is containerised and deployed for the CSC418 mid-term lab:
Docker images for both tiers, a Compose stack with a containerised database, the stack running on an
EC2 Linux instance behind an Application Load Balancer managed by an Auto Scaling Group, and a
Selenium suite that exercises the deployed application in a real browser.

The application itself is unchanged by this work. Everything here is deployment: three Dockerfiles,
one Compose file, two demonstration scripts and the AWS topology.

## Architecture

```
                      browser / Selenium
                              |
                     Application Load Balancer        listener :80, two AZs
                              |  target group :3000, health GET /api/health
              +---------------+---------------+
              |                               |
     EC2 instance A (AZ a)            EC2 instance B (AZ b)     same AMI, t3.medium
     Auto Scaling Group: min 2 / desired 2 / max 4
              |
   docker compose stack, restarted by the Docker daemon on boot
              |
   +---------------------------------------------------------------+
   | frontend (Next.js, :3000)  -->  backend (FastAPI, :8000)      |   network "app"
   |                                    |                          |
   |                 postgres :5432   redis :6379                  |   network "data", internal
   +---------------------------------------------------------------+
         volume pgdata                     volume uploads
```

| service | image | port | state |
|---|---|---|---|
| `frontend` | built from `frontend/Dockerfile` | 3000, published | none — the build is the only stateful step |
| `backend` | built from `backend/Dockerfile` | 8000, published | none |
| `postgres` | `postgres:16-alpine` | not published | named volume `pgdata` |
| `redis` | `redis:7-alpine` | not published | deliberately unpersisted |
| `migrate-and-seed` | the backend image | — | one-shot, profile `seed` |
| `selenium-hub` / `selenium-test` | `selenium/standalone-chromium` / `tests/selenium/Dockerfile` | — | profile `test` |

Two Docker networks. `data` is declared `internal: true`, so the database and Redis have no route to
the outside world and publish no host port; only the backend reaches them. `app` carries the traffic
the browser produces.

## Runtime host

There is no container runtime on the development machine: Docker Desktop requires Windows build 19045
or later and WSL2 requires 19041, and this host is on 18363. The EC2 instance is therefore the Docker
host for every task, which also matches the exam's stated architecture ("deployed on an AWS EC2 Linux
instance using Docker and Docker Compose"). Linux commands, image builds, volumes, Compose and the
browser test are all demonstrated on that one machine.

## The configuration the containers need, and why

`backend/.env` is created on the instance by `scripts/lab-env.sh`. It is not in git and it is listed in
`backend/.dockerignore`, so it is neither committed nor baked into an image. Five values matter:

| variable | value | why this value |
|---|---|---|
| `ENV` | `dev` | `prod` sets `cookie_secure = True` unconditionally (`app/core/settings.py`). Over the lab's plain-HTTP listener the browser then refuses to return the session cookie, so a correct password still ends at `/login`. `prod` additionally refuses to boot on a localhost `CORS_ORIGINS` (`app/main.py`) and refuses to seed at all (`scripts/seed_demo.py`). |
| `SECRET_KEY` | 64 random hex characters | Signs the session token. One value, inherited by both instances through the AMI, is what lets a token minted by instance A be accepted by instance B. |
| `DATABASE_URL` | `postgresql+psycopg://adoc:adoc@postgres:5432/adoc` | `app/core/db.py` asserts the driver name, and the installed driver is psycopg 3. The usual `postgresql://` prefix fails at startup. |
| `RATE_LIMIT_STORAGE_URI` | `redis://redis:6379/0` | Read at import time by `app/core/rate_limit.py`. Without it the counters live in one process's memory; with it the Redis container is a real dependency rather than decoration. |
| `DEMO_PASSWORD` | `demo-password-123` | `scripts/seed_demo.py` exits with status 2 rather than choosing a password. Synthetic demo data, already documented in `docs/DEMO.md`. |

A production deployment of this product would terminate HTTPS at the load balancer with an ACM
certificate and then run with `ENV=prod`. The lab has no domain to validate a certificate against, so
it runs `dev` and keeps the exposure short: the security group allows port 3000 from the operator's
address only until the load balancer exists, and the whole stack is terminated the same day.

## Task 1 — Load Balancer and Auto Scaling Group

Built in the AWS console in ap-southeast-1.

1. Bring the stack up on instance #1 and seed it (Tasks 3-5 below first — the AMI is baked from a
   machine that already has the images and the data, which is what keeps instance boot instant).
2. Stop instance #1, then **Create image** from it. The resulting AMI carries the built images, the
   named volumes with the seeded rows, `backend/.env` and the Docker service enabled at boot.
3. Security groups: `lab-alb-sg` accepts 80 from `0.0.0.0/0`; `lab-ec2-sg` accepts **3000 from
   `lab-alb-sg` only**, so an instance cannot be reached around the balancer.
4. Target group `lab-tg`: HTTP **3000**, health check `GET /api/health`, success codes 200-299. That
   path is served by the backend but reached through the frontend's `/api/:path*` rewrite
   (`next.config.ts`), so one health check proves both containers and the link between them.
   **Stickiness enabled** (duration 1 day): each instance holds its own database, so a client's
   requests must keep landing on the same one.
5. ALB `lab-alb`: internet-facing, listener on 80 forwarding to `lab-tg`, subnets in two availability
   zones.
6. Launch template `lab-lt`: the AMI, `t3.medium`, `lab-ec2-sg`.
7. Auto Scaling group `lab-asg`: min 2 / desired 2 / max 4, both AZs, attached to `lab-alb`,
   health check type **ELB**, instance warm-up 900 s, and a target-tracking policy on 60 % average CPU.
8. Verify: target health shows two healthy targets; `http://<lab-alb-dns>/` logs in; the ASG page shows
   two instances. Raising desired capacity to 3 launches a third instance that registers and passes the
   same health check, which is the scaling behaviour demonstrated end to end.

## Task 2 — Linux administration

`scripts/linux-admin-demo.sh` — creates `/opt/ad-optimizer/{logs,data}`, writes files into them, then
sets and displays ownership and modes (755 root, 750 working directories, 644/640 files) with `ls -lR`
and `stat`, and proves the effect by attempting a read as the unprivileged `nobody` user. `free -h`,
`df -h` and `tail` complete the set.

## Task 3 — Docker installation, image and container

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker ubuntu        # log out and back in for the group to apply
docker --version && docker compose version && systemctl is-active docker
```

Then build the two custom images and run one as a container:

```bash
docker build -t adopt-backend:lab ./backend
docker build -t adopt-frontend:lab --build-arg BACKEND_URL=http://backend:8000 ./frontend
docker images
docker run -d --name lab-frontend -p 3000:3000 adopt-frontend:lab
docker ps
curl -s http://localhost:3000/login | head -c 300
docker rm -f lab-frontend
```

The frontend image answers `/login` on its own, so this demonstrates a single custom image running as
a container without needing the database. Build the images one at a time: two `next build` and `pip
install` processes together exceed 4 GiB and the kernel kills one of them.

Notes on the Dockerfiles worth knowing for the viva: dependencies are installed from
`requirements.txt`/`package-lock.json` **before** the source is copied, so a code edit does not
re-resolve the whole dependency tree; `python:3.12-slim` contains no `curl`, so the health check is a
one-line Python `urllib` call; `BACKEND_URL` must be a build **argument** for the frontend because
`next build` writes the API rewrite into `routes-manifest.json` at compile time.

## Task 4 — named volume and persistence

```bash
bash scripts/volume-persistence-demo.sh
```

The script counts rows in `users`, `clients` and `analysis_runs`, stops and **removes** the PostgreSQL
container, reads the volume from an unrelated `alpine` container to show the files are still on the
host, recreates PostgreSQL from the image, waits for it to report healthy, and counts the same rows
again. Identical counts prove the data lived in the named volume rather than in the container's
writable layer. `docker volume inspect ad-optimization_pgdata` shows the mount point under
`/var/lib/docker/volumes/`.

## Task 5 — Compose, at least two containers

```bash
docker compose up -d --build
docker compose --profile seed run --rm migrate-and-seed
docker compose ps
docker compose logs --tail 20 backend
curl -s http://localhost:3000/api/health
```

Four containers start together in dependency order: PostgreSQL must report healthy before the backend
starts, and the backend must report healthy before the frontend and the seeder run. `restart:
unless-stopped` on the four long-running services is what makes an Auto Scaling instance serve traffic
after a reboot with nobody logged in. Inter-container traffic resolves by service name
(`postgres`, `redis`, `backend`) through Compose's own DNS.

## Task 6 — Selenium against the deployed application

```bash
docker compose --profile test up --build --abort-on-container-exit selenium-test
```

The browser runs as its own container (`selenium-hub`) and the test container drives it over the
network, which is a Selenium Grid topology. `APP_URL` is an environment variable, so the identical
image is pointed at the instance on port 3000 and then at the load balancer:

```bash
APP_URL=http://<lab-alb-dns> docker compose --profile test up --abort-on-container-exit selenium-test
```

Two assertions in `tests/selenium/test_deployed_application.py`:

* `/api/health` through the frontend answers with the backend's JSON — the multi-container link,
  observed from a browser.
* the login form at `/login` (`Welcome back.` heading, `#email`, `#password`, the submit button) takes
  a seeded client to `/dashboard`, where `[data-testid="hero-band"]` is rendered and the report footer
  carries a run number. That distinguishes a finished analysis from the "nothing to show yet" state.

Sign in with `demo@example.com` / `demo-password-123` (`admin@example.com` uses the same password and
reaches the admin panel).

## Things that will bite

* **429 on the fifth login in a minute.** `app/routers/auth.py` limits `/api/auth/login` to
  5/minute. Requests reach the backend through the frontend proxy, so a browser and the test suite can
  share one counter; wait 60 s between attempts.
* **A target group on port 80 never goes healthy.** The stack publishes 3000; nothing listens on 80 on
  the instance.
* **`next build` killed at 4 GiB.** Keep the swapfile and build one image at a time.
* **`docker compose` as root writes `backend/.env` root-owned**, which then reads as a permission error
  for the normal user. `sudo chown -R ubuntu:ubuntu ~/ad-optimizer` fixes it.
* **An AMI contains a secret** — `backend/.env` with the `SECRET_KEY`. Do not share or copy the AMI
  outside the account, and delete it and its snapshot at teardown.

## Teardown

Order matters, because an Auto Scaling group relaunches anything it still governs. Nothing is deleted
from inside the instances — terminating them discards their volumes, which is the correct behaviour for
a lab whose only permanent artefact is the AMI:

1. `lab-asg` → edit to min/desired/max 0, then **Force delete**.
2. `lab-alb`, then `lab-tg`, then `lab-lt`.
3. Terminate instance #1.
4. Deregister the AMI and delete its snapshot, then delete the security groups.

Roughly USD 0.40 for the whole exercise at `t3.medium` rates in ap-southeast-1.
