# Local development

Everything runs through Docker Compose. Runtime secrets are never committed: they live in GCP
Secret Manager, in the `shemaobt-secrets` project, and a Compose sidecar fetches them at
startup. Cloud Run gets the same values through its deploy.

Locally the only secret needed is the JWT signing key; the database is the local `db`
container, and Compose never points at Neon. Production additionally needs its Neon
connection string.

Outgoing mail reads two more on Cloud Run — `tripod_backend_email_provider` (`log`, `resend`
or `microsoft_graph`) and `tripod_backend_resend_api_key`. Compose reads both too, but treats
them as optional: when unreadable, the provider falls back to `log` and no e-mail leaves a
local machine. The sender is **not** a secret: `EMAIL_FROM_ADDRESS` is unset everywhere and
defaults to `noreply@shemaywam.com`, the address the code has always sent from. It must stay a
verified sender on the Resend domain — pointing it at another address is an administrative
change on the provider first, and a rejected sender surfaces only as a log line, never as an
error to the caller.

> Bringing up the composed API — the integration branch, on its own port, with a database of
> its own — is a different procedure, and it is in [RUNNING-LOCALLY.md](../RUNNING-LOCALLY.md).

## Prerequisites

1. Install the gcloud CLI.
2. Ask a project admin for access to the secrets project.
3. Authenticate, both for yourself and for the credentials Docker will use:

```sh
gcloud auth login
gcloud auth application-default login
```

4. Check it worked. If this prints a value, you are set:

```sh
gcloud secrets versions access latest --secret=tripod_backend_jwt_secret --project=shemaobt-secrets
```

## Running the stack

```sh
SECRETS_PROJECT_ID=shemaobt-secrets docker compose up --build backend
```

A database that does not exist yet is migrated to head as it is created, so the stack comes up
usable with no extra step. You apply migrations by hand for the other cases: a migration
written since the stack came up, and a database restored from a dump older than the newest
migration.

```sh
docker compose run --rm backend sh -c "set -a && . /run/secrets/.env && set +a && uv run alembic upgrade head"
docker compose run --rm backend sh -c "set -a && . /run/secrets/.env && set +a && uv run pytest tests"
```

`run --rm` starts a container of its own and throws it away, so neither of those needs the
stack to be up.

## Granting app access

Access is per application. A seed script creates each app row and its roles, and nobody
reaches an application until somebody grants them one of those roles. A fresh account holds
none, so the access dependency answers 403 with the message telling the person to ask.

```sh
docker compose exec backend sh -c "set -a && . /run/secrets/.env && set +a && \
  uv run python scripts/seed_apps_roles.py"
docker compose exec backend sh -c "set -a && . /run/secrets/.env && set +a && \
  uv run python scripts/grant_app_role.py <email> <app_key> <role_key>"
```

A platform admin with Secret Manager access runs it. The grant script is idempotent per user
and app: a second run updates the existing grant rather than adding a second one. There is
also a self-service path through the access-request route, reviewed by an admin, whose
automatic approval is off by default.

For the resource request form the role keys are `equipe`, `mesa`, `gestor` and `lider`,
mirroring the frontend's own capability map. GATE-02 (OBT-448, 27/aug/2026) answered that
**anyone with an account** reaches the form — `apps.auto_approve = true` — while Parte C and
the Painel stay closed by capability. The first mesa and Gestor accounts are still granted
with the command above; turning that into a process is BE-17 (OBT-477), which blocks nothing.

`scripts/seed_resource_requests.py` fills the module's own tables with the prototype's ten
board cards and the one fund they draw from. It is idempotent and safe to re-run, which
matters because `rr_fund_movements` is append-only and a doubled run could not be corrected
with an UPDATE.

**It takes the e-mail of an existing account**, and refuses to run without one:

```sh
uv run python -m scripts.seed_resource_requests <email>   # or RR_SEED_AUTHOR=<email>
```

Every request and every movement it writes names that person as author, because `created_by`
stopped being nullable when the gate answered accounts. The account is **looked up, never
created**: inventing one would put a fabricated human in `users`, which is exactly what the
invented `solicitante` names in the fixture exist to avoid.

GATE-01 (OBT-447, 26/aug/2026) confirmed **Shema Línguas** and left the other four names of
PRD v1.1 §3 undecided, so one fund is written and `provisional = false`. Its allocation is
**sample money** — asked for the real figures, the client answered that none exist yet and
asked to leave them open, since the Gestores fill each fund themselves. A real deployment
therefore seeds no allocation at all: its ledger starts at the first Gestor movement. Three of
the ten cards carry no fund, which is not a gap — the mesa assigns one at triage, so a request
in `triagem` legitimately has none.

## Data in the local database

`docker compose up` populates the database for you. On a database that does not exist yet, a
seed container downloads the newest dump from the dump bucket and Postgres restores it while
it creates the cluster. The download happens once and is reused, so later rebuilds restore
from disk with no network. Postgres runs the seed only while creating its data directory, so
an existing database is never overwritten.

To replace the data in a database you already have, which the seed path will not touch, run
`scripts/restore_local_db.sh`. It stops the backend and worker, recreates the local database,
restores, replays the Sound Necklace pilot, applies any migrations written since the dump was
taken, and starts back what it stopped.

The pilot needs replaying because production carries the Ruth pilot's artifacts but none of
the rows that bind them to a project — those only ever existed in the dev database, so no
production dump will ever have them. The replay script guards every statement, so applying it
twice is a no-op, and it is written against the production schema rather than dev's.

**It asserts no consent.** The collection-consent column is `false` on every binding it
writes. That column is asserted by hand, by a human, through the seed script's
`--consent` flag, and nobody ever recorded it for the pilot rows. A seed file must not put an
agreement into your database that never happened, so do not flip it to make a gate pass.

Its project grant is keyed on the platform-admin flag rather than on a person, because naming
one address would leave every other developer with a project they cannot open.

When the pilot changes in dev, the seed file is regenerated from the dev database rather than
edited by hand. Read the rows out of dev through a throwaway container, with the connection
string passed in the environment rather than as an argument:

```sh
DEV="$(gcloud secrets versions access latest \
  --secret=tripod_backend_neon_database_url_local --project=shemaobt-secrets)" \
  docker compose run --rm --no-deps -T -e DEV --entrypoint sh db \
  -c 'psql "$DEV" -tAc "SELECT ... FROM sn_audio_refs"'
```

Emit `INSERT` statements for the audio bindings, the pilot's project row and its language row,
and name only columns that exist in a restored production dump — dev carries columns from
branches that never merged, and a seed naming one of those fails on everybody else's machine.

To skip the production data entirely:

```sh
SEED_FROM_DUMP=0 docker compose up backend
```

That covers both halves: the seed container does not download, and the seed script ignores a
dump an earlier run left behind. You get an empty database migrated to head, which is enough
for most work. Nothing on this path can block the stack — no credentials, no bucket access, a
failed download, a restore that skips objects: each one logs a line and leaves you with an
empty database.

**The dump is not anonymized.** It carries real emails, password hashes and user content. On
disk it is readable by any local account, and restoring puts the same data unencrypted in a
Docker volume. Do not do this on a shared machine. When you no longer need the data:

```sh
docker compose down -v
rm .local-dump/latest.dump
SEED_FROM_DUMP=0 docker compose up backend
```

`SEED_FROM_DUMP=0` is not optional here. Deleting the file is precisely what makes the seed
container fetch a fresh copy — it decides on whether the dump is present, never on whether you
want it — so the first two lines on their own arm the next `docker compose up` to pull
production straight back down. Keep the variable set for as long as you want the machine
clean.

The database itself asks for a password — `POSTGRES_PASSWORD`, `tripod-local` unless you
override it — so the published port is not an open door onto that data for every account on
the machine. Socket connections inside the container stay trusted, which is what
`docker compose exec db psql` and the seed hook use, so nothing here needs it.

## The dump bucket

Dumps live in `gs://tripod-db-dumps`. Taking one is a manual admin procedure, deliberately not
a script in this repository: it reads production and writes nothing to it.

```sh
umask 077                                    # the file below is production data
FILE="tripod-$(date -u +%Y%m%dT%H%M%SZ).dump"

if PGURL="$(gcloud secrets versions access latest \
  --secret=tripod_backend_neon_database_url --project=shemaobt-secrets)" \
  docker compose run --rm --no-deps -T -e PGURL --entrypoint sh db \
  -c 'pg_dump --format=custom --no-owner --no-privileges "$PGURL"' > "$FILE.partial" \
  && [ -s "$FILE.partial" ]; then
  mv "$FILE.partial" "$FILE"
  gcloud storage cp "$FILE" "gs://tripod-db-dumps/$FILE" --project=shemaobt-secrets
  rm "$FILE"
else
  echo "dump failed — nothing uploaded"; rm -f "$FILE.partial"
fi
```

The `umask` is part of the procedure, not decoration: the file it writes is production data.
Staging it as `.partial` and uploading only on success matters for the same kind of reason — a
redirect writes whatever the command produced before it failed, so an aborted dump would
otherwise publish a truncated file.

Three details matter. The connection string travels through the environment rather than as an
argument, because argv is readable by any local process and it carries the production
password. Dump with `--no-owner --no-privileges`, or a restore fails on every object, since
the Neon roles exist nowhere locally. And run it through the `db` container so its `pg_dump`
major matches production — `pg_dump` refuses a server newer than itself and aborts with an
empty file.

Access is granted per named account, as Storage Object Viewer, and never to a group, a domain
or any of the all-users principals. The legacy project-wide bindings a new bucket is created
with have to be removed, since they hand read access to every viewer on the project. The
bucket has uniform bucket-level access, public access prevention, versioning, and a 180-day
lifecycle rule.

## Hebrew text data

Passage extraction from the Hebrew text needs a text-fabric download of roughly 300 MB on
first run, behind a Compose profile:

```sh
docker compose --profile bhsa up -d --build
curl http://localhost:8000/api/bhsa/status
```

A sidecar downloads the data into a shared volume and a second container tells the backend to
load it into memory. It persists across restarts through that volume.
