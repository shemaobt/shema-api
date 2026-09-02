# Backend Agent Guidelines (tripod-backend)

This file defines backend-specific conventions for agents working in this repository. It follows the structure and intent of `reference-agents-md/BACKEND.md`, adapted to FastAPI + SQLAlchemy + Alembic and GCP Secret Manager.

---

## 1. Stack and Runtime

- **Framework**: FastAPI
- **Server**: Uvicorn (dev) / Gunicorn (production)
- **Package manager**: `uv` (`pyproject.toml` + `uv.lock`)
- **Database**: PostgreSQL via SQLAlchemy 2 async engine + `asyncpg` — Neon in production, the local `db` container for Compose. `pytest` runs on SQLite and touches neither.
- **Migrations**: Alembic
- **Validation / schemas**: Pydantic v2
- **Auth**: JWT (`python-jose`) + passlib (`pbkdf2_sha256`)

Use these stack choices and existing project patterns. Do not introduce an alternative framework, ORM, or migration tool.

### Package management with uv

- Add dependency: `uv add <package>`
- Add dev dependency: `uv add --dev <package>`
- Sync environment: `uv sync`
- Run commands: `uv run <command>`
- Regenerate lockfile: `uv lock`

---

## 2. Project Structure

```text
tripod-backend/
├── app/
│   ├── main.py
│   ├── api/
│   ├── core/
│   ├── db/models/
│   ├── models/
│   ├── services/
│   └── utils/
├── alembic/
├── scripts/
├── tests/
├── pyproject.toml
├── uv.lock
├── Dockerfile
├── Dockerfile.dev
└── docker-compose.yml
```

### API layer: access only

- `app/api` is an access layer for HTTP only.
- Routers parse/validate input, call services, map expected business exceptions to `HTTPException`.
- **NEVER access the database directly from routers.** No `db.execute()`, `db.add()`, `db.commit()`, `db.delete()`, `select()`, or any SQLAlchemy query in `app/api/`. All data access MUST go through service functions in `app/services/`.
- **NEVER import SQLAlchemy models or query constructs in routers** (except `AsyncSession` for dependency injection). If a router needs data, create a service function for it.
- **NEVER import `fastapi.HTTPException` in services.** Services raise business exceptions from `app/core/exceptions.py` (`NotFoundError`, `ConflictError`, `RoleError`, etc.); routers map them to HTTP status codes or let the global exception handlers do it.
- Do not put business rules, orchestration logic, or model creation in routers. The only logic allowed is: input parsing, calling services, and mapping service exceptions to HTTP responses.

### Services, core, models

- `app/services`: business logic and **all** data access. Every database query lives here.
- `app/core`: config, DB session management, auth dependencies, exception definitions.
- `app/models`: request/response schemas and typed DTOs.
- `app/db/models`: SQLAlchemy table models only.

---

## 3. API and Error Conventions

- Keep one router per domain area and register in `app/main.py`.
- Protected routes use shared auth dependencies in `app/core/auth_middleware.py`.
- Raise specific exceptions for business cases in services; map them in API layer.
- For infrastructure/unexpected failures, use default framework behavior (avoid over-wrapping all exceptions).

---

## 4. Database and Alembic

- Use injected `AsyncSession` from `get_db`; do not create ad-hoc engines/sessions in routers/services.
- Keep database I/O async (`await session.execute(...)`, `await session.commit()`).
- Every schema change must be reflected in Alembic migration files under `alembic/versions`.
- Do not apply manual schema changes outside Alembic workflow.

---

## 5. Code Style

- Prefer async end-to-end in API and service paths.
- Keep strong typing on public functions (params + return type).
- Prefer explicit typed models over generic `dict` when shape is known.
- Keep services function-oriented and composable.
- Keep public service function docstrings present and concise.
- Keep code self-documenting; avoid comments that restate code.
- Use docstrings, not inline comments. A `#` comment explaining *why* belongs in the
  module or function docstring instead, where it is found by someone reading the API
  rather than only by someone already inside the body. Sphinx `#:` attribute docs are
  not inline comments.

---

## 6. Runtime Secrets

- Do not rely on committed local `.env` files for runtime secrets.
- Runtime secrets are stored in GCP Secret Manager and loaded in:
  - local Docker Compose via `gcp-secrets` service
  - Cloud Run via `--set-secrets` in deploy workflow
- Required secrets:
  - **Local (docker-compose):** `tripod_backend_jwt_secret`. The database is the local `db`
    container, not a secret — Compose never points at Neon.
  - **Production (Cloud Run):** `tripod_backend_neon_database_url`, `tripod_backend_jwt_secret`
  - **E-mail (Cloud Run):** `tripod_backend_email_provider` (`log`, `resend` or
    `microsoft_graph`) and `tripod_backend_resend_api_key`. Compose reads both too, but
    treats them as optional: when unreadable, the provider falls back to `log` and no
    e-mail leaves a local machine. The sender is **not** a secret: `EMAIL_FROM_ADDRESS`
    is unset everywhere and defaults to `noreply@shemaywam.com`, the address the code has
    always sent from. It must stay a verified sender on the Resend domain — pointing it
    at another address is an administrative change on the provider first, and a rejected
    sender surfaces only as a log line, never as an error to the caller.
- Production dumps live in `gs://tripod-db-dumps`, readable only by explicitly named
  accounts. The `db-seed` container downloads one to `.local-dump/` before `db` starts, and
  a from-scratch database seeds itself from it — no manual step. `restore_local_db.sh`
  replaces the data in a database that already exists. `SEED_FROM_DUMP=0` opts out of both.
  See `scripts/fetch_local_dump.sh`, `seed_local_db.sh` and `restore_local_db.sh`. Taking a
  dump is a manual admin procedure documented in the README, deliberately not a script in
  the repository.
- The Sound Necklace pilot is not in any production dump: `scripts/seed_sn_pilot.sql`
  replays its `sn_audio_refs` (and the project and language they depend on) after the
  restore. Written against the production schema, not dev's.

---

## 7. Docker-only Commands

- Start backend:
  - `SECRETS_PROJECT_ID=<SECRETS_PROJECT_ID> docker compose up --build backend`
- Run migrations:
  - `SECRETS_PROJECT_ID=<SECRETS_PROJECT_ID> docker compose run --rm backend sh -c "set -a && . /run/secrets/.env && set +a && uv run alembic upgrade head"`
- Run tests:
  - `SECRETS_PROJECT_ID=<SECRETS_PROJECT_ID> docker compose run --rm backend sh -c "set -a && . /run/secrets/.env && set +a && uv run pytest tests"`

## 8. Git Workflow & Pull Requests

When the user says the code is ready, asks to "create a PR", or says "prepare the PR":

1. **Create a new branch** from the current HEAD with a descriptive name (e.g. `feat/restructure-dashboard-books`).
2. **Commit in small, scoped commits** — each commit should cover a single logical change (e.g. "Add BooksPage with book grid", "Rewrite DashboardPage as statistics overview", "Update routes in App.tsx"). Avoid lumping all changes into a single commit. Break them correctly by scope.
3. **Push the branch** to the remote with `-u` to set upstream tracking.
4. **Create a pull request** using `gh pr create` targeting `main` with:
   - A concise title (under 70 characters)
   - A detailed body with a `## Summary` section (bullet points of what changed and why) and a `## Test plan` section (how to verify the changes)
5. **Return the PR URL** to the user.

Use `gh` CLI for all GitHub operations (push, PR creation). Never force-push or amend published commits.

---

## 9. Model Use on the Sound Necklace Answer Path

This section governs one path only: what happens to a storyteller's recorded answer
between the microphone and `relatorio-mapeamento.md`. Models are used freely elsewhere
in this codebase (`services/i18n`, `services/project_health`, `services/translation_helper`,
platform TTS); none of those touch an interview answer, and none are constrained here.

On this path the count is deliberately small, because a model that edits a person's own
words is a step no reader of the artifact can see afterwards. Each one has to be worth
defending.

1. **Transcription** — `services/platform/stt.py`. Verbatim, no cleanup.
2. **Disfluency cleanup** — `services/platform/disfluency.py`. Runs after transcription
   and before translation.
3. **Translation to English** — `services/platform/translation.py`. Explicitly forbidden
   from cleaning, summarising or completing.

The cleanup is the addition (owner decision, 2026-08-08). It is allowed because of
*where* it sits: it runs before the facilitator confirms the transcript on screen, so a
human still reads and confirms every sentence that reaches an artifact. Nothing a model
wrote enters a report unreviewed.

Moving it after the confirmation would break exactly that property, and is not a
refactor to make casually. Adding a fourth step on this path means adding it here with
the same argument: what a human sees, and when they see it.

Since the 2026-09-01 scope cut (ENG-690) this path has **no caller**: the Colar's SPA now
ends at the scene and phrase segmentation. The code is dormant, not gone — the rules above
still govern it, and they govern whoever picks it up. What the package is, and what it
takes to use it elsewhere, is
[`docs/sound_necklace_interview_package.md`](docs/sound_necklace_interview_package.md).

---

## 10. Summary Checklist

- [ ] Keep `app/api` thin and service-driven — **zero database access in routers**.
- [ ] Keep all database queries in `app/services/` — routers only call service functions.
- [ ] Keep service exceptions in `app/core/exceptions.py` — never import `HTTPException` in services.
- [ ] Keep SQLAlchemy usage async and session-injected.
- [ ] Keep schema changes tracked with Alembic migrations.
- [ ] Keep runtime secrets in GCP Secret Manager.
- [ ] Keep the Sound Necklace answer path to the three model steps in §9.
- [ ] Keep backend commands running inside Docker Compose.
- [ ] Keep strong typing and concise service docstrings.
