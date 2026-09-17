#!/bin/sh
# Runs in the db-seed container, before the db service starts, so `docker compose up` on a
# fresh machine ends up with real data without anyone running a script first. It only
# downloads: the restore itself is seed_local_db.sh, which postgres runs while it creates
# the cluster.
#
# It writes to the same .local-dump/latest.dump that restore_local_db.sh uses, and does
# nothing when that file is already there — so a dump pulled by either route is reused, and
# neither one re-downloads on every `up`. Delete the file to get a fresh copy.
#
# Nothing here may exit nonzero. The db service gates on this container through
# service_completed_successfully, so a failure would take the entire stack down. Missing
# credentials and an unreachable bucket are ordinary states on a new machine; they degrade
# to an empty database, which the backend then migrates to head.
#
# The dump is production data. It is chmod 644 because postgres reads it through the bind
# mount as its own uid, which also means any local account can read it — see the README.

DUMP=/seed/latest.dump
BUCKET="${DUMP_BUCKET:-tripod-db-dumps}"
PROJECT_ID="${SECRETS_PROJECT_ID:-shemaobt-secrets}"

if [ "$SEED_FROM_DUMP" = "0" ]; then
  echo "db-seed: SEED_FROM_DUMP=0, not downloading anything"
  exit 0
fi

if [ -f "$DUMP" ]; then
  echo "db-seed: $DUMP is already here, reusing it"
  exit 0
fi

export CLOUDSDK_CONFIG=/tmp/gcloud
rm -rf "$CLOUDSDK_CONFIG"
cp -r /host-gcloud "$CLOUDSDK_CONFIG" 2>/dev/null || {
  echo "db-seed: no gcloud config on the host, starting with an empty database"
  exit 0
}

echo "db-seed: looking for the newest dump in gs://$BUCKET"
FILE=$(gcloud storage ls "gs://$BUCKET/*.dump" --project="$PROJECT_ID" 2>/dev/null | sort | tail -1)
if [ -z "$FILE" ]; then
  echo "db-seed: no dump readable in gs://$BUCKET — run 'gcloud auth login' on the host, or"
  echo "db-seed: ask an admin for access. Starting with an empty database."
  exit 0
fi

echo "db-seed: downloading $FILE"
if ! gcloud storage cp "$FILE" "$DUMP.partial" --project="$PROJECT_ID"; then
  echo "db-seed: download failed, starting with an empty database"
  rm -f "$DUMP.partial"
  exit 0
fi

mv "$DUMP.partial" "$DUMP"
chmod 644 "$DUMP"
echo "db-seed: $(basename "$FILE") ready — this is PRODUCTION data, see the README"
exit 0
