from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.auth import App
from app.db.models.project import Project
from tests.baker import make_app, make_role
from tests.device_harness import TABLET_TEAM
from tests.hard_stretch_harness import MemoryStore
from tests.release_harness import APP_KEY, PREFIX, at_the_desk
from tests.room_harness import room_client, the_bucket_is_in_memory
from tests.sentence_harness import re_record, rehearsed_in_wav, spoken

SCENE_TWO = [[(0, 1000)], [(0, 42000), (42000, 49000), (49000, 50000)]]


@pytest.fixture()
def store(monkeypatch: pytest.MonkeyPatch) -> MemoryStore:
    return the_bucket_is_in_memory(monkeypatch)


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, store: MemoryStore):
    async with room_client(db_session, monkeypatch) as door:
        yield door


@pytest.fixture()
async def room_app(db_session: AsyncSession) -> App:
    app = await make_app(db_session, app_key=APP_KEY, name="Internalization Room")
    await make_role(db_session, app.id, role_key="facilitator", label="Facilitator", is_system=True)
    return app


def desk_re_recorded(session_id: str) -> str:
    return f"{PREFIX}/facilitator/sessions/{session_id}/re-recorded-sentences"


async def _the_desk(db: AsyncSession, room_app: App) -> dict[str, str]:
    team = await db.get(Project, TABLET_TEAM)
    assert team is not None
    desk, _facilitator = await at_the_desk(db, room_app, team)
    return desk


async def _the_sentences(
    client: httpx.AsyncClient, session_id: str, desk: dict[str, str]
) -> list[dict[str, Any]]:
    answered = await client.get(desk_re_recorded(session_id), headers=desk)
    assert answered.status_code == 200, answered.text
    return answered.json()["sentences"]


async def test_a_sentence_of_scene_two_recorded_again_reads_with_where_it_was_and_where_it_went(
    client: httpx.AsyncClient, db_session: AsyncSession, store: MemoryStore, room_app: App
) -> None:
    session, (_, part_two), (_, (_, middle, _)) = await rehearsed_in_wav(
        db_session, store, SCENE_TWO
    )
    desk = await _the_desk(db_session, room_app)

    before = datetime.now(UTC)
    laid = await re_record(client, session.id, middle.id, spoken(8.6))
    after = datetime.now(UTC)
    assert laid.status_code == 200, laid.text

    (sentence,) = await _the_sentences(client, session.id, desk)
    assert {
        key: sentence[key]
        for key in (
            "sentence_id",
            "segment_id",
            "scene",
            "starts_ms",
            "replaced_ends_ms",
            "ends_ms",
            "previous_take_id",
        )
    } == {
        "sentence_id": "sentence-0001",
        "segment_id": middle.id,
        "scene": "S2",
        "starts_ms": 42000,
        "replaced_ends_ms": 49000,
        "ends_ms": 51000,
        "previous_take_id": part_two.id,
    }, "a frase regravada não chegava ao registro com o trecho de antes e o de depois"
    assert before <= datetime.fromisoformat(sentence["at"]) <= after, (
        "o registro não dizia quando a frase foi regravada"
    )
