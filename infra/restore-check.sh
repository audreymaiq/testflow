#!/bin/sh
# Restore a backup into an isolated temporary database and media directory.
set -eu

backup_dir=${1:?Usage: restore-check.sh /absolute/path/to/testflow-backup}
case "$backup_dir" in /*) ;; *) echo 'Backup path must be absolute' >&2; exit 2 ;; esac
test -f "$backup_dir/database.dump" && test -f "$backup_dir/media.tar" && test -f "$backup_dir/SHA256SUMS" || {
    echo 'Backup is incomplete' >&2; exit 2;
}
(cd "$backup_dir" && sha256sum -c SHA256SUMS)

restore_root=${RESTORE_TMP_ROOT:-/tmp}
case "$restore_root" in /*) ;; *) echo 'RESTORE_TMP_ROOT must be absolute' >&2; exit 2 ;; esac
restore_dir=$(mktemp -d "$restore_root/testflow-restore-XXXXXXXX")
container="testflow-restore-$$"
cleanup() {
    docker rm -f "$container" >/dev/null 2>&1 || true
    rm -rf -- "$restore_dir"
}
trap cleanup EXIT HUP INT TERM

docker run --rm -d --name "$container" \
    -e POSTGRES_PASSWORD=restore-check-only -e POSTGRES_DB=restorecheck \
    postgres:17.6-alpine >/dev/null
ready=0
attempt=0
while [ "$attempt" -lt 30 ]; do
    if docker exec "$container" pg_isready -U postgres -d restorecheck >/dev/null 2>&1; then
        ready=1
        break
    fi
    attempt=$((attempt + 1))
    sleep 1
done
test "$ready" -eq 1 || { echo 'Isolated PostgreSQL did not start' >&2; exit 1; }

docker exec -i "$container" pg_restore -U postgres -d restorecheck \
    --no-owner --no-privileges < "$backup_dir/database.dump"
printf 'Restored migrations: '
docker exec "$container" psql -U postgres -d restorecheck -At \
    -c 'SELECT COUNT(*) FROM django_migrations'
printf 'Restored users: '
docker exec "$container" psql -U postgres -d restorecheck -At \
    -c 'SELECT COUNT(*) FROM accounts_user'
printf 'Restored exams: '
docker exec "$container" psql -U postgres -d restorecheck -At \
    -c 'SELECT COUNT(*) FROM catalog_exam'
mkdir "$restore_dir/media"
tar -C "$restore_dir/media" -xf "$backup_dir/media.tar"
printf 'Restored media files: '
find "$restore_dir/media" -type f | wc -l
printf 'Isolated restore verified: %s\n' "$backup_dir"
