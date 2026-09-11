import asyncio
import os
import tempfile
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-for-pytest-only")

# One file per run, named by the process, and outside the working directory. A fixed name in
# the worktree meant two runs in one checkout shared a database: every test drops every table
# and creates them again, so one run took the other's tables out from under it and the failures
# landed anywhere and looked like the code. `setdefault` leaves a caller's own name alone, for
# anybody reproducing a failure against a file they want to keep.
# It is set here, at import, because the app builds its engine when a test module first imports
# it; a fixture would run after that.
os.environ.setdefault(
    "DATABASE_URL",
    f"sqlite+aiosqlite:///{Path(tempfile.gettempdir()) / f'shema-api-test-{os.getpid()}.db'}",
)
# The inngest client picks its mode when it is constructed, so this has to be set
# before anything imports it — otherwise importing app.main needs a signing key.
os.environ.setdefault("INNGEST_DEV", "1")

from app.core.database import Base

# The one the app is already pointed at, so the fixtures and the routes share a database.
TEST_DATABASE_URL = os.environ["DATABASE_URL"]

# The file this run would have made for itself. When the caller named a database instead, this
# one was never created and removing it is a no-op — which is the whole of the rule: a run
# cleans up after itself and leaves alone the file somebody asked for. The name is written here
# and in the `setdefault` above, and nowhere else: change one and change the other.
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
