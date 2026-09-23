"""What every test in this suite is given before it asks for anything.

**The database is one file per process**, named by `tests.database_naming` before anything of
the app is imported, and kept outside the working directory. A fixed name in the worktree
meant two runs in one checkout shared a database; one name for the whole of an xdist run
would mean four workers sharing one.

**The schema is created once per process**, not once per test, and what gives a test a clean
database instead is a sweep: every row of every table deleted in one transaction, then the
two seeded `App` rows written again. Why it is not a rollback, and what it was measured
against, is [ADR 0031](../docs/adr/0031-one-lint-check-and-a-schema-once-per-worker.md).

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
from app.services.internalization_room import llm
from app.services.platform import tts

#: The one the app is already pointed at, so the fixtures and the routes share a database.
TEST_DATABASE_URL = os.environ["DATABASE_URL"]


@pytest.fixture(autouse=True)
def _nothing_kept_outlives_its_test():
    llm._CLIENTS.clear()
    tts.forget_what_is_kept()
    yield
    llm._CLIENTS.clear()
    tts.forget_what_is_kept()


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
    generated = the_generated_database_file()
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
