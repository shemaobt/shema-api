# shema-api

The FastAPI server behind the Shemá oral Bible translation tools: the Internalization Room,
the Facilitator Desk, the Sound Necklace, the Oral Collector and the Annotation Studio.

## Commands

Package manager is `uv`, on Python 3.11: `uv python install 3.11`, then `uv sync --frozen --group dev`.

```sh
JWT_SECRET_KEY=test-secret-for-pytest-only uv run pytest tests/ -v
uv run mypy app/
uv run ruff check . && uv run ruff format --check .
DATABASE_URL=sqlite+aiosqlite:///./boot-check.db JWT_SECRET_KEY=test-secret-for-ci-only INNGEST_DEV=1 uv run python -c "import app.main"
PYTHONWARNINGS=error::UserWarning uv run alembic heads   # exactly one head, no duplicate ids
```

The suite needs `ffmpeg` and `ffprobe` on the host, because it measures recordings with them exactly as the deployed image does. It runs on SQLite and touches neither the local Postgres nor Neon. The test database is a file per pytest run, in the system temporary directory and named by the process, so two runs in one checkout do not corrupt each other; `DATABASE_URL` is honoured when set, and the run then uses that file and leaves it behind.

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

- [`docs/doctrine/`](docs/doctrine/) — Marcia's [`DOCTRINE.md`](docs/doctrine/vendor/DOCTRINE.md), vendored at the pin in [`DOCTRINE_PIN`](docs/doctrine/DOCTRINE_PIN) and binding on every change here. Read it before touching a prompt, the turn loop or the model seam; a change to one of her artifacts needs a ruling in [`rulings/`](docs/doctrine/rulings/).
- [`CONTEXT.md`](CONTEXT.md) — the glossary. Use its terms in code, tests and commits.
- [`docs/adr/`](docs/adr/) — one hard-to-reverse decision each. Conventions and runbooks: [local development](docs/local-development.md), [database](docs/database.md), [API conventions](docs/api-conventions.md), [code style](docs/code-style.md), [CI](docs/ci.md), [buckets](docs/buckets.md), [the divine name, spoken](docs/divine-name-speakable-form.md), and the pinned [Sound Necklace snapshot](docs/sound_necklace_interview_package.md).
- [`RUNNING-LOCALLY.md`](RUNNING-LOCALLY.md) — the composed API on its own port. [`http/`](http/) — request examples.
