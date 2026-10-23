#!/usr/bin/env bash
# Cloud-init for each Auto Scaling instance. Terraform renders the values below through
# templatefile(), so every literal shell expansion is written as $$ in this file.
set -euxo pipefail

exec > >(tee -a /var/log/user-data.log | logger -t user-data -s 2>/dev/null) 2>&1

REPO_URL="${repo_url}"
BRANCH="${branch}"
APP_DIR=/opt/ad-optimizer
# Empty means "let scripts/bootstrap-ec2.sh choose" (process memory).
RATE_LIMIT_STORAGE_URI="${rate_limit_storage_uri}"
export REPO_URL BRANCH APP_DIR RATE_LIMIT_STORAGE_URI

echo "== owner: ${owner_tag}, branch: $BRANCH =="

# ---------------------------------------------------------------------------
# 1. Swap, so the Next.js build does not get OOM-killed on a 4 GB instance.
# ---------------------------------------------------------------------------
if [ ! -f /swapfile ]; then
  fallocate -l 2G /swapfile
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

# ---------------------------------------------------------------------------
# 2. git, then the repository. scripts/bootstrap-ec2.sh installs Docker and Compose.
# ---------------------------------------------------------------------------
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq git

if [ ! -d "$APP_DIR/.git" ]; then
  git clone --depth 1 --branch "$BRANCH" "$REPO_URL" "$APP_DIR"
fi

cd "$APP_DIR"
bash scripts/bootstrap-ec2.sh

# ---------------------------------------------------------------------------
# 3. Nothing else: bootstrap-ec2.sh has already built the images, started the stack and
#    seeded the demo client. A replacement instance runs this whole file again, which is
#    why the data lives on EBS-backed Docker volumes rather than on the instance disk.
# ---------------------------------------------------------------------------
docker compose ps

echo "== user-data finished; app on port ${app_port}, API on ${api_port} =="
