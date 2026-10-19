"""ENG-1378 (b) — a red-microphone rehearsal is never a kept take (ENG-1379's Expected).

Her route keeps a turn's audio only when the turn came in as audio; a rehearsal arrives as
its frases' words (her api/turn/route.ts:404), so its verdict is read and nothing is kept.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.internalization_room import background
from app.services.internalization_room.sessions import get_session
from tests.hard_stretch_harness import a_session
from tests.room_harness import the_bucket_is_in_memory, the_room_speaks
from tests.scene_rehearsal_harness import IR, a_room, recorded, translated
from tests.turn_harness import the_room_agent_is


@pytest.fixture()
async def room(db_session, rival_factory, monkeypatch):
    async with a_room(db_session, rival_factory, monkeypatch) as built:
        yield built


@pytest.fixture()
def kept(monkeypatch: pytest.MonkeyPatch, rival_factory):
    async def guide(*, system_prompt: str, **_: Any) -> str:
        if "corrected_response" in system_prompt:
            return json.dumps({"verdict": "pass", "issues": []})
        return "Isso. Vocês contaram a cena inteira."

    async def reader(**_: Any) -> str:
        return json.dumps({"decisions": [], "retelling": {"scope": "S2", "approved": True}})

    @asynccontextmanager
    async def fresh() -> AsyncIterator[AsyncSession]:
        async with rival_factory() as session:
            yield session

    the_room_speaks(monkeypatch)
    the_room_agent_is(monkeypatch, turn=guide, classifier=reader)
    monkeypatch.setattr(background, "AsyncSessionLocal", fresh)
    return the_bucket_is_in_memory(monkeypatch)


async def test_a_rehearsal_the_voice_approved_keeps_its_verdict_and_no_take(
    room, kept, db_session, rival_factory
) -> None:
    session_id = await a_session(db_session, pericope="P01")
    opened = await room.client.post(f"{IR}/sessions/{session_id}/turns")
    assert opened.status_code == 200, opened.text
    rehearsal_id = await recorded(room, session_id)
    await translated(room, session_id, rehearsal_id, [(0, 20000)])

    sent = await room.client.post(
        f"{IR}/sessions/{session_id}/scene-rehearsals/{rehearsal_id}/send",
        data={"turn_id": "turno-da-cena"},
    )
    assert sent.status_code == 200, sent.text

    async with rival_factory() as fresh:
        retellings = (await get_session(fresh, session_id)).retellings
    assert retellings == {"1": {"scope": "S2", "approved": True}}, (
        "o ensaio do microfone vermelho virava uma tomada guardada, ou perdia o veredito"
    )
    assert kept.objects == {}
    read = await room.client.get(f"{IR}/sessions/{session_id}")
    assert read.json()["kept_takes"] == []
