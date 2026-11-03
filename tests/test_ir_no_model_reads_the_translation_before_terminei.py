from __future__ import annotations

from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.internalization_room import back_translation as bt_api
from app.api.internalization_room import segments as segments_api
from app.db.models.internalization_room import IRTake
from app.services.internalization_room.segments import final_segments
from app.services.internalization_room.sessions import get_session
from tests.hard_stretch_harness import MemoryStore
from tests.release_harness import PREFIX, TABLET
from tests.room_harness import (
    Room,
    ScriptedAnalyst,
    played_every_part,
    press_terminei,
    rehearsed_in_parts_of,
    room_client,
    the_bucket_is_in_memory,
    the_room_speaks,
    the_transcriber_says,
)
from tests.turn_harness import the_room_agent_is

FIVE_FRASES = [
    "Noemi ficou sozinha.",
    "Ela ouviu que o Senhor deu pão.",
    "Ela partiu com as noras.",
    "Ela pediu que voltassem.",
    "Rute ficou com ela.",
]

AN_ADDITION_ON_FRASE_2 = {
    "findings": [{"kind": "addition", "note": "Boaz não está nesta cena.", "chunk": 2}]
}


class Analyst(ScriptedAnalyst):
    def __init__(self) -> None:
        super().__init__()
        self.whole_readings = 0

    async def __call__(self, *, system_prompt: str, user_content: str, **_: Any) -> str:
        self.whole_readings += 1
        return await super().__call__(system_prompt=system_prompt, user_content=user_content)


@pytest.fixture()
def analyst(monkeypatch: pytest.MonkeyPatch) -> Analyst:
    reader = Analyst()
    the_room_agent_is(monkeypatch, analyst=reader)
    return reader


@pytest.fixture()
def room(monkeypatch: pytest.MonkeyPatch) -> Room:
    return the_room_speaks(monkeypatch)


@pytest.fixture(autouse=True)
def bucket(monkeypatch: pytest.MonkeyPatch) -> MemoryStore:
    the_transcriber_says(monkeypatch, list(FIVE_FRASES))
    monkeypatch.setattr(segments_api, "heard", bt_api.heard)
    return the_bucket_is_in_memory(monkeypatch)


@pytest.fixture()
def per_request(test_engine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)


async def _tell_five_frases(client: httpx.AsyncClient, session_id: str, part: IRTake) -> None:
    for frase in range(5):
        told = await client.post(
            f"{PREFIX}/sessions/{session_id}/back-translation/chunks",
            headers={"X-Room-Device": TABLET},
            data={
                "take_id": part.id,
                "starts_ms": str(frase * 1000),
                "ends_ms": str((frase + 1) * 1000),
            },
            files={"file": ("frase.m4a", b"uma frase contada", "audio/mp4")},
        )
        assert told.status_code == 200, told.text


async def test_five_frases_told_back_ask_no_model_anything_before_terminei(
    db_session: AsyncSession,
    per_request: async_sessionmaker[AsyncSession],
    analyst: Analyst,
    room: Room,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session, (part,) = await rehearsed_in_parts_of(db_session, [0])

    async with room_client(db_session, monkeypatch, per_request=per_request) as client:
        await _tell_five_frases(client, session.id, part)

    assert analyst.whole_readings == 0, (
        "cada frase guardada mandava o analista ler a tradução enquanto a equipe traduzia"
    )
    assert (room.briefs, room.judged, room.said) == ([], [], [])


async def test_a_frase_told_again_asks_no_model_anything_before_terminei(
    db_session: AsyncSession,
    per_request: async_sessionmaker[AsyncSession],
    analyst: Analyst,
    room: Room,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session, (part,) = await rehearsed_in_parts_of(db_session, [0])

    async with room_client(db_session, monkeypatch, per_request=per_request) as client:
        await _tell_five_frases(client, session.id, part)
        third = (await final_segments(db_session, session.id))[2]
        retold = await client.post(
            f"{PREFIX}/sessions/{session.id}/segments/{third.id}/replace",
            headers={"X-Room-Device": TABLET},
            data={"take_id": part.id, "starts_ms": "2000", "ends_ms": "3000"},
            files={"file": ("de-novo.m4a", b"contada de novo", "audio/mp4")},
        )

    assert retold.status_code == 200, retold.text
    assert analyst.whole_readings == 0, (
        "a frase contada de novo mandava o analista ler a tradução antes do terminei"
    )
    assert (room.briefs, room.judged, room.said) == ([], [], [])


async def test_five_frases_checked_at_terminei_get_the_verdict_of_a_reading_made_at_terminei(
    db_session: AsyncSession,
    per_request: async_sessionmaker[AsyncSession],
    analyst: Analyst,
    room: Room,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session, (part,) = await rehearsed_in_parts_of(db_session, [0])
    analyst.readings = [AN_ADDITION_ON_FRASE_2]

    async with room_client(db_session, monkeypatch, per_request=per_request) as client:
        await _tell_five_frases(client, session.id, part)
        read_before = analyst.whole_readings
        verdict = (
            await press_terminei(client, session.id, report=played_every_part([part.id]))
        ).json()
        second = (await final_segments(db_session, session.id))[1]

    assert analyst.whole_readings - read_before == 1, (
        "o terminei servia uma leitura feita antes dele, em segundo plano"
    )
    assert verdict["refusal"] is None
    assert verdict["checked"] is False
    assert verdict["used_fail_safe"] is False
    assert verdict["finding_kind"] == "addition"
    assert verdict["finding_segment_id"] == second.id
    assert len(room.briefs) == 1


async def test_a_reading_stored_ahead_before_the_deploy_never_answers_terminei(
    db_session: AsyncSession,
    per_request: async_sessionmaker[AsyncSession],
    analyst: Analyst,
    room: Room,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session, (part,) = await rehearsed_in_parts_of(db_session, [0])
    analyst.readings = [AN_ADDITION_ON_FRASE_2]

    async with room_client(db_session, monkeypatch, per_request=per_request) as client:
        await _tell_five_frases(client, session.id, part)
        told = await final_segments(db_session, session.id)
        row = await get_session(db_session, session.id)
        await db_session.refresh(row)
        row.back_translation = {
            **(row.back_translation or {}),
            "read_ahead": {
                "segment_ids": [stretch.id for stretch in told],
                "findings": [],
                "nuances": [],
            },
        }
        await db_session.commit()
        verdict = (
            await press_terminei(client, session.id, report=played_every_part([part.id]))
        ).json()

    assert analyst.whole_readings == 1, (
        "uma leitura adiantada guardada antes do deploy respondia o terminei"
    )
    assert verdict["checked"] is False
    assert verdict["finding_kind"] == "addition"
    assert verdict["finding_segment_id"] == told[1].id
