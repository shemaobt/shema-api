"""What every test in this suite is given before it asks for anything.

**The database is one file per process**, named by `tests.database_naming` before anything of
the app is imported, and kept outside the working directory. A fixed name in the worktree
meant two runs in one checkout shared a database; one name for the whole of an xdist run
would mean four workers sharing one.

**The schema is created once per process**, not once per test, and what gives a test a clean
database instead is a sweep: every row of every table deleted in one transaction, then the
two seeded `App` rows written again. Why it is not a rollback, and what it was measured
against, is [ADR 0031](../docs/adr/0031-one-lint-check-and-a-schema-once-per-worker.md).

Seven tables here are append-only, guarded by a SQLite trigger that aborts any `DELETE` on
them, and cases hold that guard by asserting it raises. Dropping the whole schema stepped
over them; a sweep cannot, so it takes the guards off and puts them back inside its own
transaction, reading their definitions from `sqlite_master` rather than from a list here
that would go stale the first time an eighth table joins them.

`app.db.models` is imported here on purpose. `Base.metadata` is populated by importing the
models, and a schema created once, at the start of a process, must not depend on which of
them the collected modules happened to reach for.
"""

import asyncio
import os
from collections.abc import AsyncGenerator

import pytest
from sqlalchemy import delete, event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from tests.database_naming import database_environment_for_this_process, the_generated_database_file

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-for-pytest-only")
os.environ.update(database_environment_for_this_process())
# The inngest client picks its mode when it is constructed, so this has to be set
# before anything imports it — otherwise importing app.main needs a signing key.
os.environ.setdefault("INNGEST_DEV", "1")

import app.db.models  # noqa: F401
from app.core.database import Base

#: The one the app is already pointed at, so the fixtures and the routes share a database.
TEST_DATABASE_URL = os.environ["DATABASE_URL"]


@pytest.fixture(scope="session")
def event_loop() -> AsyncGenerator[asyncio.AbstractEventLoop, None]:
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def test_engine():
    engine = create_async_engine(TEST_DATABASE_URL)

    @event.listens_for(engine.sync_engine, "connect")
    def _enable_sqlite_fk(dbapi_conn, _):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as conn:
        await conn.exec_driver_sql("PRAGMA foreign_keys=OFF")
        await conn.run_sync(Base.metadata.drop_all)
        await conn.exec_driver_sql("PRAGMA foreign_keys=ON")
        await conn.run_sync(Base.metadata.create_all)

    yield engine
    await engine.dispose()
    generated = the_generated_database_file()
    if generated is not None:
        generated.unlink(missing_ok=True)


@pytest.fixture()
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    # Foreign keys are off for the sweep and on for everything else. `rr_requests` and
    # `rr_snapshots` reference each other (a request names the snapshot it revises, a
    # snapshot names its request), so there is no order in which both tables can be emptied
    # with the constraint enforced once a row actually uses the link. SQLite cannot ALTER a
    # constraint into place, so `use_alter=True` — which is what makes this work on
    # PostgreSQL — writes the FK inline here instead.
    #
    # Latent until BE-04 (OBT-453), which is the first issue to write `revision_of_id`.
    # Enforcing referential integrity while emptying every table protects nothing.
    #
    # The PRAGMA takes effect because pysqlite opens the transaction at the first DML and
    # not before, so this statement runs outside it; the same reason is why turning them
    # back on at the end would not. Nothing needs to: aiosqlite on a file engine pools with
    # `NullPool`, so the next connection is a new one and the `connect` listener above puts
    # foreign keys back on for it. A pooled connection would carry this off, and the line
    # is here to name that.
    async with test_engine.begin() as conn:
        await conn.exec_driver_sql("PRAGMA foreign_keys=OFF")

        guards = [
            (name, sql)
            for name, sql in (
                await conn.exec_driver_sql(
                    "SELECT name, sql FROM sqlite_master WHERE type = 'trigger'"
                )
            ).all()
            if " DELETE ON " in sql
        ]
        for name, _ in guards:
            await conn.exec_driver_sql(f'DROP TRIGGER "{name}"')

        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(delete(table))

        for _, sql in guards:
            await conn.exec_driver_sql(sql)

    session_factory = async_sessionmaker(
        test_engine, expire_on_commit=False, class_=AsyncSession, autoflush=False
    )
    async with session_factory() as session:
        from app.db.models.auth import App

        mm_app = App(
            app_key="meaning-map-generator",
            name="Meaning Map Generator",
            is_active=True,
        )
        th_app = App(
            app_key="translation-helper",
            name="Translation Helper",
            is_active=True,
        )
        session.add(mm_app)
        session.add(th_app)
        await session.commit()

        yield session
        await session.rollback()
