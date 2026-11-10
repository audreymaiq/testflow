#!/bin/sh
# Run on the deployment host; BACKUP_DIR must be a protected off-app directory.
set -eu

repo_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
env_file=${TESTFLOW_ENV_FILE:-"$repo_dir/.env.production"}
backup_dir=${BACKUP_DIR:?Set BACKUP_DIR to an absolute protected directory}
case "$backup_dir" in /*) ;; *) echo 'BACKUP_DIR must be absolute' >&2; exit 2 ;; esac
test -f "$env_file" || { echo 'Production environment file is missing' >&2; exit 2; }
umask 077
mkdir -p "$backup_dir"
stamp=$(date -u +%Y%m%dT%H%M%SZ)
partial="$backup_dir/.testflow-$stamp.incomplete"
final="$backup_dir/testflow-$stamp"
mkdir "$partial"

compose() {
    docker compose --env-file "$env_file" -f "$repo_dir/compose.prod.yml" "$@"
}

compose exec -T db pg_dump -U testflow -Fc testflow > "$partial/database.dump"
compose run --rm --no-deps --entrypoint tar worker -C /app/media/private -cf - . > "$partial/media.tar"
(cd "$partial" && sha256sum database.dump media.tar > SHA256SUMS)
printf 'revision=%s\ncreated_utc=%s\n' "$(git -C "$repo_dir" rev-parse HEAD)" "$stamp" > "$partial/manifest.txt"
mv "$partial" "$final"
printf 'Backup created: %s\n' "$final"
