#!/bin/sh
# Runs inside the postgres container, from /docker-entrypoint-initdb.d, which the
# entrypoint executes only when it initialises a new data directory. A database that
# already exists is never touched.
#
# The dump is at /seed/latest.dump, put there by the db-seed container or by
# restore_local_db.sh. No dump means no data: the backend migrates an empty database to
# head on startup, which is enough for most work.
#
# SEED_FROM_DUMP is read here as well as in db-seed. That container skips the download, but
# a dump an earlier run already left in the directory would still be restored, so opting
# out has to cover this half too.
#
# Nothing here may exit nonzero. The entrypoint aborts initdb on a failing script and the
# container never goes healthy, so backend and worker never start — a worse outcome than
# any restore problem this can hit.
set -e

DUMP=/seed/latest.dump
PILOT=/pilot/sn-pilot.sql

if [ "$SEED_FROM_DUMP" = "0" ]; then
  echo "seed: SEED_FROM_DUMP=0, starting with an empty database"
  exit 0
fi

if [ ! -f "$DUMP" ]; then
  echo "seed: no dump present, starting with an empty database"
  exit 0
fi

echo "seed: restoring $DUMP into $POSTGRES_DB"
if ! pg_restore --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  --no-owner --no-privileges "$DUMP"; then
  echo "seed: pg_restore reported errors — see above for which objects were skipped."
  echo "seed: for a clean start, 'docker compose down -v' and bring the stack back up"
  echo "seed: with SEED_FROM_DUMP=0."
fi

if [ -f "$PILOT" ]; then
  echo "seed: replaying the Sound Necklace pilot"
  if ! psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" --quiet \
    --set ON_ERROR_STOP=1 --file "$PILOT"; then
    echo "seed: the pilot overlay did not apply — the Sound Necklace will have no audios."
    echo "seed: the rest of the database is fine."
  fi
fi
echo "seed: done"
