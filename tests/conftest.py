"""What every test in this suite is given before it asks for anything.

**The database is one file per process**, named by `database_naming` before anything of the
app is imported, and kept outside the working directory. A fixed name in the worktree meant
two runs in one checkout shared a database; one name for the whole of an xdist run would mean
four workers sharing one. Each process names its own, and a `DATABASE_URL` the caller set is
left alone for anybody reproducing a failure against a file they want to keep.

**The schema is created once per process**, not once per test: 138 DDL statements over 69
tables cost 0.20 s measured, which under 3259 tests was the floor of the whole suite. What
gives a test a clean database instead is a sweep — every row of every table deleted in one
transaction, in reverse dependency order, then the two seeded `App` rows written again — at
0.014 s measured. A rollback could not do it: 24 sites in `app/` open their own session and
commit on another connection, and several cases read the result back through a second engine.

`app.db.models` is imported here on purpose. `Base.metadata` is populated by importing the
models, and a schema created once, at the start of a process, must not depend on which of
them the collected modules happened to reach for.
"""

import asyncio
import os
from collections.abc import AsyncGenerator

import pytest
from database_naming import the_database_of_this_process, the_database_this_process_generated
from sqlalchemy import delete, event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-for-pytest-only")
os.environ.update(the_database_of_this_process())
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
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    yield engine
    await engine.dispose()
    generated = the_database_this_process_generated()
    if generated is not None:
        generated.unlink(missing_ok=True)


@pytest.fixture()
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    async with test_engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(delete(table))

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
