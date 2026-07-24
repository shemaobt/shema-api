#!/usr/bin/env bash
# Create (or update) the bucket that holds production dumps, and grant read access
# to named people. Idempotent: run it again with a new address to add someone.
#
#   ./scripts/provision_dump_bucket.sh alice@shemaywam.com bob@shemaywam.com
#
# Access is granted per principal, never to a group like allAuthenticatedUsers:
# these dumps carry real user data.
set -euo pipefail

BUCKET="${DUMP_BUCKET:-tripod-db-dumps}"
PROJECT_ID="${SECRETS_PROJECT_ID:-shemaobt-secrets}"
LOCATION="${DUMP_BUCKET_LOCATION:-us-central1}"
RETENTION_DAYS="${DUMP_RETENTION_DAYS:-30}"

if [ "$#" -eq 0 ]; then
  echo "usage: $0 <email> [email...]" >&2
  echo "       grants read access on gs://$BUCKET to each address" >&2
  exit 1
fi

if gcloud storage buckets describe "gs://$BUCKET" --project="$PROJECT_ID" >/dev/null 2>&1; then
  echo "==> gs://$BUCKET already exists"
else
  echo "==> creating gs://$BUCKET in $LOCATION"
  gcloud storage buckets create "gs://$BUCKET" \
    --project="$PROJECT_ID" \
    --location="$LOCATION" \
    --uniform-bucket-level-access \
    --public-access-prevention
fi

# Uniform access means object ACLs cannot quietly widen this; the bucket policy is
# the only door. Versioning keeps a fat-fingered overwrite from destroying a dump.
gcloud storage buckets update "gs://$BUCKET" --project="$PROJECT_ID" --versioning

echo "==> expiring dumps older than $RETENTION_DAYS days"
lifecycle=$(mktemp)
trap 'rm -f "$lifecycle"' EXIT
cat > "$lifecycle" <<EOF
{"rule": [{"action": {"type": "Delete"}, "condition": {"age": $RETENTION_DAYS}}]}
EOF
gcloud storage buckets update "gs://$BUCKET" --project="$PROJECT_ID" --lifecycle-file="$lifecycle"

for email in "$@"; do
  echo "==> granting read access to $email"
  gcloud storage buckets add-iam-policy-binding "gs://$BUCKET" \
    --project="$PROJECT_ID" \
    --member="user:$email" \
    --role="roles/storage.objectViewer" >/dev/null
done

echo
echo "==> verifying nothing reaches these dumps except named accounts"
# Adding readers proves nothing on its own: a bucket keeps whatever grants it already
# had, and a new one is created with legacy project bindings (projectViewer and
# friends) that hand read access to every viewer on the project. Anything broader
# than a named user or service account fails the run.
members=$(gcloud storage buckets get-iam-policy "gs://$BUCKET" --project="$PROJECT_ID" \
  --flatten="bindings[].members" --format="value(bindings.members)")
wide=$(printf '%s\n' "$members" | grep -Ev '^(user:|serviceAccount:)' | sort -u || true)

printf '%s\n' "$members" | sort -u | sed 's/^/  /'

if [ -n "$wide" ]; then
  echo >&2
  echo "REFUSING: these principals can read the dumps but are not named accounts:" >&2
  printf '%s\n' "$wide" | sed 's/^/  /' >&2
  echo >&2
  echo "Remove each one before treating this bucket as restricted, e.g.:" >&2
  echo "  gcloud storage buckets remove-iam-policy-binding gs://$BUCKET \\" >&2
  echo "    --project=$PROJECT_ID --member=<principal> --role=<role>" >&2
  echo "Roles per principal: gcloud storage buckets get-iam-policy gs://$BUCKET" >&2
  exit 1
fi

echo
echo "gs://$BUCKET is readable only by the accounts listed above."
