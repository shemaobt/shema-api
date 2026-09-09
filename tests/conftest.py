import asyncio
import os
from collections.abc import AsyncGenerator

import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-for-pytest-only")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test.db")
# The inngest client picks its mode when it is constructed, so this has to be set
# before anything imports it — otherwise importing app.main needs a signing key.
os.environ.setdefault("INNGEST_DEV", "1")

from app.core.database import Base

TEST_DATABASE_URL = "sqlite+aiosqlite:///./test.db"


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


@pytest.fixture()
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    async with test_engine.begin() as conn:
        # Foreign keys are off for the drop and on for everything else. `rr_requests` and
        # `rr_snapshots` reference each other (a request names the snapshot it revises, a
        # snapshot names its request), so there is no order in which both tables can be
        # dropped with the constraint enforced once a row actually uses the link. SQLite
        # cannot ALTER a constraint into place, so `use_alter=True` — which is what makes
        # this work on PostgreSQL — writes the FK inline here instead.
        #
        # Latent until BE-04 (OBT-453), which is the first issue to write `revision_of_id`.
        # Enforcing referential integrity while demolishing the schema protects nothing.
        await conn.exec_driver_sql("PRAGMA foreign_keys=OFF")
        await conn.run_sync(Base.metadata.drop_all)
        await conn.exec_driver_sql("PRAGMA foreign_keys=ON")
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
