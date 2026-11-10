#!/bin/sh
# Run from an authorized Linux deployment host with DNS and TLS access ready.
set -eu

repo_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
env_file=${TESTFLOW_ENV_FILE:-"$repo_dir/.env.production"}
mode=${1:-preflight}
case "$mode" in preflight|--execute) ;; *) echo 'Usage: deploy.sh [preflight|--execute]' >&2; exit 2 ;; esac
test -f "$env_file" || { echo 'Production environment file is missing' >&2; exit 2; }

revision=$(git -C "$repo_dir" rev-parse HEAD)
configured_revision=$(sed -n 's/^BUILD_SHA=//p' "$env_file" | tail -n 1)
test "$configured_revision" = "$revision" || {
    echo 'BUILD_SHA must equal the checked-out Git revision' >&2; exit 2;
}
git -C "$repo_dir" diff --quiet
git -C "$repo_dir" diff --cached --quiet

compose() {
    docker compose --env-file "$env_file" -f "$repo_dir/compose.prod.yml" "$@"
}

compose config --quiet
compose build
compose up -d db redis
compose run --rm --no-deps api python manage.py check --deploy
compose run --rm --no-deps api python manage.py makemigrations --check --dry-run
compose run --rm --no-deps api python manage.py migrate --plan
compose run --rm --no-deps api python -c 'from django.conf import settings; assert settings.IMPORT_INFERENCE_URL, "OCR runtime is not configured"'

if [ "$mode" = preflight ]; then
    echo 'Preflight passed. Deployment was not started.'
    exit 0
fi

: "${BACKUP_DIR:?Set BACKUP_DIR before production migration}"
BACKUP_DIR="$BACKUP_DIR" TESTFLOW_ENV_FILE="$env_file" /bin/sh "$repo_dir/infra/backup.sh"
compose run --rm --no-deps api python manage.py migrate --noinput
compose up -d api worker recovery web
compose ps

site_domain=$(sed -n 's/^SITE_DOMAIN=//p' "$env_file" | tail -n 1)
curl --fail --silent --show-error --max-time 20 "https://$site_domain/healthz"
echo
printf 'Deployment health probe passed for revision %s\n' "$revision"
