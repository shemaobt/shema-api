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
# Hardcoded to match the DATABASE_URL compose hands the backend. An override here
# would restore one database while the application reads another.
DB_NAME="tripod"

cd "$(dirname "$0")/.."

# Ask before the download, not after: the dump holds real user data, and once it is
# on the disk the bucket permissions no longer protect it.
if [ "${1:-}" = "--yes" ]; then
  shift
else
  echo "This puts a copy of PRODUCTION data on this machine — real emails, password"
  echo "hashes and user content. Do not run it on a shared or unencrypted machine."
  printf "Type 'yes' to continue: "
  read -r reply
  [ "$reply" = "yes" ] || { echo "aborted"; exit 1; }
fi

FILE="${1:-}"
if [ -z "$FILE" ]; then
  echo "==> finding the newest dump in gs://$BUCKET"
  FILE=$(gcloud storage ls "gs://$BUCKET/*.dump" --project="$PROJECT_ID" | sort | tail -1)
  [ -n "$FILE" ] || { echo "no dumps in gs://$BUCKET — run scripts/dump_prod_db.sh" >&2; exit 1; }
else
  FILE="gs://$BUCKET/$(basename "$FILE")"
fi

umask 077
LOCAL_FILE=$(mktemp -t tripod-dump)
trap 'rm -f "$LOCAL_FILE"' EXIT INT TERM

echo "==> downloading $FILE"
gcloud storage cp "$FILE" "$LOCAL_FILE" --project="$PROJECT_ID"

echo "==> starting the local database"
docker compose up -d --wait db

# DROP DATABASE ... FORCE only kills the sessions open right now. The backend runs with
# --reload and pool_pre_ping, so it reconnects within seconds and would serve requests
# off a half-restored schema. Stop the consumers, then put back what was running.
RUNNING=$(docker compose ps --services --filter status=running | grep -E '^(backend|worker)$' || true)
if [ -n "$RUNNING" ]; then
  echo "==> stopping $(echo "$RUNNING" | tr '\n' ' ')while the database is replaced"
  # shellcheck disable=SC2086
  docker compose stop $RUNNING
fi

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

if [ -n "$RUNNING" ]; then
  echo "==> restarting $(echo "$RUNNING" | tr '\n' ' ')"
  # shellcheck disable=SC2086
  docker compose start $RUNNING
fi

echo
echo "Local database restored from $(basename "$FILE")."
