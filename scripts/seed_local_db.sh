#!/bin/sh
# Runs inside the postgres container, from /docker-entrypoint-initdb.d, which the
# entrypoint executes only when it initialises a new data directory. A database that
# already exists is never touched.
#
# The dump comes off the host directory restore_local_db.sh writes to, mounted at /seed.
# No dump means no data: the backend migrates an empty database to head on startup, which
# is enough for most work.
#
# Nothing here may exit nonzero. The entrypoint aborts initdb on a failing script and the
# container never goes healthy, so backend and worker never start — a worse outcome than
# any restore problem this can hit.
set -e

DUMP=/seed/latest.dump

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
echo "seed: done"
