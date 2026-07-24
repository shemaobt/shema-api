#!/bin/sh
# Runs inside the postgres container, from /docker-entrypoint-initdb.d, which the
# entrypoint executes only when it initialises a new data directory. A database that
# already exists is never touched.
#
# The dump is placed at /seed/latest.dump by the db-seed service. No dump means no
# data: the backend migrates an empty database to head on startup, which is enough
# for most work.
#
# SEED_FROM_DUMP is checked here as well as in db-seed: that service skips the download,
# but a dump pulled by an earlier run stays in the volume, and opting out covers it too.
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
pg_restore --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  --no-owner --no-privileges "$DUMP"
echo "seed: done"
