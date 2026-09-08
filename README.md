# shema-api

The shared API server behind the Shemá oral Bible translation tools. It carries the
authentication and app-scoped access that all of them share, the core data of languages,
projects, organizations and phases, and the services particular to each product: the
Internalization Room, the Facilitator Desk, the Sound Necklace, the Oral Collector and the
Annotation Studio.

FastAPI · SQLAlchemy 2 async · Alembic · PostgreSQL on Neon · uv · Docker · Cloud Run

## Running it

You need the gcloud CLI, access to the secrets project, and Docker. The suite runs on the host
rather than in Compose, so it also needs `uv`, Python 3.11 and `ffmpeg`. Runtime secrets are
fetched from GCP Secret Manager at startup; nothing sensitive is committed here.

```sh
gcloud auth login && gcloud auth application-default login
SECRETS_PROJECT_ID=shemaobt-secrets docker compose up --build backend
JWT_SECRET_KEY=test-secret-for-pytest-only DATABASE_URL=sqlite+aiosqlite:///./test.db uv run pytest tests/ -v
```

The database comes up seeded and migrated. The full procedure — access, seeding from a
production dump and the warnings that go with it, the Hebrew text data — is in
[`docs/local-development.md`](docs/local-development.md).

## Where the rest is

- [`AGENTS.md`](AGENTS.md) — how to run and check everything, in one page.
- [`CONTEXT.md`](CONTEXT.md) — the glossary. It is what the words in this repository mean.
- [`docs/adr/`](docs/adr/) — the decisions, one to a file, each with what was rejected.
- [`docs/`](docs/) — conventions and runbooks.
- [`RUNNING-LOCALLY.md`](RUNNING-LOCALLY.md) — the composed API on its own port.
- [`http/`](http/) — request examples for health, auth and roles.

## Licence

See [`LICENSE.md`](LICENSE.md).
