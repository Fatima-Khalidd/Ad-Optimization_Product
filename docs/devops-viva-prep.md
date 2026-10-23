# Viva preparation — CSC418 Mid-Term Lab (Section B, 15 marks)

Viva is on 28 October 2026. The examiner has the repo, the deployment and the marking
scheme in front of them; they are checking that you built it and that you know why each
piece is where it is.

Answer structure that works: **what it is → where it is in my project → what it would
break if it were wrong.** Roughly 40 seconds per answer.

The project's own words for these decisions are in [DEVOPS.md](DEVOPS.md) ("Five decisions
worth being able to defend"). This file is the question set.

---

## 1. AWS EC2, Load Balancing and Auto Scaling — 3 marks

**Q: What is the difference between a load balancer and an Auto Scaling Group?**
The ALB is a router: one DNS name, it distributes requests to registered targets and
reports their health. The ASG is a lifecycle manager: it launches and terminates EC2
instances to hold a desired count and replaces unhealthy ones. In my stack the ALB is
`aws_lb.app` and the ASG is `aws_autoscaling_group.app` in
[terraform/alb.tf](../terraform/alb.tf) and [terraform/asg.tf](../terraform/asg.tf);
they are joined by the target group ARN in the ASG's `target_group_names`.

**Q: How does the load balancer know an instance is alive?**
It polls the target group health check — `HTTP GET /api/health` on the container port,
200 expected, `healthy_threshold` 2 / `unhealthy_threshold` 3. My API returns
`{status, env, instance}` from `backend/app/main.py`, where `instance` is the EC2
instance id injected through `INSTANCE_LABEL`. That is also how I prove distribution:
`bash scripts/verify-load-balancing.sh <alb-dns>` curls the endpoint repeatedly and
counts distinct `instance` values.

**Q: What does `health_check_type = "ELB"` mean on the ASG, and why not "EC2"?**
"EC2" only checks the hypervisor — a booted but broken Docker container looks healthy.
"ELB" uses the target health, so an instance whose container crashed is marked unhealthy
and replaced. The grace period has to cover container boot plus image pull, which is why
mine is 900 seconds rather than the 300 default.

**Q: Walk me through your Auto Scaling Group settings.**
`min_size = 2`, `desired_capacity = 2`, `max_size = 4` — the exam asks for two instances
behind the balancer, so the minimum is 2 and never zero. Scaling is a target-tracking CPU
policy at 60% (`aws_autoscaling_policy.cpu_target_tracking`), so a burst of report analyses adds a third
machine without a scheduled action. New instances come from the launch template
(`aws_launch_template.app`): Ubuntu 24.04, `t3.medium`, 40 GB encrypted gp3 root, IMDSv2
required, an SSM instance profile, and user data that installs Docker and runs
`scripts/bootstrap-ec2.sh`.

**Q: Is target-group stickiness on?**
No — `stickiness { enabled = false }` in [terraform/alb.tf](../terraform/alb.tf). The app
holds no per-node session state (auth is a signed JWT in a cookie, minted by
`backend/app/core/security.py`), so requests can land anywhere. Turning it off is also
what makes the demo work: with sticky sessions each browser is pinned to one target and
the distribution never shows.

**Q: Why does the ASG need a launch template instead of a bare AMI?**
The template pins the machine shape — instance type, security group, IAM profile,
`http_tokens = "required"`, user data. The ASG only references it (`launch_template`
block), so changing the image means a new template version and an instance refresh, which
is why `instance_refresh` with `min_healthy_percentage = 50` is set: it rolls the fleet
without dropping below half capacity.

**Q: How do you reach a box that has no port 22 open?**
Session Manager. The instance role attaches `AmazonSSMManagedInstanceCore`, the instance
security group has no ingress 22 unless `ssh_cidrs` is deliberately set in
`terraform/security.tf`, and the outbound rule lets the SSM agent dial out.
`terraform output session_manager_command` prints the exact CLI.

**Q: What is the security group design?**
Two groups. The ALB group accepts 80 from `0.0.0.0/0`. The instance group accepts 3000
and 8000 **only from the ALB's group** (`source_security_group_id`), so even if someone
learns an instance's public IP, port 3000 is unreachable. Rules are written as separate
`aws_security_group_rule` resources because referencing the two groups from each other
inline creates a Terraform cycle.

**Q: What breaks if you delete one instance?**
Nothing user-visible. The ALB stops routing to it, the ASG launches a replacement, and
the new one re-seeds itself from `bootstrap-ec2.sh`. That is the live demo in
[devops-aws-deploy.md](devops-aws-deploy.md) — `aws autoscaling
terminate-instance-in-auto-scaling-group --should-decrement-desired-capacity false`.

**Q: Is the database really on the EC2 instances? That seems wrong.**
It is deliberate and it is the honest answer, not a mistake. Each instance runs the full
Compose stack including its own Postgres container, and `seed_demo` re-creates the demo
client on boot, so any instance the ALB picks can serve the same demo. For real
multi-user traffic you point `DATABASE_URL` at RDS and start only the app containers
(`docker compose up -d --no-deps backend frontend`) — documented in
[devops-architecture.md](devops-architecture.md). Per-instance Postgres with an ALB is a
demo pattern; a shared database is the production one, and knowing which is which is the
point.

**Q: Cost, and how do you tear it down?**
Two `t3.medium` plus an ALB is about $0.25/hour. `terraform -chdir=terraform destroy`
removes the ASG, ALB, template, roles and groups; the ASG terminates its own instances,
so there is nothing orphaned. I run `terraform plan` before apply and read it — that is
the professional habit the marks are for.

---

## 2. Linux commands and file permissions — 2 marks

**Q: Show me directory creation with permissions in one step.**
`mkdir -p /srv/adopt/logs` — `-p` makes parents and does not error if it exists.
`chmod 750` on it: owner rwx, group rx, other nothing.

**Q: Explain `chmod 640` versus `chmod a+r`.**
640 is absolute: owner rw, group r, other none. `a+r` is symbolic and only ever adds
permission. Use absolute modes for secrets so nothing is inherited from the current
state; use symbolic for one-bit changes. `chmod u+x script.sh` is the usual symbolic case.

**Q: What is the difference between `chmod` and `chown`?**
`chmod` sets mode bits, `chown` sets ownership (`chown appuser:appgroup file`). Only
ownership change needs root; permission change needs to be the owner or root.

**Q: What does umask do?**
It is the inverse default mask applied to new files. Directories start from 777 and files
from 666, so `umask 022` gives 755/644 (world-readable) and `umask 077` gives 700/600
(you only). My `bootstrap-ec2.sh` writes `.env` with `umask 077` then `chmod 600` so a
world-readable secret cannot be created by accident.

**Q: What is `chmod 2775` / the setgid bit on a directory?**
`2000` setgid: new files inside inherit the directory's group instead of the creator's
primary group, and it makes the group sticky for the whole subtree. That is how a shared
upload/scan directory keeps `appgroup` ownership when several users write to it. On a
file, setgid means something different (and is mostly legacy) — the `-rwxrwsr-x` display
is where you see it.

**Q: What about the sticky bit?**
`chmod 1777` — /tmp behaviour: everyone writes, only the owner (or root) deletes.

**Q: How do you find world-writable files, and how do you read a mode numerically?**
`find /srv/adopt -type f ! -perm -004` lists files that are *not* world-readable;
`find ... -perm -o=w` finds world-writable ones. `stat -c '%A %a %U %G %n' file` prints
symbolic mode, octal mode, owner, group and name — that is what my demo script uses
because `ls -l` needs mental arithmetic.

**Q: Directory 750 vs file 750 — why does the same number mean different things?**
On a directory `x` means "traverse/search into it", so the group can `cd` and access
entries by name but cannot list them (that's `r`). On a file `x` means execute. So 750 on
a directory is a normal private-but-shared setting; 750 on a binary is an executable.

**Q: Which service commands do you actually use?**
`systemctl status docker`, `journalctl -u docker --since -10m`, `ps aux | grep uvicorn`,
`ss -tlnp` to see which ports are listening, `df -h`/`free -m` before a big build. On
EC2 `docker` group membership comes from `usermod -aG docker $USER`, and the group only
takes effect on a new login — `newgrp docker` is the trick when you do not want to
reconnect.

`bash scripts/linux-admin-demo.sh` runs all of this in order with banners, cleans up
after itself, and only touches `/tmp/adopt-linux-demo` so nothing in the repo can break.

---

## 3. Docker images, Dockerfile and containers — 3 marks

**Q: Why two `FROM` lines in one Dockerfile?**
Multi-stage build. `frontend/Dockerfile` has `deps` (runs `npm ci`), `build` (runs
`npm run build`), and `runtime` which copies only `.next/standalone`, `.next/static` and
`public` into `node:24-alpine`. The final image has no source, no `node_modules` and no
toolchain — it is a few hundred MB instead of a few GB, and the compiler is not present
for an attacker to use. `backend/Dockerfile` is the same idea: `base` installs pinned
requirements once, `runtime` and `test` branch from it so the dependency layer is shared.

**Q: Why does `COPY requirements.txt` come before `COPY app ./app`?**
Docker caches layers in build order, and a layer is invalidated by any change in it or
above it. Copying the manifest first means editing a route handler re-runs only the cheap
`COPY app` layer; the `pip install` of pandas and numpy stays cached. Reverse the two
lines and every code change reinstalls the world.

**Q: What is `USER appuser` doing, and why uid 1001?**
It drops privileges: the container starts as a non-root user, so a compromised app cannot
write to mounted volumes as root or exploit the kernel as easily. 1001 is chosen because
the Next image already uses uid 1000 (`node`), so the two containers do not collide on
host-mounted files. `--create-home` gives it a writable `$HOME` for caches.

**Q: Explain `HEALTHCHECK` in your two Dockerfiles.**
Backend: a `python -c` with `urllib` against `http://127.0.0.1:8000/api/health`,
interval 15s, retries 5, `--start-period=25s` so slow first-boot migrations are not
counted as failures. Frontend: `wget --spider http://127.0.0.1:3000/api/health`, which is
deliberately the *proxy* path — it only passes when Next's rewrite to the backend
container resolves, so a healthy frontend proves both tiers. `docker ps` shows
`(healthy)`; Compose uses it for `depends_on: condition: service_healthy`.

**Q: What is `EXPOSE` — does it open a port?**
No. It is documentation plus metadata (`docker port`, `-P` default publishing). Actual
mapping is `-p 3000:3000` at run time, or `ports:` in Compose. That distinction is a
classic viva trap.

**Q: Build and run commands you should be able to type from memory.**
```bash
docker build -t adopt-backend:local --target runtime backend/
docker run -d --name adopt-backend -p 8000:8000 -e DATABASE_URL=... adopt-backend:local
docker images
docker ps -a
docker inspect adopt-backend --format '{{json .State.Health}}'
docker logs --tail 50 adopt-backend
docker exec -it adopt-backend sh        # inside: whoami, id, ls /app/backend
docker rm -f adopt-backend
```
Also: `docker history adopt-backend:local` shows the layer list — it is the fastest way to
demonstrate the caching answer above.

**Q: Why is `output: "standalone"` behind an environment flag instead of just set?**
Because this repo's frontend is also deployed on Vercel, where standalone output is not
needed and would change the build artefacts. `next.config.ts` only sets it when
`NEXT_STANDALONE_OUTPUT=1`, which just the Docker build stage exports. One config file,
two very different targets, and neither one silently breaks the other — that is the
DevOps point of the whole question.

**Q: What is the difference between `CMD` and `ENTRYPOINT`, and `docker run` vs
`docker start`?**
`ENTRYPOINT` is the fixed executable; `CMD` is its default arguments and is overridable by
`docker run image <args>`. My images use `CMD` only, because Compose overrides the
command wholesale for `migrate` (`alembic upgrade head`) and `seed` — with an
`ENTRYPOINT` script that would take more work. `docker run` creates a container from an
image; `docker start` restarts an existing stopped one.

**Q: What is in `.dockerignore` and why?**
`.env`, `__pycache__`, `.pytest_cache`, `node_modules`, `.next`, `storage/`, tests'
caches. Two reasons: `node_modules` from Windows would be unusable in a Linux image, and
`.env` must never reach the image because layers are extractable — a secret baked into an
image is a secret published. Environment variables come in at run time from Compose, not
from the build context.

**Q: How did you install Docker, and what is the difference between Docker Desktop and
Docker Engine?**
On my laptop it is Docker Desktop (Engine inside a VM plus the CLI). On EC2
`scripts/bootstrap-ec2.sh` uses the official `get.docker.com` script — that installs
`docker-ce`, `containerd`, the CLI and a systemd unit, then `usermod -aG docker $USER`.
Desktop is for developers; on a server you want Engine so it comes up on boot under
systemd without a GUI. Note `apt install docker.io` also exists but ships an older
Ubuntu-packaged version; `docker-ce` from Docker's repo is the standard for a production
image.

**Q: Your Windows build is too old for Docker Desktop. What is your Docker host, then?**
An Ubuntu 24.04 Server VM on Hyper-V, with Docker Engine installed inside it by the same
`get.docker.com` script the EC2 instances use (`docs/devops-windows-docker-host.md`).
Build 18363 is below Docker Desktop's 19045 floor and WSL2 needs 19041, so neither inbox
path exists — but Hyper-V is the layer Docker Desktop itself uses on older Windows to run a
Linux daemon, so this is the same shape (Windows host → Linux VM → `dockerd` + Compose
plugin) without the GUI or the version gate. The upside for the lab is that
`systemctl is-active docker` and `chown`/`groupadd` are real here, and the images are
Linux-native rather than running through a file-sharing shim.

**Q: What makes a good image tag?**
`:latest` is a lie in CI. I use `adopt-backend:local` for local demos and would use the
git SHA for real deploys, because a rollback needs an immutable tag.

---

## 4. Docker volumes and data persistence — 2 marks

**Q: Name the three storage mechanisms and pick the right one.**
*Bind mount* (`-v /host/path:/container/path`) — host directory, you control the path,
good for configs and live code. *Named volume* (`-v pgdata:/var/lib/postgresql/data`) —
Docker manages it under `/var/lib/docker/volumes/<name>/_data`, portable, works on any
host including Docker Desktop's VM. *Anonymous volume* — created implicitly when a Dockerfile
declares `VOLUME`; you cannot reference it, so it is not something you persist to.
Postgres and uploaded CSVs are named volumes in `docker-compose.yml`: `pgdata`,
`redisdata`, `appstorage`. I gave them explicit names so they survive a project rename.

**Q: Prove persistence.**
`bash scripts/demo-volume-persistence.sh` — it counts rows in `users`, writes a probe
file into the backend's `storage/`, runs `docker stop` + `docker rm -f` on both app
containers, recreates them, and re-checks that the row count and file contents are
identical. Containers are disposable; volumes are not.

**Q: Which commands delete data and which do not?**
`docker rm -f <container>` — data safe (volume still referenced by nothing, but still on
disk). `docker compose down` — safe; containers and network gone, named volumes kept.
`docker compose down -v` — **gone**, this deletes named volumes and any anonymous ones.
`docker volume rm adopt-pgdata` — refuses while a container uses it.
`docker system prune --volumes` — the dangerous one; it removes volumes no longer
referenced, which is exactly the state of a stopped stack.

**Q: Why does Redis have a volume if it only holds rate-limit counters?**
So a stack restart does not reset the counters and let a brute-force attempt start fresh.
It also has `--save 60 1`, so it snapshots to `/data` (the `redisdata` mount) — a
rate-limiter store that is trivially rebuildable still shouldn't be an amplifier for
credential stuffing. In a real deployment I'd use ElastiCache with one endpoint shared by
all ASG nodes (`terraform/variables.tf` has the `RATE_LIMIT_STORAGE_URI` wiring);
per-instance Redis means per-instance counters, and I'd say that out loud rather than
pretend the limiter is global.

**Q: What is `tmpfs` and when would you use it instead?**
`tmpfs` mounts memory-backed storage (`docker run --tmpfs /run`); contents never touch
disk and vanish with the container. Right for scratch and secrets-in-flight, wrong for a
database.

**Q: Your app writes to `./storage` — what happens to permissions there?**
`appstorage` is created by Docker, and the backend runs as uid 1001, so `bootstrap` and
the Dockerfile `chown -R appuser /app/backend` make the mount writable by the app user.
If a bind mount is used instead with SELinux/AppArmor hosts you'd add `:z`/`:Z`; with a
named volume you don't hit that.

---

## 5. Docker Compose and multi-container communication — 3 marks

**Q: How many containers does your stack run, and what talks to what?**
Five in the default project: `db` (postgres:16-alpine), `redis`, `migrate` (one-shot),
`backend` (FastAPI :8000), `frontend` (Next.js :3000). Frontend → backend → Postgres;
backend → Redis. Three opt-in profiles add `seed`, `test`, `chrome` and `selenium`.

**Q: How does the frontend container find the backend? Is there an IP?**
No IP — service-name DNS. Compose creates a network with an embedded DNS resolver, and
each service is resolvable by its name, so the rewrite target is `http://backend:8000`.
That value is baked at build time (`ARG BACKEND_URL=http://backend:8000` in
`frontend/Dockerfile`) and also set at run time so `docker compose config` shows it.
Same string works on EC2 because the service is still named `backend` there.

**Q: Explain your `depends_on`. Why isn't it enough?**
`db: condition: service_healthy`, `migrate: condition: service_completed_successfully`,
and `frontend: depends_on backend service_healthy`. Plain `depends_on` only orders
*container start*, which is why Compose v2 adds conditions — Postgres accepting
connections is not the same as `pg_isready` returning true, and an API that started
before migrations finished returns 500. Even so, conditions do not mean "the app is
usable", which is why my Selenium tests use explicit waits rather than sleeping.

**Q: What is `restart: unless-stopped` vs `"no"`?**
The long-running services use `unless-stopped` (or `always`) so a crash is recovered by
Docker. `migrate`, `seed`, `test` and `selenium` are one-shot jobs — `restart: "no"`,
because a migration that failed and loops would thrash the database.

**Q: How do you keep Postgres from being reachable from the internet?**
Two things: `5432`/`6379` are never published (no `ports:` on those services), and they
live on the `data` network declared `internal: true`, which strips the default route to
the host network. The instance security group additionally only accepts 3000/8000 from the
ALB's group.

**Q: What is `x-backend-env` and the `<<:` merge?**
A YAML anchor. Compose ignores top-level keys starting with `x-`, so it is the standard
place for shared state; `&backend-env` defines it and `*backend-env` references it, and
`<<: *backend-env` merges it so `seed` can add `DEMO_PASSWORD` on top. Without it the same
twelve variables would be pasted four times and drift apart.

**Q: Where do secrets live?**
`.env` at the repo root, gitignored; `.env.example` documents the keys. Compose
interpolates `${SECRET_KEY:?copy .env.example to .env first}` — the `:?` makes an unset
variable a hard failure at parse time instead of a container running with an empty secret.
Passwords must stay alphanumeric because they are interpolated into `DATABASE_URL`.

**Q: Useful Compose commands beyond `up`.**
```bash
docker compose config            # the resolved file; catches interpolation bugs
docker compose ps                # states + health
docker compose logs -f backend
docker compose exec db psql -U adoptimizer -d adoptimizer
docker compose up -d --build frontend
docker compose run --rm seed     # run: for one-off containers, up: for services
docker compose down              # keeps volumes; -v destroys them
```

**Q: What would you change about Compose for real production?**
Compose files are per-host; multi-host needs Swarm or Kubernetes. For a real deploy I'd
move to ECS Fargate or EKS, pull the image from ECR instead of building on the instance
(slower boot, needs the Docker daemon and build cache on every box), and use RDS instead
of a Postgres container.

---

## 6. Selenium testing and test execution — 2 marks

**Q: What does your test suite actually check?**
Five tests in `tests/selenium/test_application.py`: the landing page CTA renders,
`/api/health` answers *through the Next proxy* with `env == "dev"` and a non-empty
`instance`, an anonymous `/api/auth/me` is 401, login lands on `/dashboard` and the
post-login `hero-band` element is visible, and the upload page shows `drop-zone`.
Task 6's requirement is "open the application and verify a web element" — that is the
login test plus `data-testid` locators.

**Q: Why `data-testid` instead of XPath or CSS classes?**
`driver.find_element(By.CSS_SELECTOR, '[data-testid="hero-cta"]')`. XPath and class-based
selectors break when someone restyles; a `data-testid` is an explicit contract between the
component and the test. Tailwind class names are also not unique, so `.rounded-sm` would
match half the page.

**Q: What is the difference between implicit and explicit waits, and which do you use?**
Implicit applies globally and makes every call wait until the timeout; explicit
(`WebDriverWait(driver, TIMEOUT).until(EC.element_to_be_clickable(...))`) waits for a
condition on one element. Mixing the two is a known footgun — the timeouts compound. My
`helpers.py` uses explicit waits only, with `SELENIUM_TIMEOUT` (default 20), and the login
helper waits on `EC.url_contains("/dashboard")` because the redirect is what proves
authentication, not that a pixel appeared.

**Q: What is the difference between `find_element` and `find_elements`? When does a test
fail versus error?**
`find_element` raises `NoSuchElementException` if nothing matches; `find_elements`
returns an empty list. A failed assertion is `AssertionError` (the app is wrong); an
exception from Selenium is an *error* (the test can't reach the app) — the distinction
matters when reading CI output.

**Q: How do you run it locally and in a container?**
```bash
pip install -r tests/selenium/requirements.txt
APP_BASE_URL=http://localhost:3000 DEMO_PASSWORD=... pytest tests/selenium -v
# or with the Chrome container:
docker compose --profile selenium up --build selenium
```
The containerised path sets `REMOTE_WEBDRIVER_URL=http://chrome:4444/wd/hub`, so
`conftest.py` builds a remote `WebDriver` against `selenium/standalone-chrome` instead of
`webdriver-manager` downloading a local driver. `shm_size: 2gb` is required — Chrome
crashes on the default 64 MB `/dev/shm`.

**Q: How do you run Selenium against the deployed AWS app?**
`APP_BASE_URL="http://<alb-dns>"` plus the demo password, which lives in
`/opt/ad-optimizer/.demo-password` on the instance (mode 600) — the deploy doc has the
Session Manager one-liner. It passing over the ALB URL is the evidence that the balancer,
the container and the proxy chain all work end to end.

**Q: Headless — why, and what changes?**
`--headless=new` on a server or CI box: no display, so no X server, faster and fewer
dependencies. Window size still has to be set explicitly because responsive breakpoints
depend on it; a test that passes headless and fails headed is usually a viewport issue.

**Q: What would you add if this were a real suite?**
Page objects for the multi-page flow, and a pytest fixture that creates a throwaway user
per run instead of sharing `demo@example.com` — concurrent runs on the same account fight
over the uploaded CSV. Also `--maxfail=1` and reruns on flaky CI, and screenshots on
failure attached to the report.

**Q: What is the difference between Selenium and the backend test suite?**
Selenium drives a real browser over HTTP, so it covers the Next.js rewrite, cookies and
hydration — things `backend/tests` cannot see because they call ASGI in-process. They are
complementary layers of the same test pyramid, and both run in CI.

---

## If you get stuck

Say what you do know and get specific: "that rule is in `terraform/security.tf`, the
instance group only accepts 3000 from the ALB group — I'd need a minute on the rest of
it." Never guess a flag name out loud. And never claim you ran something you did not:
if a question lands on a step you skipped, say which file implements it and how you'd
verify it.
