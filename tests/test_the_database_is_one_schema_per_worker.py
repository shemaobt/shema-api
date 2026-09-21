"""ENG-969 — what a test is given by the database, now that the schema outlives the test.

The schema used to be dropped and created again before every test: 138 DDL statements over
69 tables, measured at 0.2 s, under every one of 2961 tests. It is now created once per
worker process, and each test is given a clean database by a sweep — every row of every
table deleted, then the two seeded `App` rows written again.

That trades one guarantee for another, so the guarantees are held here from outside the
fixture: what a test sees at its start, that a row committed on the production path does not
reach the next test, that a process running this module alone still has every table, and
that each worker owns its own file.

No model is imported at the top of this file, and that is the point of the third case: what
the schema has must come from the conftest importing `app.db.models`, never from what this
module happened to reach for. A module-level `from app.db.models.auth import App` runs the
package's `__init__` and registers all 69 tables, which would make that case unable to fail.
"""

import os

from sqlalchemy import text

from app.core.database import AsyncSessionLocal, Base

SEEDED_KEYS = ["meaning-map-generator", "translation-helper"]

#: `Base.metadata` is populated by importing the models, not by collecting the suite.
TABLES_IN_THE_SCHEMA = 69

A_THIRD_APP = "a-third-app-committed-outside-the-test-session"


async def _app_keys(session) -> list[str]:
    rows = await session.execute(text("SELECT app_key FROM apps"))
    return sorted(rows.scalars().all())


async def test_a_test_starts_with_the_two_seeded_apps_and_nothing_else(db_session) -> None:
    assert await _app_keys(db_session) == SEEDED_KEYS


async def test_the_production_path_commits_on_its_own_connection(db_session) -> None:
    """24 sites in `app/` open their own session and commit; this is one of them.

    First of the two on purpose: under `--dist loadfile` the module's cases run on one
    worker in file order, and the next one is what says the row did not survive.
    """
    from app.db.models.auth import App

    async with AsyncSessionLocal() as session:
        session.add(App(app_key=A_THIRD_APP, name="A third app", is_active=True))
        await session.commit()

    assert A_THIRD_APP in await _app_keys(db_session)


async def test_the_sweep_takes_back_what_the_production_path_committed(db_session) -> None:
    assert await _app_keys(db_session) == SEEDED_KEYS


async def test_a_module_running_alone_still_has_every_table(db_session) -> None:
    """No case here writes an `ir_session`; the table answering empty is the schema's proof."""
    assert len(Base.metadata.sorted_tables) == TABLES_IN_THE_SCHEMA

    rows = await db_session.execute(text("SELECT COUNT(*) FROM ir_sessions"))

    assert rows.scalar_one() == 0


def test_the_database_file_is_named_by_the_process_that_owns_it() -> None:
    """The controller names one too and the workers inherit it; each worker names its own."""
    worker = os.environ.get("PYTEST_XDIST_WORKER")
    url = os.environ["DATABASE_URL"]

    if worker is not None:
        assert worker in url
    assert str(os.getpid()) in url
