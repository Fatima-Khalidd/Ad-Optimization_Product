#!/usr/bin/env bash
# Section A, task 3 - install Docker on the EC2 instance and bring the stack up.
# Ubuntu 22.04/24.04. Idempotent: safe to re-run.
#
#   git clone https://github.com/Fatima-Khalidd/Ad-Optimization_Product.git
#   cd Ad-Optimization_Product
#   sudo BRANCH=devops-lab bash scripts/bootstrap-ec2.sh
#
# BRANCH matters: the Dockerfiles, Compose file and Terraform live on devops-lab, not main.
# After it finishes the app is on http://<instance-public-dns>:3000 and the API on :8000.

set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/Fatima-Khalidd/Ad-Optimization_Product.git}"
APP_DIR="${APP_DIR:-/opt/ad-optimizer}"
BRANCH="${BRANCH:-main}"
# Optional: pass the load balancer DNS so the final message prints a working URL.
ALB_DNS="${ALB_DNS:-}"
# Per-instance Redis is pointless once the Auto Scaling Group adds a second node, so on
# EC2 the login limiter defaults to process memory. Terraform passes one shared ElastiCache
# endpoint here when rate_limit_storage_uri is set.
RATE_LIMIT_STORAGE_URI="${RATE_LIMIT_STORAGE_URI:-memory://}"

if [ "$(id -u)" -ne 0 ]; then echo "run with sudo: sudo bash $0"; exit 1; fi

echo "== 1. Install Docker Engine + the Compose plugin =="
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
# git and curl are needed even when Docker is already installed, for steps 3 and 4.
apt-get install -y -qq ca-certificates curl gnupg git >/dev/null
if command -v docker >/dev/null 2>&1; then
  echo "docker already present: $(docker --version)"
else
  # get.docker.com installs docker-ce, docker-cli and docker-compose-plugin in one pass.
  curl -fsSL https://get.docker.com | sh
fi
systemctl enable --now docker >/dev/null 2>&1
docker --version
docker compose version

echo
echo "== 2. Let the login user run docker without sudo =="
for candidate in "${SUDO_USER:-}" ubuntu admin ec2-user; do
  [ -n "$candidate" ] || continue
  if id -u "$candidate" >/dev/null 2>&1; then
    usermod -aG docker "$candidate" && echo "added $candidate to the docker group (re-login to apply)"
  fi
done

echo
echo "== 3. Fetch the application =="
mkdir -p "$APP_DIR"
if [ -d "$APP_DIR/.git" ]; then
  git -C "$APP_DIR" fetch --depth 1 origin "$BRANCH"
  git -C "$APP_DIR" reset --hard "origin/$BRANCH"
else
  git clone --depth 1 --branch "$BRANCH" "$REPO_URL" "$APP_DIR"
fi

echo
echo "== 4. Instance identity from the EC2 metadata service =="
# IMDSv2: a token is required before the metadata call, and it is scoped to link-local only.
TOKEN=$(curl -fsS -X PUT "http://169.254.169.254/latest/api/token" \
  -H "X-aws-ec2-metadata-token-ttl-seconds: 21600" 2>/dev/null || true)
INSTANCE_ID=$(curl -fsS -H "X-aws-ec2-metadata-token: ${TOKEN:-}" \
  http://169.254.169.254/latest/meta-data/instance-id 2>/dev/null || echo "unknown")
AZ=$(curl -fsS -H "X-aws-ec2-metadata-token: ${TOKEN:-}" \
  http://169.254.169.254/latest/meta-data/placement/availability-zone 2>/dev/null || echo "unknown")
# Off EC2 - a VirtualBox VM, a lab PC, Codespaces - there is no metadata service, and the
# hostname labels the node just as well for the distribution demo.
if [ "$INSTANCE_ID" = "unknown" ]; then
  INSTANCE_ID="$(hostname)"
  AZ="not-aws"
fi
echo "instance-id=$INSTANCE_ID  az=$AZ"

echo
echo "== 5. Environment file for the Compose stack =="
ENV_FILE="$APP_DIR/.env"
if [ ! -f "$ENV_FILE" ]; then
  DEMO_PASSWORD="$(openssl rand -hex 12)"
  umask 077
  cat > "$ENV_FILE" <<EOF
POSTGRES_USER=adoptimizer
POSTGRES_DB=adoptimizer
POSTGRES_PASSWORD=$(openssl rand -hex 16)
SECRET_KEY=$(openssl rand -hex 32)
ENV=dev
# The load balancer targets port 3000 on this instance, and the API health check needs
# port 8000 reachable from the ALB's security group, so bind on all interfaces here.
BACKEND_BIND=0.0.0.0
BACKEND_PORT=8000
FRONTEND_PORT=3000
INSTANCE_LABEL=$INSTANCE_ID
DEMO_EMAIL=demo@example.com
DEMO_PASSWORD=$DEMO_PASSWORD
RATE_LIMIT_STORAGE_URI=$RATE_LIMIT_STORAGE_URI
EOF
  chmod 600 "$ENV_FILE"
  echo "$DEMO_PASSWORD" > "$APP_DIR/.demo-password"
  chmod 600 "$APP_DIR/.demo-password"
  echo "wrote $ENV_FILE (mode 600) with generated secrets"
else
  echo "keeping the existing $ENV_FILE"
fi
grep -q '^INSTANCE_LABEL=' "$ENV_FILE" || printf 'INSTANCE_LABEL=%s\n' "$INSTANCE_ID" >> "$ENV_FILE"

echo
echo "== 6. Build and start =="
cd "$APP_DIR"
docker compose up -d --build

echo
echo "== 7. Seed the demo client (idempotent, skips if it already exists) =="
docker compose --profile seed run --rm seed || echo "seed skipped or failed - see docs/DEVOPS.md"

echo
echo "== 8. What is running =="
docker compose ps
docker volume ls --filter name=adopt-
curl -sS http://127.0.0.1:8000/api/health; echo

cat <<INFO

Through the load balancer (the graded path) : http://${ALB_DNS:-<alb-dns>}/
This instance, if your IP is allowed       : http://$(curl -fsS -H "X-aws-ec2-metadata-token: ${TOKEN:-}" http://169.254.169.254/latest/meta-data/public-hostname 2>/dev/null || echo '<public-dns>'):3000
API health, names this node                : http://127.0.0.1:8000/api/health  (instance label: $INSTANCE_ID)
Demo password (mode 600)                   : sudo cat $APP_DIR/.demo-password
Logs                                       : cd $APP_DIR && docker compose logs -f backend
INFO
