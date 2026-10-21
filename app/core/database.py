from collections.abc import AsyncGenerator
from typing import Final

from sqlalchemy import Connection, event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings
from app.core.db_url import async_database_url, ssl_connect_args

#: How long a statement of the app waits on a lock before Postgres refuses it: inside the 90 s
#: a turn waits on another turn of its session, and past a frase uploaded on a slow link while
#: it holds the session's row (ADR 0079).
LOCK_TIMEOUT: Final = "30s"
#: How long one statement of the app may run: above the longest the app means to run.
STATEMENT_TIMEOUT: Final = "1min"


class Base(DeclarativeBase):
    pass


settings = get_settings()
_raw_url = settings.database_url
engine = create_async_engine(
    async_database_url(_raw_url),
    pool_pre_ping=True,
    connect_args=ssl_connect_args(_raw_url),
)


def _bound_the_waits(connection: Connection) -> None:
    """Set both waits for this transaction alone, in one round trip.

    Per transaction and not when the connection starts: production reaches Neon through its
    pooler, which hands the server connection to another client between transactions and
    keeps nothing a connection was started with (ADR 0079).
    """
    connection.exec_driver_sql(
        f"SELECT set_config('lock_timeout', '{LOCK_TIMEOUT}', true), "
        f"set_config('statement_timeout', '{STATEMENT_TIMEOUT}', true)"
    )


if engine.dialect.name == "postgresql":
    event.listen(engine.sync_engine, "begin", _bound_the_waits)

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


async def init_db() -> None:
    return None


async def close_db() -> None:
    await engine.dispose()
