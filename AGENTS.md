# shema-api

The FastAPI server behind the Shemá oral Bible translation tools: the Internalization Room,
the Facilitator Desk, the Sound Necklace, the Oral Collector and the Annotation Studio.

## Commands

Package manager is `uv`, on Python 3.11: `uv python install 3.11`, then `uv sync --frozen --group dev`.

```sh
JWT_SECRET_KEY=test-secret-for-pytest-only uv run pytest tests/ -n 4 --dist loadfile -m "not migration and not fresh_interpreter"

uv run ruff check . && uv run ruff format --check .
DATABASE_URL=sqlite+aiosqlite:///./boot-check.db JWT_SECRET_KEY=test-secret-for-ci-only INNGEST_DEV=1 uv run python -c "import app.main"
uv run mypy app/
JWT_SECRET_KEY=test-secret-for-ci-only uv run pytest tests/ -m fresh_interpreter

env -u DATABASE_URL JWT_SECRET_KEY=test-secret-for-ci-only uv run pytest tests/ -n 4 --dist loadfile -m migration
PYTHONWARNINGS=error::UserWarning uv run alembic heads   # exactly one head, no duplicate ids
```

A test that spawns a process to prove what it proves does not run in the first line, the
`test` job's own selection. The four lines between the blank ones are the `checks` job — the
four commands the old `lint` job ran, in order, then the `fresh_interpreter` selection: the
file that opens a clean interpreter to prove something the suite's own process cannot. The
`migration` selection is the `migrations` job's own step, `DATABASE_URL` cleared: that job
sets it at job level for its Postgres container, and left in place the migration-walking
files would run against that Postgres instead of the SQLite file each builds for itself. The
three selections partition the whole suite, pinned in `tests/test_ci_gates.py`. `main` sends
fourteen files to `migration` and three to `fresh_interpreter`; this branch has eight and one.

The suite needs `ffmpeg` and `ffprobe` on the host, because it measures recordings with them exactly as the deployed image does. It runs on SQLite and touches neither the local Postgres nor Neon. The test database is one file per process, in the system temporary directory and named by the xdist worker or, in a serial run, by the pid, so two runs in one checkout and four workers in one run do not corrupt each other; `DATABASE_URL` is honoured when set, and the run then uses that one file and leaves it behind — so a run that names its own database runs serially, without `-n`. The schema is created once per process and each test is given a clean database by a sweep, not by recreating it: [ADR 0031](docs/adr/0031-one-lint-check-and-a-schema-once-per-worker.md).

## Rules

Every schema change is an Alembic migration, and nothing is applied by hand. Routers never touch the database and services never raise HTTP: [ADR 0009](docs/adr/0009-routers-never-touch-the-database.md).

All repository documentation — this file, `CONTEXT.md`, the ADRs, `README.md` and `docs/` — is written in English. Code identifiers and model prompts are not touched.

## Staging

A push to `dev` deploys the `tripod-backend-staging` Cloud Run service. It has no domain of
its own, so read the URL rather than writing it down, and point a local client at it with
`BACKEND_URL`:

```sh
gcloud run services describe tripod-backend-staging --region us-central1 --format='value(status.url)'
```

## Where the rest is

- [`CONTEXT.md`](CONTEXT.md) — the glossary. Use its terms in code, tests and commits.
- [`docs/adr/`](docs/adr/) — one hard-to-reverse decision each. Conventions and runbooks: [local development](docs/local-development.md), [database](docs/database.md), [API conventions](docs/api-conventions.md), [code style](docs/code-style.md), [CI](docs/ci.md), [buckets](docs/buckets.md), and the pinned [Sound Necklace snapshot](docs/sound_necklace_interview_package.md).
- [`docs/resource_requests.md`](docs/resource_requests.md) — the Resource Circle module: layout, aggregate ownership, the two client-gated seams in both variants, and the open questions with the gate that owns each.
- [`docs/shema.md`](docs/shema.md) — the Shemá module: the verdict on every existing capability it reuses, extends or leaves alone; why a Shemá project is not a `projects` row; and where the region dimension the platform has no column for actually lives.
- [`RUNNING-LOCALLY.md`](RUNNING-LOCALLY.md) — the composed API on its own port. [`http/`](http/) — request examples.
