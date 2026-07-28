#!/usr/bin/env bash
# Replace the local dev database with the newest production dump from the bucket.
#
#   ./scripts/restore_local_db.sh                      # newest dump
#   ./scripts/restore_local_db.sh tripod-2026....dump  # a specific one
#
# Destroys whatever is in the local container. It touches nothing remote.
#
# The dump is kept at .local-dump/latest.dump rather than in a temporary file: the db
# service mounts that directory, so every later rebuild of the database restores from
# it with no download. Delete the file to stop that.
#
# It is chmod 644 because postgres reads it as its own uid through the bind mount, and
# a developer with a restrictive umask would otherwise get a seed that fails. That does
# leave production data readable by other local accounts — one more reason this does
# not belong on a shared machine.
#
# Confirmation comes before the download: once the dump is on the disk, the bucket
# permissions no longer protect it. The backend and worker are stopped for the swap,
# since DROP DATABASE ... FORCE only kills the sessions open at that moment and they
# reconnect within seconds onto a half-restored schema.
set -euo pipefail

BUCKET="${DUMP_BUCKET:-tripod-db-dumps}"
PROJECT_ID="${SECRETS_PROJECT_ID:-shemaobt-secrets}"
DB_NAME="tripod"
DUMP_DIR=".local-dump"

cd "$(dirname "$0")/.."

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
  [ -n "$FILE" ] || { echo "no dumps in gs://$BUCKET — ask an admin to take one" >&2; exit 1; }
else
  FILE="gs://$BUCKET/$(basename "$FILE")"
fi

mkdir -p "$DUMP_DIR"
LOCAL_FILE="$DUMP_DIR/latest.dump"
trap 'rm -f "$LOCAL_FILE.partial"' EXIT INT TERM

echo "==> downloading $FILE to $LOCAL_FILE"
gcloud storage cp "$FILE" "$LOCAL_FILE.partial" --project="$PROJECT_ID"
mv "$LOCAL_FILE.partial" "$LOCAL_FILE"
chmod 644 "$LOCAL_FILE"

echo "==> starting the local database"
docker compose up -d --wait db

RUNNING=$(docker compose ps --services --filter status=running | grep -E '^(backend|worker)$' || true)
if [ -n "$RUNNING" ]; then
  echo "==> stopping $(echo "$RUNNING" | tr '\n' ' ')while the database is replaced"
  # shellcheck disable=SC2086
  docker compose stop $RUNNING
fi

echo "==> recreating $DB_NAME"
docker compose exec -T db psql -U postgres -d postgres \
  -c "DROP DATABASE IF EXISTS $DB_NAME WITH (FORCE)" \
  -c "CREATE DATABASE $DB_NAME"

echo "==> restoring"
if ! docker compose exec -T db pg_restore -U postgres -d "$DB_NAME" \
  --no-owner --no-privileges < "$LOCAL_FILE"; then
  echo "!!! pg_restore reported errors — see above for which objects were skipped."
  echo "!!! Continuing so the migrations and the stack come back up; re-run this script"
  echo "!!! if the database looks wrong."
fi

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
