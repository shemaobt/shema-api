#!/usr/bin/env bash
# Replace the local dev database with the newest production dump from the bucket.
#
#   ./scripts/restore_local_db.sh                      # newest dump
#   ./scripts/restore_local_db.sh tripod-2026....dump  # a specific one
#
# Destroys whatever is in the local container. It touches nothing remote.
set -euo pipefail

BUCKET="${DUMP_BUCKET:-tripod-db-dumps}"
PROJECT_ID="${SECRETS_PROJECT_ID:-shemaobt-secrets}"
DB_NAME="${LOCAL_DB_NAME:-tripod}"

cd "$(dirname "$0")/.."

FILE="${1:-}"
if [ -z "$FILE" ]; then
  echo "==> finding the newest dump in gs://$BUCKET"
  FILE=$(gcloud storage ls "gs://$BUCKET/*.dump" --project="$PROJECT_ID" | sort | tail -1)
  [ -n "$FILE" ] || { echo "no dumps in gs://$BUCKET — run scripts/dump_prod_db.sh" >&2; exit 1; }
else
  FILE="gs://$BUCKET/$(basename "$FILE")"
fi

LOCAL_FILE=$(mktemp -t tripod-dump)
trap 'rm -f "$LOCAL_FILE"' EXIT

echo "==> downloading $FILE"
gcloud storage cp "$FILE" "$LOCAL_FILE" --project="$PROJECT_ID"

echo "==> starting the local database"
docker compose up -d --wait db

echo "==> recreating $DB_NAME"
# FORCE drops the open connections a running backend holds; without it the DROP
# blocks until every session goes away.
docker compose exec -T db psql -U postgres -d postgres \
  -c "DROP DATABASE IF EXISTS $DB_NAME WITH (FORCE)" \
  -c "CREATE DATABASE $DB_NAME"

echo "==> restoring"
docker compose exec -T db pg_restore -U postgres -d "$DB_NAME" --no-owner --no-privileges < "$LOCAL_FILE"

echo "==> applying migrations written since the dump"
docker compose run --rm --entrypoint sh backend \
  -c 'set -a && . /run/secrets/.env && set +a && uv run alembic upgrade head'

echo
echo "Local database restored from $(basename "$FILE")."
