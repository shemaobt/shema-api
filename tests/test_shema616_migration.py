"""OBT-616 — the list arrives with Karina's nineteen countries, and no stored project moves.

Same constraint as the other migration tests: Alembic's full chain does not run on SQLite, so this
exercises the one revision under test. The schema is built from ``Base.metadata`` — the
post-migration shape — then the new table is dropped and the database stamped at the parent,
filled with two projects, and walked up and back down.

What is worth proving is not that a table appeared. It is the DoD's line *os projetos existentes
não mudam*: a project stored in a listed country with its flag down keeps it down through the
upgrade and the downgrade — the rule runs on writes, never over rows already written — and a flag
raised by hand stays raised. And that the list it starts from is the one Karina approved, each
country with the English name a team may type.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

import app.db.models  # noqa: F401  (populates Base.metadata with every table)
from app.core.database import Base
from app.db.models.shema import ShemaProject
from app.db.models.shema_enums import ShemaRegionKey

pytestmark = pytest.mark.migration

REPO_ROOT = Path(__file__).resolve().parent.parent

REVISION = "20261027_shema616"
PREVIOUS_REVISION = "20261009_shema575"

#: Karina's table of 19/out/2026, in her words: the four she named, the Middle East, and the three
#: she approved as debatable.
KARINAS_NAMES = {
    "Índia",
    "China",
    "Irã",
    "Iraque",
    "Arábia Saudita",
    "Bahrein",
    "Catar",
    "Emirados Árabes Unidos",
    "Iêmen",
    "Israel",
    "Jordânia",
    "Kuwait",
    "Líbano",
    "Omã",
    "Palestina",
    "Síria",
    "Egito",
    "Turquia",
    "Chipre",
}

#: The English name of every country whose English spelling differs from hers.
ENGLISH = {
    "Índia": "India",
    "Irã": "Iran",
    "Iraque": "Iraq",
    "Arábia Saudita": "Saudi Arabia",
    "Bahrein": "Bahrain",
    "Catar": "Qatar",
    "Emirados Árabes Unidos": "United Arab Emirates",
    "Iêmen": "Yemen",
    "Jordânia": "Jordan",
    "Líbano": "Lebanon",
    "Omã": "Oman",
    "Palestina": "Palestine",
    "Síria": "Syria",
    "Egito": "Egypt",
    "Turquia": "Turkey",
    "Chipre": "Cyprus",
}

STORED_IN_IRAN = "6a1f3c2e-7b4d-4e5f-9a8b-0c1d2e3f4a5b"
MARKED_BY_HAND = "7b2e4d3f-8c5e-4f6a-0b9c-1d2e3f4a5b6c"


def _run_alembic(database_url: str, *argv: str) -> subprocess.CompletedProcess:
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


async def _build_and_seed(database_url: str) -> None:
    engine = create_async_engine(database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text("DROP TABLE shema_sensitive_countries"))
    async with AsyncSession(engine) as session:
        session.add_all(
            [
                ShemaProject(
                    id=STORED_IN_IRAN,
                    language_name="Língua Gravada",
                    location="Teerã, Irã",
                    region_key=ShemaRegionKey.OTHER,
                    sensitive_country=False,
                ),
                ShemaProject(
                    id=MARKED_BY_HAND,
                    language_name="Língua do Norte",
                    location="Roraima, Brasil",
                    region_key=ShemaRegionKey.SOUTH_AMERICA,
                    sensitive_country=True,
                ),
            ]
        )
        await session.commit()
    await engine.dispose()


async def _rows(database_url: str, sql: str) -> list[tuple]:
    engine = create_async_engine(database_url)
    async with engine.connect() as conn:
        rows = [tuple(row) for row in (await conn.execute(text(sql))).all()]
    await engine.dispose()
    return rows


async def _flags(database_url: str) -> dict[str, tuple]:
    rows = await _rows(
        database_url, "SELECT id, sensitive_country, location, version FROM shema_projects"
    )
    return {row[0]: tuple(row[1:]) for row in rows}


@pytest.fixture()
async def database(tmp_path) -> str:
    url = f"sqlite+aiosqlite:///{tmp_path / 'shema616.db'}"
    await _build_and_seed(url)
    stamped = _run_alembic(url, "stamp", PREVIOUS_REVISION)
    assert stamped.returncode == 0, stamped.stderr
    return url


async def test_the_upgrade_seeds_karinas_nineteen_with_their_english_names(database) -> None:
    up = _run_alembic(database, "upgrade", REVISION)
    assert up.returncode == 0, up.stderr

    rows = await _rows(database, "SELECT name, spellings FROM shema_sensitive_countries")
    listed = {name: json.loads(spellings) for name, spellings in rows}
    assert set(listed) == KARINAS_NAMES
    for name, english in ENGLISH.items():
        assert english in listed[name], name


async def test_the_upgrade_and_the_downgrade_leave_every_stored_project_as_it_was(
    database,
) -> None:
    """*A regra não roda sobre linhas já gravadas*: Iran is on the list from this revision on, and
    the project stored there is not flagged by it; the one a coordinator marked stays marked."""
    before = await _flags(database)

    assert _run_alembic(database, "upgrade", REVISION).returncode == 0
    after_upgrade = await _flags(database)
    down = _run_alembic(database, "downgrade", PREVIOUS_REVISION)
    assert down.returncode == 0, down.stderr
    after_downgrade = await _flags(database)

    assert before[STORED_IN_IRAN][0] in (0, False)
    assert before[MARKED_BY_HAND][0] in (1, True)
    assert after_upgrade == before
    assert after_downgrade == before
    tables = await _rows(
        database,
        "SELECT name FROM sqlite_master WHERE type = 'table'"
        " AND name = 'shema_sensitive_countries'",
    )
    assert tables == []
