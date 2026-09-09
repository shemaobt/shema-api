# Database

PostgreSQL through the SQLAlchemy 2 async engine and `asyncpg`: Neon in production, the local
`db` container under Compose. The suite runs on SQLite and reaches neither.

## Sessions

Take the `AsyncSession` injected by the `get_db` dependency. Never build an engine or a
session inside a router or a service — a second engine has its own pool, its own transaction,
and none of the lifecycle the application manages.

Keep the I/O async the whole way: `await session.execute(...)`, `await session.commit()`. A
synchronous call on this path blocks the event loop for every other request on the worker.

All queries live in the service layer; see [API conventions](api-conventions.md) and
[ADR 0009](adr/0009-routers-never-touch-the-database.md).

## Migrations

Every schema change is an Alembic migration, and nothing is applied by hand. Autogenerate the
revision after changing the models, read what it produced, and only then apply it:

```sh
uv run alembic revision --autogenerate -m 'short description'
uv run alembic upgrade head
```

The graph must stand at exactly one head. Alembic does not fail on a duplicate revision id —
it warns and carries on, leaving two heads — so CI asks the graph directly, and the newest
migration is walked down and back up on a clean database to prove its downgrade is honest.

Production migrations run on deploy after a merge to `main`; staging's run on every push to
`dev`.

Values added to an enum are the case to watch. The Postgres type is invisible to SQLite, so a
new member passes the suite and fails only where the real type exists: the migration owes an
`ALTER TYPE`.
