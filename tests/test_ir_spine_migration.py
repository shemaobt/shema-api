"""The recorded events follow the spine: one bead per entity in each scene, one per silence.

Same constraint as the sibling migration tests: Alembic's full chain does not run on SQLite,
so this exercises the one migration under test. The schema is built from ``Base.metadata``,
stamped at the parent revision, filled with events under the keys the old spine wrote, and
walked up — then back down.
"""

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

import app.db.models  # noqa: F401  (populates Base.metadata with every table)
from app.core.database import Base
from tests.alembic_harness import run_alembic

pytestmark = pytest.mark.migration

REVISION = "20260916_spine01"
PREVIOUS_REVISION = "20260916_ver01"

TABLE = "ir_coverage_events"
WHEN = "2026-09-16 09:00:00"

#: What the old spine recorded for one team on Ruth 1:1-5, and one row on another passage.
RECORDED = [
    ("P01", "being:B3", "engaged"),
    ("P01", "place:PL2", "surfaced"),
    ("P01", "preserved:R6", "engaged"),
    ("P01", "preserved:R10", "surfaced"),
    ("P01", "scene:2", "engaged"),
    ("P01", "being:B999", "surfaced"),
    ("P03", "being:B3", "surfaced"),
]


async def _build_and_seed(database_url: str) -> str:
    engine = create_async_engine(database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_id = str(uuid.uuid4())
    project_id = str(uuid.uuid4())
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO ir_sessions (id, pericope, status, messages, after_panorama,"
                " coverage_state, kept_takes, back_translation, project_id, created_at,"
                " updated_at) VALUES (:id, 'P01', 'done', '[]', 0, '{}', '{}', '{}',"
                " :project_id, :now, :now)"
            ),
            {"id": session_id, "project_id": project_id, "now": WHEN},
        )
        for pericope, element_key, status in RECORDED:
            await conn.execute(
                text(
                    f"INSERT INTO {TABLE} (id, session_id, project_id, pericope, element_key,"
                    " status, at) VALUES (:id, :session, :project_id, :pericope, :key,"
                    " :status, :now)"
                ),
                {
                    "id": str(uuid.uuid4()),
                    "session": session_id,
                    "project_id": project_id,
                    "pericope": pericope,
                    "key": element_key,
                    "status": status,
                    "now": WHEN,
                },
            )
    await engine.dispose()
    return session_id


async def _events(database_url: str) -> set[tuple[str, str, str]]:
    engine = create_async_engine(database_url)
    async with engine.connect() as conn:
        rows = (
            await conn.execute(text(f"SELECT pericope, element_key, status FROM {TABLE}"))
        ).all()
    await engine.dispose()
    return {tuple(row) for row in rows}


@pytest.fixture()
async def recorded_under_the_old_keys(tmp_path) -> str:
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'spine.db'}"
    await _build_and_seed(database_url)

    stamped = run_alembic(database_url, "stamp", PREVIOUS_REVISION)
    assert stamped.returncode == 0, stamped.stderr
    return database_url


async def test_an_entity_event_moves_to_the_scene_the_old_bead_stood_in(
    recorded_under_the_old_keys,
) -> None:
    url = recorded_under_the_old_keys

    up = run_alembic(url, "upgrade", REVISION)
    assert up.returncode == 0, up.stderr

    events = await _events(url)
    assert ("P01", "being:S1:B3", "engaged") in events, (
        "a conta antiga de Naomi dizia cena 1, e o evento gravado nela ficava sob uma chave "
        "que ninguém mais serve — necklace_with_touches lê estritamente por element_key"
    )
    assert ("P01", "place:S1:PL2", "surfaced") in events
    assert ("P03", "being:S1:B3", "surfaced") in events
    assert not any(key in {"being:B3", "place:PL2"} for _p, key, _s in events)


async def test_a_folded_rules_events_land_on_the_absences_it_folds_into(
    recorded_under_the_old_keys,
) -> None:
    url = recorded_under_the_old_keys

    assert run_alembic(url, "upgrade", REVISION).returncode == 0

    events = await _events(url)
    assert {
        ("P01", "absence:1", "engaged"),
        ("P01", "absence:2", "engaged"),
        ("P01", "absence:4", "engaged"),
    } <= events
    assert ("P01", "absence:3", "engaged") not in events
    assert not any(key == "preserved:R6" for _p, key, _s in events)


async def test_what_the_new_spine_still_serves_or_never_did_is_left_alone(
    recorded_under_the_old_keys,
) -> None:
    url = recorded_under_the_old_keys

    assert run_alembic(url, "upgrade", REVISION).returncode == 0

    events = await _events(url)
    assert ("P01", "preserved:R10", "surfaced") in events
    assert ("P01", "scene:2", "engaged") in events
    assert ("P01", "being:B999", "surfaced") in events


async def test_the_way_down_puts_the_entity_keys_back(recorded_under_the_old_keys) -> None:
    url = recorded_under_the_old_keys
    assert run_alembic(url, "upgrade", REVISION).returncode == 0

    down = run_alembic(url, "downgrade", PREVIOUS_REVISION)
    assert down.returncode == 0, down.stderr

    events = await _events(url)
    assert ("P01", "being:B3", "engaged") in events
    assert ("P01", "place:PL2", "surfaced") in events
    assert ("P03", "being:B3", "surfaced") in events
    assert not any(
        key.split(":")[1].startswith("S") for _p, key, _s in events if key.count(":") == 2
    )
    assert ("P01", "absence:1", "engaged") in events
