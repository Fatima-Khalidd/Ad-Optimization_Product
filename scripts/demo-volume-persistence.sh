#!/usr/bin/env bash
# Section A, task 4 - Docker volumes and data persistence.
#
# Proves that application data lives on named volumes rather than inside a container
# writable layer: destroy the containers, bring them back, and the data is still there.
#
#   bash scripts/demo-volume-persistence.sh
#
# Nothing here removes volumes. The one command that would (`docker compose down --volumes`)
# is printed at the end as the counter-example - do not run it during the demo.

set -euo pipefail

if docker compose version >/dev/null 2>&1; then COMPOSE="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then COMPOSE="docker-compose"
else echo "Docker is not installed or not on PATH."; exit 1
fi

$COMPOSE ps --format '{{.Name}}\t{{.Status}}' >/dev/null 2>&1 || {
  echo "Stack is not running. Start it first: docker compose up -d --build"
  exit 1
}

banner() { printf '\n=== %s ===\n' "$1"; }

banner "1. Named volumes that exist"
docker volume ls --filter name=adopt-
$COMPOSE volumes

banner "2. Where the database volume lives on the host"
docker volume inspect adopt-pgdata \
  --format 'name={{ .Name }} driver={{ .Driver }} mountpoint={{ .Mountpoint }}'

banner "3. State before the recreation"
ROWS_BEFORE=$($COMPOSE exec -T db psql -U "${POSTGRES_USER:-adoptimizer}" -d "${POSTGRES_DB:-adoptimizer}" \
  -tAc "select count(*) from users;" | tr -d '[:space:]')
echo "users table rows: $ROWS_BEFORE"
$COMPOSE exec -T db psql -U "${POSTGRES_USER:-adoptimizer}" -d "${POSTGRES_DB:-adoptimizer}" \
  -c "select id, email, role from users order by id;"

# A probe file written through the backend container, into the appstorage volume.
$COMPOSE exec -T backend python -c \
  "import pathlib,datetime;pathlib.Path('storage/probe.txt').write_text('PERSISTED ' + datetime.datetime.now().isoformat() + chr(10))"
echo "probe written to storage/probe.txt:"
$COMPOSE exec -T backend cat storage/probe.txt

banner "4. Destroy the containers (not the volumes)"
$COMPOSE stop backend db
docker rm -f adopt-backend adopt-db >/dev/null
$COMPOSE ps --format '{{.Name}}\t{{.Status}}' || true
echo "^ both containers are gone; the volumes still exist:"
docker volume ls --filter name=adopt-

banner "5. Recreate from the same volumes"
$COMPOSE up -d db
until $COMPOSE exec -T db pg_isready -q -U "${POSTGRES_USER:-adoptimizer}"; do
  echo "waiting for Postgres to accept connections..."; sleep 2
done
$COMPOSE up -d --no-deps backend

banner "6. State after the recreation - identical means persistence works"
ROWS_AFTER=$($COMPOSE exec -T db psql -U "${POSTGRES_USER:-adoptimizer}" -d "${POSTGRES_DB:-adoptimizer}" \
  -tAc "select count(*) from users;" | tr -d '[:space:]')
echo "users table rows: $ROWS_AFTER (was $ROWS_BEFORE)"
[ "$ROWS_BEFORE" = "$ROWS_AFTER" ] || { echo "MISMATCH - investigate before the demo"; exit 1; }

echo "the new container reads the probe file written by the deleted one:"
$COMPOSE exec -T backend cat storage/probe.txt

banner "7. Also check the API still reports the same data"
curl -sSf http://127.0.0.1:8000/api/health || echo "(backend still warming up; retry in a few seconds)"

echo
echo "Task 4 evidence: sections 3, 4 and 6 above, plus 'docker volume inspect adopt-pgdata'."
echo
echo "Counter-example you should be able to explain but NOT run: 'docker compose down --volumes'"
echo "removes adopt-pgdata and adopt-appstorage with it, and the demo client would have to be"
echo "re-seeded with 'docker compose --profile seed run seed'."
