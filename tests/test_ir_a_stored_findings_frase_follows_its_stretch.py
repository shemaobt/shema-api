from __future__ import annotations

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.internalization_room.segments import final_segments
from tests.release_harness import PREFIX, TABLET
from tests.room_harness import (
    PART_MS,
    Room,
    ScriptedAnalyst,
    heard_every_part,
    press_terminei,
    rehearsed_in_parts,
    room_client,
    the_analyst_is_scripted,
    the_room_speaks,
)


@pytest.fixture()
def analyst(monkeypatch: pytest.MonkeyPatch) -> ScriptedAnalyst:
    return the_analyst_is_scripted(monkeypatch)


@pytest.fixture()
def room(monkeypatch: pytest.MonkeyPatch) -> Room:
    return the_room_speaks(monkeypatch)


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    async with room_client(db_session, monkeypatch) as door:
        yield door


async def _finish(client: httpx.AsyncClient, db: AsyncSession, session_id: str) -> httpx.Response:
    return await press_terminei(client, session_id, report=await heard_every_part(db, session_id))


async def _findings_of_the_read(client: httpx.AsyncClient, session_id: str) -> list[dict]:
    read = await client.get(f"{PREFIX}/sessions/{session_id}")
    assert read.status_code == 200, read.text
    return read.json()["back_translation"]["findings"]


async def test_a_divide_that_leaves_earlier_stretches_untold_moves_the_finding_down_with_its_frase(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    analyst: ScriptedAnalyst,
    room: Room,
) -> None:
    session, _parts = await rehearsed_in_parts(db_session, 3)
    told = await final_segments(db_session, session.id)
    analyst.readings = [{"findings": [{"kind": "addition", "note": "Rute foi junto", "chunk": 3}]}]
    await _finish(client, db_session, session.id)
    assert await _findings_of_the_read(client, session.id) == [
        {"kind": "addition", "frase": 3, "segment_id": told[2].id}
    ]

    divided = await client.post(
        f"{PREFIX}/sessions/{session.id}/segments/{told[0].id}/divide",
        headers={"X-Room-Device": TABLET},
        json={"at_ms": PART_MS // 2},
    )

    assert divided.status_code == 200, divided.text
    assert await _findings_of_the_read(client, session.id) == [
        {"kind": "addition", "frase": 2, "segment_id": told[2].id}
    ], "o achado seguia dizendo a frase 3 depois que o corte deixou a terceira como a segunda"
