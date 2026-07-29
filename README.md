# tripod-backend

Shared API backend for Tripod — a platform powering multiple language and translation tools. Handles authentication (JWT), app-scoped RBAC, and core data (languages, projects, organizations, phases).

**Stack:** FastAPI · SQLAlchemy 2 async · Alembic · PostgreSQL (Neon) · uv · Docker · Cloud Run

## Architecture

```
app/
├── api/           # FastAPI routers (auth, languages, orgs, projects, phases, roles, rag, bhsa, shema)
├── core/          # Config, database engine, middleware, exceptions, app version
├── db/
│   └── models/    # SQLAlchemy ORM models (auth · language · org · phase · project)
├── models/        # Pydantic request/response schemas
└── services/      # Business logic, one package per domain:
                   #   auth/ · authorization/ · language/ · org/ · phase/ · project/
                   #   rag/ (document upload, query, embeddings)
                   #   bhsa/ (Hebrew text-fabric passage extraction)
                   #   shema/ (Ecossistema Shemá project management)
alembic/           # Database migrations
scripts/           # One-off scripts (e.g. seed_apps_roles.py)
tests/             # Async pytest suite, one file per service domain
http/              # .http request examples (VS Code REST Client / JetBrains)
```

Each layer has a single responsibility: routers call services, services use db models, Pydantic models handle serialization. No business logic lives in routers; no DB calls live outside services.

## Configuration

Settings are read from the environment by `app/core/config.py`. [`.env.example`](.env.example) lists every variable the app reads; the first two are required and the app refuses to start without them:

| Variable | Why it is required |
|---|---|
| `DATABASE_URL` | There is no fallback DSN — a default would silently point the app at the wrong database. |
| `JWT_SECRET_KEY` | An empty signing key would sign every access and refresh token with `""`. |

Everything else has a working default or is inert when unset. Runtime secrets come from GCP Secret Manager (see [Local development](#local-development)) — `.env.example` is a reference, not a file to fill in with real values.

## Shemá module

`Ecossistema Shemá` — project management for the network of multimodal Bible-translation projects run by YWAM/JOCUM field teams — is built inside this backend rather than as a separate service, so it reuses the existing auth, roles, projects, storage and notification infrastructure.

| Layer | Home |
|---|---|
| Routers | `app/api/shema/`, mounted at `/api/shema` |
| Business logic and data access | `app/services/shema/`, one file per operation |
| Request/response schemas | `app/models/shema.py` |
| SQLAlchemy tables | `app/db/models/shema.py` |
| Migrations | `alembic/versions/`, shared with the rest of the platform |

`GET /api/shema/health` reports the module name, the app version and whether the module can reach the database.

> The existing `project_health` module is a different instrument from Shemá's health assessment (SHM-08) — read it before assuming reuse, and keep the two data models apart.

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

## Local development

Secrets are stored in GCP Secret Manager (project `shemaobt-secrets`) and fetched at startup by a Docker Compose sidecar.

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

> Use a Neon dev branch for local work to avoid touching production data.

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

## API examples

[`http/`](http/) contains `.http` request files for health, auth, and roles. See [`http/README.md`](http/README.md) for token usage.
