# tripod-backend

Shared API backend for Tripod — a platform powering multiple language and translation tools. Handles authentication (JWT), app-scoped RBAC, and core data (languages, projects, organizations, phases).

**Stack:** FastAPI · SQLAlchemy 2 async · Alembic · PostgreSQL (Neon) · uv · Docker · Cloud Run

## Architecture

```
app/
├── api/           # FastAPI routers, one module per domain area
├── core/          # Config, database engine, middleware, exceptions
├── db/
│   └── models/    # SQLAlchemy ORM models, grouped by domain
├── models/        # Pydantic request/response schemas
└── services/      # Business logic and all data access, one package per domain. Among them:
                   #   rag/ (document upload, query, embeddings)
                   #   bhsa/ (Hebrew text-fabric passage extraction)
                   #   oral_collector/ (field recordings, storytellers, review flags)
                   #   device/ (tablets: the single-use code that claims one into a
                   #            project, and the long-lived credential it buys — which
                   #            authenticates the room app, rotates without a new claim,
                   #            and is revoked by unlinking)
alembic/           # Database migrations
scripts/           # One-off scripts (e.g. seed_apps_roles.py)
tests/             # Async pytest suite, one file per service domain
http/              # .http request examples (VS Code REST Client / JetBrains)
docs/              # Module designs — written before the module, not after
```

Each layer has a single responsibility: routers call services, services use db models, Pydantic models handle serialization. No business logic lives in routers; no DB calls live outside services.

## CI/CD (GitHub Actions)

| Trigger | What happens |
|---|---|
| Pull request opened/updated | ruff check + ruff format + pytest |
| Reviewer requested on PR | Claude PR review (Sonnet 4.6) — inline + summary comments |
| `deep-review` label added | Claude PR review (Opus 4.7) — adds `[ARCHITECTURE]` critique |
| `@claude` mention in PR/issue | Claude answers in-thread (Opus 4.7) |
| Weekly (Mon 09:00 UTC) | Claude usage rollup → optional Discord webhook |
| Push to `main` | Build image → `alembic upgrade head` → deploy to Cloud Run |

Config is pulled from GCP Secret Manager at container startup — no env vars are set manually in production or CI.

### Code review

Claude reviews PRs on demand, not on every push:

- **Standard review** — request a reviewer in the GitHub UI. Claude (Sonnet 4.6) reads `CLAUDE.md`, the diff, and posts inline `[BLOCKING]` / `[SUGGESTION]` / `[NIT]` comments plus a summary verdict. Re-request the reviewer to re-run on new commits.
- **Deep review** — add the `deep-review` label to the PR. The same review re-runs on Opus 4.7 with an extra `[ARCHITECTURE]` pass that critiques the design as a whole. Use this for large refactors, new modules, or anything where the standard review felt thin. Remove and re-add the label to re-run.
- **Follow-ups** — comment `@claude <question>` on a PR or issue (Opus 4.7). Useful for "explain this change", "suggest a service-layer refactor for this endpoint", or "is there a simpler approach here?".

Drafts and bot-authored PRs are skipped automatically. Linting and tests still run on every push as usual.

### Cost monitoring

OAuth/Pro-Max billing has no per-token dashboard, so each Claude run reports its own usage:

- **Per-run summary** — every Actions run for `claude-review` and `claude-mention` writes a token / model / cost-equivalent table to the run's job summary (visible at the top of the Actions run page).
- **PR cost footer** — each PR review posts (and updates in place) a single comment with the same numbers, so reviewers can see what each review cost without leaving the PR.
- **Weekly Discord rollup** — `claude-cost-report.yml` runs Mondays at 09:00 UTC. It downloads the per-run cost artifacts from the prior 7 days, aggregates totals by model tier and workflow, and posts an embed to the `DISCORD_WEBHOOK_URL` repo secret. If the secret is unset, the workflow still produces the report in its job summary; only the Discord post is skipped. Trigger an ad-hoc rollup with `gh workflow run claude-cost-report.yml -f lookback_days=14`.

Costs are computed at public API list pricing as a stable comparison metric — actual billing under OAuth is your Pro/Max subscription's quota.

## Bucket CORS

`gcs-cors.json` and `sound-necklace-cors.json` are **applied by hand and by nobody else** —
no workflow, script or startup path reads them. They can drift from the live buckets
silently, and one of them already did. Read the bucket before trusting the file:

```sh
gcloud storage buckets describe gs://sound-necklace-private --format="json(cors_config)"
gcloud storage buckets update  gs://sound-necklace-private --cors-file=sound-necklace-cors.json
```

The Sound Necklace SPA only ever issues signed **GET** against GCS — uploads go through
`PUT /api/sound-necklace/sessions/{id}/resources`, not a signed URL — so `PUT` and
`x-goog-resumable` do not belong in its allowlist.

`Range` stays in `responseHeader`, but not for the reason first written here. It **is** a
CORS-safelisted request header: the Fetch standard safelists `range` when the value parses
as a single range with a non-null start, which is what an ordinary seek sends
(`bytes=1048576-`). Those do not preflight. What is not safelisted is a suffix range —
`bytes=-500`, the tail of a file — because browsers historically never emitted them; those
still preflight, and GCS answers preflights with `responseHeader` in
`Access-Control-Allow-Headers`. The same field also becomes `Access-Control-Expose-Headers`
on simple requests, which is what lets a player read `Content-Range` and `Content-Length`
back. Keeping all four costs nothing and covers both paths.

Sources: [Fetch, CORS-safelisted request-header](https://fetch.spec.whatwg.org/#cors-safelisted-request-header) ·
[Cloud Storage CORS](https://docs.cloud.google.com/storage/docs/cross-origin)

### The Cloud Run origins

`sound-necklace-718681737495.us-central1.run.app` is the **deterministic** URL —
`SERVICE-PROJECTNUMBER.REGION.run.app` — which can be written down before the service
exists. The form is confirmed live: the same pattern for `tripod-backend` answers `200` on
`/health`.

`sound-necklace-f7ssqjozfq-uc.a.run.app` is the legacy form, whose second field is a random
hash Cloud Run assigns **at creation**. The `sound-necklace` service does not exist yet
(both URLs 404 exactly as an invented one does), so that hash cannot have been read off a
deployment — it does not identify anything. Cloud Run still gives every service a
hash-based URL alongside the deterministic one, so once the service is deployed, read the
real URL and replace this entry rather than deleting the line and assuming the deterministic
one is enough.

## Local development

Secrets are stored in GCP Secret Manager (project `shemaobt-secrets`) and fetched at startup by a Docker Compose sidecar.

> Bringing up the **composed API** — the integration branch, on its own port, with a database
> of its own — is a different procedure, and it is in [RUNNING-LOCALLY.md](RUNNING-LOCALLY.md).
> That is the one to follow when a client has to be developed against facilitator routes that
> have not reached `main` yet.

### Prerequisites

1. **Install the [gcloud CLI](https://cloud.google.com/sdk/docs/install).**

2. **Request secret access.** Ask a project admin to add you on the project.

3. **Authenticate your local gcloud:**
   ```bash
   gcloud auth login                       # interactive login with the email that was granted access
   gcloud auth application-default login   # sets Application Default Credentials (used by Docker)
   ```

4. **Verify access works** (optional but recommended):
   ```bash
   gcloud secrets versions access latest \
     --secret=tripod_backend_jwt_secret \
     --project=shemaobt-secrets
   ```
   If this prints a value, you're good. If it fails, double-check that step 2 was done for your email and that you logged in with the correct account in step 3.

### Running the stack

```bash
# Start the backend (defaults to project shemaobt-secrets)
SECRETS_PROJECT_ID=shemaobt-secrets docker compose up --build backend

# In another terminal — apply migrations, seed, run tests
docker compose exec backend sh -c "set -a && . /run/secrets/.env && set +a && uv run alembic upgrade head"
docker compose exec backend sh -c "set -a && . /run/secrets/.env && set +a && uv run python scripts/seed_apps_roles.py"
docker compose exec backend sh -c "set -a && . /run/secrets/.env && set +a && uv run pytest tests"
```

Compose services run against the `db` container, never against Neon. An empty database is
migrated to head on startup, so the stack comes up usable with no extra step. (`pytest` is
separate: it runs on SQLite and reaches neither database.)

### Granting app access

Access is per application. `scripts/seed_apps_roles.py` creates the `apps` row and its roles;
nobody reaches an application until somebody grants them one of those roles. A fresh account
holds none, so `require_app_access` answers **403** with the message that tells the person to
ask for access.

```bash
docker compose exec backend sh -c "set -a && . /run/secrets/.env && set +a && \
  uv run python scripts/grant_app_role.py <email> <app_key> <role_key>"
```

**Who runs it:** a platform admin with Secret Manager access on `shemaobt-secrets`. The script
is idempotent per user and app — a second run updates the existing grant rather than adding a
second one.

There is also a self-service path (`POST /api/access-requests`, reviewed by an admin); whether
approval is automatic is `apps.auto_approve`, off by default, and the role an approval grants
comes from `DEFAULT_ROLE_BY_APP_KEY` in `app/services/access_request/_default_roles.py`.

For **`resource-request-form`** the roles are `equipe`, `mesa` and `gestor`, mirroring the
frontend's `capabilities.ts`. GATE-02 (OBT-448, 27/aug/2026) answered that **anyone with an
account** reaches the form — `apps.auto_approve = true` — while Parte C and the Painel stay
closed by capability. The first mesa and Gestor accounts are still granted with the command
above; turning that into a process is BE-17 (OBT-477), which blocks nothing. A fourth role,
**Líder de Base**, arrives with BE-16 (OBT-476).

`scripts/seed_resource_requests.py` fills the module's own tables with the prototype's ten
board cards and the one fund they draw from. It is idempotent and safe to re-run, which
matters because `rr_fund_movements` is append-only and a doubled run could not be corrected
with an UPDATE.

**It takes the e-mail of an existing account**, and refuses to run without one:

```bash
uv run python -m scripts.seed_resource_requests <email>   # ou RR_SEED_AUTHOR=<email>
```

Every request and every movement it writes names that person as author, because
`created_by` stopped being nullable when the gate answered accounts. The account is
**looked up, never created**: inventing one would put a fabricated human in `users`, which
is exactly what the invented `solicitante` names in the fixture exist to avoid.

GATE-01 (OBT-447, 26/aug/2026) confirmed **Shema Línguas** and left the other four names of
PRD v1.1 §3 undecided, so one fund is written and `provisional = false`. Its allocation is
**sample money** — asked for the real figures, the client answered that none exist yet and
asked to leave them open, since the Gestores fill each fund themselves. A real deployment
therefore seeds no allocation at all: its ledger starts at the first Gestor movement. Three
of the ten cards carry no fund, which is not a gap — the mesa assigns one at triage, so a
request in `triagem` legitimately has none.

### Data in the local database

`docker compose up` populates the database for you. On a database that does not exist yet,
the `db-seed` container downloads the newest dump from `gs://tripod-db-dumps` into
`.local-dump/latest.dump`, and postgres restores it while it creates the cluster. No script
to run first — real data is the default.

The download happens once. `db-seed` reuses a dump that is already in the directory, so
later rebuilds — `docker compose down -v`, `docker volume rm tripod-api_db_data` — restore
from disk with no network. Delete the file to pull a fresh one. Postgres runs the seed only
while creating its data directory, so an existing database is never overwritten.

To replace the data in a database you already have, which the seed path will not touch:

```bash
./scripts/restore_local_db.sh
```

That stops the backend and worker, recreates the local `tripod` database, restores, replays
the Sound Necklace pilot, applies any migrations written since the dump was taken, and
starts back what it stopped.

To skip the production data entirely:

```bash
SEED_FROM_DUMP=0 docker compose up backend
```

That covers both halves — `db-seed` does not download, and the seed script ignores a dump
an earlier run already left behind. You get an empty database migrated to head, which is
enough for most work.

Nothing in this path can block the stack. No gcloud credentials, no access to the bucket, a
failed download, a `pg_restore` that skips objects — each one logs a line and leaves you
with an empty database. `db-seed` gates the `db` service, so it always exits clean.

#### The Sound Necklace pilot

Production carries the 49 acousteme artifacts of the Ruth pilot but none of the
`sn_audio_refs` that bind them to a project, and `sn_audio_refs` is the only thing a
project gate can stand on. Those rows were only ever created in the dev database, so no
production dump will ever have them. `scripts/seed_sn_pilot.sql` replays them — plus the
pilot project and its language, which production also lacks — right after the restore. Both
routes apply it: the initdb hook on a from-scratch cluster, and `restore_local_db.sh`, which
drops and recreates the database on a cluster that already exists and so never reaches that
hook.

Every statement guards itself, so applying it twice is a no-op, and it is written against
the **production** schema rather than dev's, which carries columns from unmerged branches.
Two things it deliberately does not assert:

- `consent_present` is `false` on every binding. That column is the collection consent of
  PRD §12/O6, which a human asserts by hand through
  `scripts/seed_sn_audio_refs.py --consent`. Nobody recorded it for the pilot rows, and a
  seed file must not put an agreement into your database that never happened.
- The project grant is keyed on `is_platform_admin`, not on a person. `list_user_projects`
  has no admin bypass, so the pilot needs a `project_user_access` row to appear in any
  project list at all — but naming one address would leave every other developer with a
  project they cannot open.

To refresh it after the pilot changes in dev:

```bash
DEV="$(gcloud secrets versions access latest \
  --secret=tripod_backend_neon_database_url_local --project=shemaobt-secrets)" \
  docker compose run --rm --no-deps -T -e DEV --entrypoint sh db \
  -c 'psql "$DEV" -tAc "SELECT ... FROM sn_audio_refs"'
```

Emit `INSERT` statements for `sn_audio_refs`, the pilot row of `projects` and its
`languages` row, and name only columns that exist in a restored production dump.

**The dump is not anonymized.** It carries real emails, password hashes and user content.
On disk it is `chmod 644` — postgres reads it through the bind mount as its own uid — so
any local account can read it, and restoring puts the same data unencrypted in a Docker
volume. Do not do this on a shared machine. When you no longer need the data:

```bash
docker compose down -v
rm .local-dump/latest.dump
SEED_FROM_DUMP=0 docker compose up backend
```

`SEED_FROM_DUMP=0` is not optional here. Deleting the file is precisely what makes
`db-seed` fetch a fresh copy — it decides on whether the dump is present, never on whether
you want it — so the first two lines on their own arm the next `docker compose up` to pull
production straight back down. Keep the variable set for as long as you want the machine
clean.

The database itself asks for a password — `POSTGRES_PASSWORD`, `tripod-local` unless you
override it — so the published port is not an open door onto that data for every account on
the machine. Socket connections inside the container stay trusted, which is what
`docker compose exec db psql` and the initdb hook use, so nothing in this README needs it.

### The dump bucket

Dumps live in `gs://tripod-db-dumps` and are taken by hand by an admin — nothing schedules
this, and there is no script in the repository for it. Reads production, writes nothing
to it:

```bash
umask 077                                    # the file below is production data
FILE="tripod-$(date -u +%Y%m%dT%H%M%SZ).dump"

# Stage as .partial and upload only on success: a redirect writes whatever the command
# produced before it failed, so an aborted dump would otherwise publish a truncated file.
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

Three details that matter. The connection string goes through the environment rather than
as an argument, because argv is readable by any local process and it carries the production
password. `--no-owner --no-privileges` because the Neon roles do not exist in the local
container, so without them a restore fails on every object. And the dump runs through the
`db` container so its `pg_dump` major matches production — pg_dump refuses a server newer
than itself, so a mismatched client aborts with an empty file.

The bucket already exists. Grant a new developer access by adding their email as
**Storage Object Viewer** in the Cloud Console. Its configuration, if it ever has to be
rebuilt: uniform bucket-level access (so object ACLs cannot widen it), public access
prevention enabled, versioning on, and a 180-day lifecycle rule. Access is granted per
named account — never to a group, a domain, `allUsers` or `allAuthenticatedUsers`, and
the legacy `projectViewer`/`projectEditor` bindings a new bucket is created with have to
be removed, since they hand read access to every viewer on the project.

### BHSA (Hebrew text data)

BHSA passage extraction requires text-fabric data (~300MB download on first run). Use the `bhsa` Docker profile:

```bash
# Start backend + download BHSA data + auto-load into memory
docker compose --profile bhsa up -d --build

# Check status
curl http://localhost:8000/api/bhsa/status

# Fetch a passage
curl 'http://localhost:8000/api/bhsa/passage?ref=Ruth%201:1-6'
```

The `bhsa-fetcher` sidecar downloads text-fabric data into a shared volume (`tf_data`), then `bhsa-load` triggers the backend to load it into memory. Data persists across restarts via the Docker volume.

## Migrations

```bash
# Create (after changing models)
docker compose exec backend sh -c "set -a && . /run/secrets/.env && set +a && uv run alembic revision --autogenerate -m 'short description'"

# Apply locally (manual — never run automatically against local DB)
docker compose exec backend sh -c "set -a && . /run/secrets/.env && set +a && uv run alembic upgrade head"
```

Production migrations run automatically on deploy (after merge to `main`).

## Lint

```bash
uv run ruff check . --fix
uv run ruff format .
```

Or via Docker: `docker compose --profile lint run --rm lint`

## Module designs

[`docs/resource_requests.md`](docs/resource_requests.md) — the Resource Circle module: layout, aggregate ownership, the two client-gated seams in both variants, and the open questions with the gate that owns each.

## API examples

[`http/`](http/) contains `.http` request files for health, auth, and roles. See [`http/README.md`](http/README.md) for token usage.
