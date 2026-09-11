"""What every test in this suite is given before it asks for anything.

**The database is one file per run**, named by the process and kept outside the working
directory. A fixed name in the worktree meant two runs in one checkout shared a database:
every test drops every table and creates them again, so one run took the other's tables out
from under it, and the failures landed anywhere and looked like the code under test.
``setdefault`` leaves a caller's own name alone, for anybody reproducing a failure against a
file they want to keep; that run then owns its file, and this one removes only the file it
made for itself.

It is named before anything of the app is imported, because the app builds its engine on
import and a fixture would run long after that. The name is therefore written twice — once in
the ``setdefault`` below and once for the cleanup — and cannot be written once: the lint
refuses a module-level assignment before that import (E402), and a helper module is not
importable this early because ``tests`` is not a package. Change one and change the other.
"""

import asyncio
import os
import tempfile
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-for-pytest-only")
os.environ.setdefault(
    "DATABASE_URL",
    f"sqlite+aiosqlite:///{Path(tempfile.gettempdir()) / f'shema-api-test-{os.getpid()}.db'}",
)
# The inngest client picks its mode when it is constructed, so this has to be set
# before anything imports it — otherwise importing app.main needs a signing key.
os.environ.setdefault("INNGEST_DEV", "1")

from app.core.database import Base

#: The one the app is already pointed at, so the fixtures and the routes share a database.
TEST_DATABASE_URL = os.environ["DATABASE_URL"]

_PER_RUN_DATABASE = Path(tempfile.gettempdir()) / f"shema-api-test-{os.getpid()}.db"


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

    yield engine
    await engine.dispose()
    _PER_RUN_DATABASE.unlink(missing_ok=True)


@pytest.fixture()
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

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
