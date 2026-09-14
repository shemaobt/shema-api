"""Walking a migration against a throwaway database, for the tests that check one.

Every migration test asks the same four questions of a database file it built itself: run
Alembic over it, then which tables, which columns, which indexes and what one cell holds.
The helpers that answer them were copied into each test module — ten identical copies of the
subprocess call alone — so the environment a migration needs to run under was written down
ten times and could drift in any of them.

Alembic is run as a subprocess and not through its Python API because ``alembic/env.py``
resolves ``DATABASE_URL`` when it is imported: pulling it into the test process would bind
the migration to the suite's own database instead of the file under test.

Each helper opens its own engine and disposes of it. The database under test is a file the
caller made, never the session the suite runs on, and a connection left open on SQLite holds
a lock that the next ``run_alembic`` subprocess would wait on.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine

REPO_ROOT = Path(__file__).resolve().parent.parent


def run_alembic(database_url: str, *argv: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "alembic", *argv],
        cwd=REPO_ROOT,
        env={
            **os.environ,
            "DATABASE_URL": database_url,
            "JWT_SECRET_KEY": "test-secret-for-pytest-only",
            "INNGEST_DEV": "1",
        },
        capture_output=True,
        text=True,
    )


async def tables_of(database_url: str) -> set[str]:
    engine = create_async_engine(database_url)
    async with engine.connect() as conn:
        names = await conn.run_sync(lambda sync: inspect(sync).get_table_names())
    await engine.dispose()
    return set(names)


async def columns_of(database_url: str, table: str) -> set[str]:
    engine = create_async_engine(database_url)
    async with engine.connect() as conn:
        columns = await conn.run_sync(lambda sync: inspect(sync).get_columns(table))
    await engine.dispose()
    return {column["name"] for column in columns}


async def indexes_of(database_url: str, table: str) -> dict[str, tuple[bool, list[str]]]:
    """Every index on ``table`` by name, each with whether it is unique and over what.

    The richer of the two shapes the copies carried: a caller that only wants the names reads
    the keys, and one proving that an index is unique over given columns — which is the whole
    point of a migration that adds one — does not have to inspect the database a second time.
    """
    engine = create_async_engine(database_url)
    async with engine.connect() as conn:
        found = await conn.run_sync(lambda sync: inspect(sync).get_indexes(table))
    await engine.dispose()
    return {index["name"]: (bool(index["unique"]), list(index["column_names"])) for index in found}


async def scalar(database_url: str, sql: str, params: dict) -> object:
    engine = create_async_engine(database_url)
    async with engine.connect() as conn:
        value = (await conn.execute(text(sql), params)).scalar_one_or_none()
    await engine.dispose()
    return value
