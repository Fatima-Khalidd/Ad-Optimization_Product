#!/usr/bin/env bash
# CSC418 Task 4 — named volume and data persistence after container recreation.
#
#   bash scripts/volume-persistence-demo.sh
#
# Needs the stack already running and seeded:
#   docker compose up -d --build
#   docker compose --profile seed run --rm migrate-and-seed
#
# The point of the demonstration: the PostgreSQL container is destroyed and built again from the
# image, and the rows are still there, because they were never inside the container — they are in
# the named volume.

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

VOLUME=ad-optimization_pgdata

banner() {
    printf '\n===== %s =====\n' "$1"
}

rows() {
    docker compose exec -T postgres psql -U adoc -d adoc -tAc "$1"
}

banner "1. the named volumes this project created"
docker volume ls
echo
docker volume inspect "$VOLUME" --format 'name={{.Name}}
driver={{.Driver}}
mountpoint={{.Mountpoint}}'

banner "2. row counts before the container is destroyed"
echo "users:         $(rows 'select count(*) from users;')"
echo "clients:       $(rows 'select count(*) from clients;')"
echo "analysis_runs: $(rows 'select count(*) from analysis_runs;')"

banner "3. the container's own filesystem, for comparison"
echo "Everything under /var/lib/postgresql/data in this container is a mount point, not content:"
docker compose exec -T postgres sh -c 'ls -l /var/lib/postgresql/data | head -5'
docker compose exec -T postgres sh -c 'du -sh /var/lib/postgresql/data'

banner "4. destroy the container"
# stop leaves it on disk; `rm -f -s` also deletes that stopped container. The volume is a separate
# object, so neither command touches it.
docker compose stop postgres
docker compose rm -f -s postgres
echo "containers now running:"
docker ps --format '{{.Names}}  {{.Status}}'

banner "5. prove the data outlived it, straight from the volume"
# A brand-new, throwaway container mounts the same volume with nothing else attached to it.
echo "files in the volume, from an unrelated container:"
docker run --rm -v "$VOLUME":/pgdata alpine sh -c 'ls /pgdata | head -5'
echo "database directory size: $(docker run --rm -v "$VOLUME":/pgdata alpine sh -c 'du -sh /pgdata' | cut -f1)"

banner "6. recreate the container from the image"
docker compose up -d postgres

banner "7. wait for it to report healthy"
for _ in $(seq 1 30); do
    state=$(docker inspect --format '{{.State.Health.Status}}' ad-optimization-postgres-1 2>/dev/null || echo starting)
    [ "$state" = healthy ] && break
    sleep 2
done
echo "postgres health: $state"

banner "8. row counts after recreation"
echo "users:         $(rows 'select count(*) from users;')"
echo "clients:       $(rows 'select count(*) from clients;')"
echo "analysis_runs: $(rows 'select count(*) from analysis_runs;')"

banner "9. the application still works on the recreated database"
docker compose exec -T backend python -c \
    "import urllib.request as u; print(u.urlopen('http://127.0.0.1:8000/api/health', timeout=5).read().decode())"

banner "done"
echo "If the counts in step 8 match step 2, the data came from the named volume, not the container."
