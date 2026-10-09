"""Every time the room could not hear the team, it says her first D line.

Her app calls `didntCatchThat(0)` at every miss: in the conversation, in the Panorama and on a
telling-back with nothing told. The other two D lines stay in her file and are never chosen.
"""

from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.internalization_room import sessions as sessions_api
from app.services.internalization_room.hearing import HeardSpeech
from app.services.internalization_room.sessions import create_session
from app.services.platform.tts import SynthesizedSpeech
from tests.device_harness import TABLET_TEAM
from tests.release_harness import PREFIX, P
from tests.room_harness import press_terminei, room_client

PANORAMA = "OV-Ruth"


async def _heard_nothing(*_: Any, **__: Any) -> HeardSpeech:
    return HeardSpeech(text="")


async def _voice(text: str, **_: Any) -> tuple[SynthesizedSpeech, bool]:
    entry = SynthesizedSpeech(
        audio=b"audio", mime_type="audio/mpeg", etag="e", cached=False, key="tts/voice/t.mp3"
    )
    return entry, False


async def _noop_settle(**_: Any) -> None:
    return None


@pytest.fixture()
async def client(db_session, monkeypatch):
    monkeypatch.setattr(sessions_api, "heard_speech", _heard_nothing)
    monkeypatch.setattr(sessions_api.room, "synthesize_facilitator_speech", _voice)
    monkeypatch.setattr(sessions_api, "settle_coverage", _noop_settle)
    async with room_client(db_session, monkeypatch) as c:
        yield c


async def _three_silent_takes(client, session_id: str) -> list[str]:
    heard = []
    for _ in range(3):
        answered = await client.post(
            f"{PREFIX}/sessions/{session_id}/turns",
            files={"file": ("silencio.m4a", b"audio", "audio/m4a")},
        )
        assert answered.status_code == 200, answered.text[:300]
        heard.append(answered.json()["fixed_line"])
    return heard


async def test_three_inaudible_takes_in_a_row_in_a_passage_session_each_hear_d_1(
    client, db_session: AsyncSession
) -> None:
    session = await create_session(db_session, project_id=TABLET_TEAM, language="pt", pericope=P)

    assert await _three_silent_takes(client, session.id) == ["D0", "D0", "D0"]


async def test_three_inaudible_takes_in_a_row_in_a_panorama_session_each_hear_d_1(
    client, db_session: AsyncSession
) -> None:
    session = await create_session(
        db_session, project_id=TABLET_TEAM, language="pt", pericope=PANORAMA
    )

    assert await _three_silent_takes(client, session.id) == ["D0", "D0", "D0"]


@pytest.mark.parametrize("stored", [1, 2, 3])
async def test_an_empty_telling_back_hears_d_1_whatever_the_number_of_messages_so_far(
    client, db_session: AsyncSession, stored: int
) -> None:
    session = await create_session(db_session, project_id=TABLET_TEAM, language="pt", pericope=P)
    session.messages = [
        {"role": "guide", "text": "Vamos conhecer a cena.", "outcome": "pass"}
    ] * stored
    await db_session.commit()

    answer = await press_terminei(client, session.id)

    assert answer.status_code == 200, answer.text[:300]
    assert answer.json()["fixed_line"] == "D0"
