"""A session stored with today's bead ids reads them under hers once the migration lands.

Same constraint as the sibling migration tests: the schema is built from ``Base.metadata``,
stamped at the parent revision, filled with rows written under the ids the room wrote until
now, and walked up — then back down.
"""

import json
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

import app.db.models  # noqa: F401  (populates Base.metadata with every table)
from app.core.database import Base
from tests.alembic_harness import run_alembic

pytestmark = pytest.mark.migration

REVISION = "20261012_spine02"
PREVIOUS_REVISION = "20261011_cons01"
WHEN = "2026-10-12 09:00:00"

#: A P01 session as the room stored it before her ids: every axis, scene and silence under
#: our spelling, an entity bead whose id is already hers, a road her spine never had, and a
#: key no spine ever served.
STORED_TODAY = {
    "arc": "surfaced",
    "context": "not_encountered",
    "tone": "engaged",
    "function": "not_encountered",
    "scene:1": "engaged",
    "scene:2": "surfaced",
    "absence:1": "engaged",
    "absence:2": "not_encountered",
    "being:S1:B2": "engaged",
    "place:S2:the-road": "engaged",
    "preserved:R3": "surfaced",
    "being:B999": "surfaced",
}

UNDER_HER_IDS = {
    "L1:arc": "surfaced",
    "L1:context": "not_encountered",
    "L1:tone": "engaged",
    "L1:function": "not_encountered",
    "scene:S1": "engaged",
    "scene:S2": "surfaced",
    "absence:S1": "engaged",
    "absence:S2": "not_encountered",
    "being:S1:B2": "engaged",
    "place:S2:the-road": "engaged",
    "preserved:R3": "surfaced",
    "being:B999": "surfaced",
}

EVENTS_TODAY = {
    ("arc", "surfaced"),
    ("scene:1", "engaged"),
    ("absence:1", "engaged"),
    ("being:S1:B2", "engaged"),
}
EVENTS_UNDER_HER_IDS = {
    ("L1:arc", "surfaced"),
    ("scene:S1", "engaged"),
    ("absence:S1", "engaged"),
    ("being:S1:B2", "engaged"),
}


async def _execute(url: str, sql: str, params: dict | None = None) -> None:
    engine = create_async_engine(url)
    async with engine.begin() as conn:
        await conn.execute(text(sql), params or {})
    await engine.dispose()


async def _session(url: str, coverage: str) -> str:
    session_id = str(uuid.uuid4())
    await _execute(
        url,
        "INSERT INTO ir_sessions (id, pericope, status, messages, after_panorama,"
        " coverage_state, back_translation, created_at, updated_at)"
        " VALUES (:id, 'P01', 'in_progress', '[]', 0, :coverage, '{}', :now, :now)",
        {"id": session_id, "coverage": coverage, "now": WHEN},
    )
    return session_id


async def _coverage(url: str, session_id: str) -> dict | None:
    engine = create_async_engine(url)
    async with engine.connect() as conn:
        stored = (
            await conn.execute(
                text("SELECT coverage_state FROM ir_sessions WHERE id = :id"), {"id": session_id}
            )
        ).scalar_one()
    await engine.dispose()
    return json.loads(stored)


async def _events(url: str) -> set[tuple[str, str]]:
    engine = create_async_engine(url)
    async with engine.connect() as conn:
        rows = (
            await conn.execute(text("SELECT element_key, status FROM ir_coverage_events"))
        ).all()
    await engine.dispose()
    return {(key, status) for key, status in rows}


async def _anchors(url: str) -> list[str | None]:
    engine = create_async_engine(url)
    async with engine.connect() as conn:
        rows = (
            await conn.execute(text("SELECT element_key FROM ir_questions ORDER BY audio_key"))
        ).all()
    await engine.dispose()
    return [key for (key,) in rows]


@pytest.fixture()
async def stored_today(tmp_path) -> dict[str, str]:
    url = f"sqlite+aiosqlite:///{tmp_path / 'her_ids.db'}"
    engine = create_async_engine(url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
    stamped = run_alembic(url, "stamp", PREVIOUS_REVISION)
    assert stamped.returncode == 0, stamped.stderr

    worked = await _session(url, json.dumps(STORED_TODAY))
    for key, status in EVENTS_TODAY:
        await _execute(
            url,
            "INSERT INTO ir_coverage_events (id, session_id, pericope, element_key, status, at)"
            " VALUES (:id, :session, 'P01', :key, :status, :now)",
            {"id": str(uuid.uuid4()), "session": worked, "key": key, "status": status, "now": WHEN},
        )
    for audio, anchor in (("a", "scene:2"), ("b", "absence:1"), ("c", "being:S1:B2"), ("d", None)):
        await _execute(
            url,
            "INSERT INTO ir_questions (id, device_id, session_id, pericope, audio_key,"
            " element_key, status, created_at) VALUES (:id, 'tablet', :session, 'P01', :audio,"
            " :anchor, 'open', :now)",
            {
                "id": str(uuid.uuid4()),
                "session": worked,
                "audio": audio,
                "anchor": anchor,
                "now": WHEN,
            },
        )
    return {
        "url": url,
        "worked": worked,
        "never_seeded": await _session(url, "null"),
        "empty": await _session(url, "{}"),
    }


async def test_a_session_stored_with_todays_ids_keeps_every_status_under_her_ids(stored_today):
    url = stored_today["url"]

    up = run_alembic(url, "upgrade", REVISION)

    assert up.returncode == 0, up.stderr
    assert await _coverage(url, stored_today["worked"]) == UNDER_HER_IDS, (
        "a sessão guardada com as chaves de antes abria com os eixos, as cenas e os silêncios "
        "por começar, e o trabalho da equipe sumia do colar"
    )
    assert await _events(url) == EVENTS_UNDER_HER_IDS, (
        "a história da Mesa lia os eventos pelas chaves novas e não achava os de antes"
    )
    assert await _anchors(url) == ["scene:S2", "absence:S1", "being:S1:B2", None]
    assert await _coverage(url, stored_today["never_seeded"]) is None
    assert await _coverage(url, stored_today["empty"]) == {}


async def test_a_second_run_moves_nothing_and_never_lowers_a_bead(stored_today):
    url = stored_today["url"]
    assert run_alembic(url, "upgrade", REVISION).returncode == 0
    written_by_the_old_code_after = {**UNDER_HER_IDS, "arc": "not_encountered"}
    await _execute(
        url,
        "UPDATE ir_sessions SET coverage_state = :coverage WHERE id = :id",
        {"coverage": json.dumps(written_by_the_old_code_after), "id": stored_today["worked"]},
    )
    assert run_alembic(url, "stamp", PREVIOUS_REVISION).returncode == 0

    again = run_alembic(url, "upgrade", REVISION)

    assert again.returncode == 0, again.stderr
    assert await _coverage(url, stored_today["worked"]) == UNDER_HER_IDS, (
        "a chave antiga que o código velho ainda escreveu por começar apagava o eixo já "
        "levantado sob a chave nova"
    )
    assert await _events(url) == EVENTS_UNDER_HER_IDS
    assert await _anchors(url) == ["scene:S2", "absence:S1", "being:S1:B2", None]


async def test_walking_down_gives_back_exactly_the_ids_it_renamed(stored_today):
    url = stored_today["url"]
    assert run_alembic(url, "upgrade", REVISION).returncode == 0

    down = run_alembic(url, "downgrade", PREVIOUS_REVISION)

    assert down.returncode == 0, down.stderr
    assert await _coverage(url, stored_today["worked"]) == STORED_TODAY
    assert await _events(url) == EVENTS_TODAY
    assert await _anchors(url) == ["scene:2", "absence:1", "being:S1:B2", None]
