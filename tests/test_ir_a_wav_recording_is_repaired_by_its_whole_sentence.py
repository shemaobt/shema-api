"""On a WAV recording her Speaker is told the team can record the whole sentence again.

Her check hands the Speaker, beside each finding, what the team can do about it: `repair`
is "sentence" where the recording is WAV and "part" anywhere else (her `repairOf`,
src/backtranslation/repair.ts at 18fa7c4). Ours handed "part" on every finding, so on her
script P01-regravar-frase-faltou the voice sent the team to record «a parte» again where hers
asks for the whole sentence.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from tests.room_harness import (
    Room,
    ScriptedAnalyst,
    heard_every_part,
    press_terminei,
    rehearsed_in_parts,
    room_client,
    the_analyst_is_scripted,
    the_room_speaks,
)

WAV = "audio/wav"


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


def _handed(brief: str) -> list[dict[str, Any]]:
    block = brief.split("## The findings for ", 1)[1].split("\n## ", 1)[0]
    return list(json.loads(block[block.index("[") :]))


async def _terminei(client: httpx.AsyncClient, db: AsyncSession, session_id: str) -> None:
    pressed = await press_terminei(
        client, session_id, report=await heard_every_part(db, session_id)
    )
    assert pressed.status_code == 200, pressed.text


@pytest.mark.parametrize(
    "finding",
    [
        {"kind": "addition", "note": "o pedido das noras", "frase": 2},
        {
            "kind": "nuance",
            "note": "O tempo ficou solto.",
            "frase": 2,
            "quote": "contada de volta",
            "story": "foi naquela mesma noite",
        },
    ],
)
async def test_a_finding_on_a_wav_part_tells_her_speaker_the_sentence_can_be_recorded_again(
    client, db_session, analyst: ScriptedAnalyst, room: Room, finding: dict[str, Any]
) -> None:
    session, _ = await rehearsed_in_parts(db_session, 2, content_types=(WAV, WAV))
    analyst.readings = [{"findings": [finding]}]

    await _terminei(client, db_session, session.id)

    assert [one["repair"] for one in _handed(room.briefs[-1])] == ["sentence"], (
        "numa gravação WAV o falante ouvia «part» e mandava gravar a parte de novo"
    )
