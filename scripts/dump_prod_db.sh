#!/usr/bin/env bash
# Dump the production database and upload it to the restricted bucket, where
# scripts/restore_local_db.sh picks it up.
#
#   ./scripts/dump_prod_db.sh
#
# Reads production, writes nothing to it. pg_dump runs inside the compose postgres
# image, so the host needs docker and gcloud but no local postgres client.
#
# The umask and cleanup trap are armed before the file exists, so a dump that dies
# halfway leaves no world-readable production data behind. --no-owner/--no-privileges
# because the Neon roles do not exist locally and a restore would fail on every object.
#
# The connection string reaches the container through the environment rather than as an
# argument: argv is readable by any local process, and it carries the production password.
set -euo pipefail

BUCKET="${DUMP_BUCKET:-tripod-db-dumps}"
PROJECT_ID="${SECRETS_PROJECT_ID:-shemaobt-secrets}"
SECRET="${PROD_DB_SECRET:-tripod_backend_neon_database_url}"
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
FILE="tripod-${STAMP}.dump"

cd "$(dirname "$0")/.."

if [ "${1:-}" != "--yes" ]; then
  echo "This copies PRODUCTION data into gs://$BUCKET/$FILE."
  printf "Type 'yes' to continue: "
  read -r reply
  [ "$reply" = "yes" ] || { echo "aborted"; exit 1; }
fi

echo "==> reading production connection string from Secret Manager"
DB_URL=$(gcloud secrets versions access latest --secret="$SECRET" --project="$PROJECT_ID" | tr -d '\n')
[ -n "$DB_URL" ] || { echo "could not read $SECRET — run 'gcloud auth login'" >&2; exit 1; }

echo "==> dumping to $FILE"
umask 077
trap 'rm -f "$FILE"' EXIT INT TERM
PGURL="$DB_URL" docker compose run --rm --no-deps -T -e PGURL --entrypoint sh db \
  -c 'pg_dump --format=custom --no-owner --no-privileges "$PGURL"' > "$FILE"

echo "==> uploading to gs://$BUCKET/$FILE"
gcloud storage cp "$FILE" "gs://$BUCKET/$FILE" --project="$PROJECT_ID"

echo
echo "Done. Developers pick it up with: ./scripts/restore_local_db.sh"
