"""ENG-969 — what a test is given by the database, now that the schema outlives the test.

The schema used to be dropped and created again before every test. It is now created once
per worker process, and each test is given a clean database by a sweep instead
([ADR 0031](../docs/adr/0031-one-lint-check-and-a-schema-once-per-worker.md)).

That trades one guarantee for another, so the guarantees are held here from outside the
fixture: what a test sees at its start, that a row committed on the production path does not
reach the next test, that a process running this module alone still has every table, and
that each worker owns its own file.

No model is imported at the top of this file, and that is the point of the third case: what
the schema has must come from the conftest importing `app.db.models`, never from what this
module happened to reach for. A module-level `from app.db.models.auth import App` runs the
package's `__init__` and registers all 71 tables, which would make that case unable to fail.
"""

import os

import pytest
from sqlalchemy import text

from app.core.database import AsyncSessionLocal, Base
from tests.database_naming import the_generated_database_file

SEEDED_KEYS = ["meaning-map-generator", "translation-helper"]

#: `Base.metadata` is populated by importing the models, not by collecting the suite.
TABLES_IN_THE_SCHEMA = 79

A_THIRD_APP = "a-third-app-committed-outside-the-test-session"
A_FOURTH_APP = "a-fourth-app-committed-before-the-sweep"


async def _app_keys(session) -> list[str]:
    rows = await session.execute(text("SELECT app_key FROM apps"))
    return sorted(rows.scalars().all())


async def test_a_test_starts_with_the_two_seeded_apps_and_nothing_else(db_session) -> None:
    assert await _app_keys(db_session) == SEEDED_KEYS


@pytest.fixture()
async def a_row_committed_before_the_sweep(test_engine) -> None:
    from app.db.models.auth import App

    async with AsyncSessionLocal() as session:
        session.add(App(app_key=A_FOURTH_APP, name="A fourth app", is_active=True))
        await session.commit()


async def test_the_production_path_commits_on_its_own_connection(db_session) -> None:
    """One of the sites in `app/` that open their own session and commit."""
    from app.db.models.auth import App

    async with AsyncSessionLocal() as session:
        session.add(App(app_key=A_THIRD_APP, name="A third app", is_active=True))
        await session.commit()

    assert A_THIRD_APP in await _app_keys(db_session)


async def test_the_sweep_takes_back_what_the_production_path_committed(
    a_row_committed_before_the_sweep, db_session
) -> None:
    assert await _app_keys(db_session) == SEEDED_KEYS


async def test_a_module_running_alone_still_has_every_table(db_session) -> None:
    """No case here writes an `ir_session`; the table answering empty is the schema's proof."""
    assert len(Base.metadata.sorted_tables) == TABLES_IN_THE_SCHEMA, (
        "a migration added or dropped a table: count them again and change the number"
    )

    rows = await db_session.execute(text("SELECT COUNT(*) FROM ir_sessions"))

    assert rows.scalar_one() == 0


def test_the_database_file_is_named_by_the_process_that_owns_it() -> None:
    """The controller names one too and the workers inherit it; each worker names its own.

    A caller who named the database is the one run where the name is not this suite's to
    choose, and `AGENTS.md` promises that name is honoured.
    """
    if the_generated_database_file() is None:
        pytest.skip("the caller named this database, so the name is theirs and not ours")

    worker = os.environ.get("PYTEST_XDIST_WORKER")
    url = os.environ["DATABASE_URL"]

    if worker is not None:
        assert worker in url
    assert str(os.getpid()) in url
