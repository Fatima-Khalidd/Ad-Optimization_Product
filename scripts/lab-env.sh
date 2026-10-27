#!/usr/bin/env bash
# CSC418 — create the environment file that the containers read at run time.
#
#   bash scripts/lab-env.sh
#
# Configuration lives here rather than in the image, so the same image runs against any database
# and no secret is ever committed or baked into a layer. backend/.env is matched by .gitignore and
# listed in backend/.dockerignore; this file is the only place the lab's SECRET_KEY is stored.

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

TARGET=backend/.env

if [ -f "$TARGET" ]; then
    echo "$TARGET already exists — leaving it untouched."
    echo "Delete it first only if you mean to generate a new SECRET_KEY."
    exit 0
fi

# 64 hex characters. A fresh key per instance would be normal, but the AMI is baked from this
# instance, so both Auto Scaling instances inherit this one file and this one key — which is what
# lets a login cookie issued by one instance be accepted by the other.
SECRET_KEY=$(od -An -tx1 -N32 /dev/urandom | tr -d ' \n')

cat > "$TARGET" <<EOF
# Written by scripts/lab-env.sh on $(hostname) — do not commit, do not screenshot.
# ENV=dev, not prod: prod forces cookie_secure=True (app/core/settings.py) and a browser will not
# return a Secure cookie over the plain HTTP listener this lab uses, so login would fail silently.
ENV=dev
SECRET_KEY=${SECRET_KEY}
# +psycopg is required: app/core/db.py asserts the driver name, and psycopg 3 is what is installed.
DATABASE_URL=postgresql+psycopg://adoc:adoc@postgres:5432/adoc
# Read at import time (app/core/rate_limit.py), so the Redis container has to be up first.
RATE_LIMIT_STORAGE_URI=redis://redis:6379/0
STORAGE_ROOT=/app/storage
# scripts/seed_demo.py exits with status 2 rather than inventing a password. This is a synthetic
# demo account on a throwaway database, and the same value is already documented in docs/DEMO.md.
DEMO_PASSWORD=demo-password-123
EOF

chmod 600 "$TARGET"

echo "wrote $TARGET (mode 600, SECRET_KEY generated, $(wc -l < "$TARGET") lines)"
echo "verify without printing the key:  grep -v SECRET_KEY $TARGET"
