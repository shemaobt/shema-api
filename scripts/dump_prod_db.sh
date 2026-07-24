#!/usr/bin/env bash
# Dump the production database and upload it to the restricted bucket, where
# scripts/restore_local_db.sh picks it up.
#
#   ./scripts/dump_prod_db.sh
#
# Reads production, writes nothing to it. pg_dump runs inside the compose postgres
# image, so the host needs docker and gcloud but no local postgres client.
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
# Arm the cleanup and tighten the mode before the file exists: a dump that dies
# halfway would otherwise leave world-readable production data behind.
umask 077
trap 'rm -f "$FILE"' EXIT INT TERM
# --no-owner/--no-privileges: the roles on Neon do not exist in the local container,
# and a restore that tries to reassign them fails on every object.
docker compose run --rm --no-deps -T --entrypoint pg_dump db \
  --format=custom --no-owner --no-privileges "$DB_URL" > "$FILE"

echo "==> uploading to gs://$BUCKET/$FILE"
gcloud storage cp "$FILE" "gs://$BUCKET/$FILE" --project="$PROJECT_ID"

echo
echo "Done. Developers pick it up with: ./scripts/restore_local_db.sh"
