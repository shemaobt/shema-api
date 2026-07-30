# Backend Agent Guidelines (tripod-backend)

This file defines backend-specific conventions for agents working in this repository. It follows the structure and intent of `reference-agents-md/BACKEND.md`, adapted to FastAPI + SQLAlchemy + Alembic and GCP Secret Manager.

---

## 1. Stack and Runtime

- **Framework**: FastAPI
- **Server**: Uvicorn (dev) / Gunicorn (production)
- **Package manager**: `uv` (`pyproject.toml` + `uv.lock`)
- **Database**: PostgreSQL (Neon) via SQLAlchemy 2 async engine + `asyncpg`
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

---

## 6. Runtime Secrets

- Do not rely on committed local `.env` files for runtime secrets.
- Runtime secrets are stored in GCP Secret Manager and loaded in:
  - local Docker Compose via `gcp-secrets` service
  - Cloud Run via `--set-secrets` in deploy workflow
- Required secrets:
  - **Local (docker-compose):** `tripod_backend_neon_database_url_local` (Neon DB for dev/test), `tripod_backend_jwt_secret`
  - **Production (Cloud Run):** `tripod_backend_neon_database_url`, `tripod_backend_jwt_secret`

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

## 9. Summary Checklist

- [ ] Keep `app/api` thin and service-driven — **zero database access in routers**.
- [ ] Keep all database queries in `app/services/` — routers only call service functions.
- [ ] Keep service exceptions in `app/core/exceptions.py` — never import `HTTPException` in services.
- [ ] Keep SQLAlchemy usage async and session-injected.
- [ ] Keep schema changes tracked with Alembic migrations.
- [ ] Keep runtime secrets in GCP Secret Manager.
- [ ] Keep backend commands running inside Docker Compose.
- [ ] Keep strong typing and concise service docstrings.

---

## 10. Quality Gates

Static quality gates run in CI (on every PR) and locally via `make quality`.
Before opening a PR, run `make quality` and treat any violation as blocking. The
machine-readable reports are written to `reports/quality/`.

- **Architecture/dependencies** (`import-linter`, config in `pyproject.toml [tool.importlinter]`):
  no new cross-layer cycles; layers respected (`api > services > models > db > core`); routers must not import
  ORM directly; services must not import `fastapi`/`inngest`. Current violations are baselined via
  `ignore_imports` — **any new violation fails the PR**. To pay down the debt, remove the matching
  `ignore_imports` line when you fix it.
- **Complexity/size** (`ruff` `C901` + `PLR0915`, plus `scripts/check_module_size.py` for file
  length): Phase 0 calibrated to the current worst value. Prompt text must live in dedicated
  `*_default_prompts.py` files, which are exempt from the file-length gate.
- **Coverage** (`pytest-cov`, `fail_under` in `pyproject.toml`): Phase 0 = 66%.
- **Mutation** (`cosmic-ray`, scope `app/utils`): nightly job, **non-blocking**.

The ratchet (progressive tightening of the limits) is documented in `obt/.claude/quality-gates-plan.md`.
