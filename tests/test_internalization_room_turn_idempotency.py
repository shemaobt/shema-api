"""ENG-626: a turn posted twice under the same id runs the fan-out once, not twice.

`take_turn` had no request id and no dedupe, so a re-sent turn — the ordinary shape of a
client that timed out waiting for the first response — ran transcription, the Guide, the
Validator and synthesis all over again and appended a second exchange to the transcript.
"""

from __future__ import annotations

import json
import sys
from typing import Any

import pytest

from app.api.internalization_room import sessions as sessions_api
from app.services.internalization_room.hearing import HeardSpeech
from app.services.internalization_room.sessions import create_session, get_session
from app.services.platform.tts import SynthesizedSpeech
from tests.release_harness import KEY, PREFIX, P
from tests.room_harness import room_client

TEAM_ANSWER = "Noemi voltou para Belem com Rute no tempo da colheita"
GUIDE_LINE = "Vamos ficar nesta cena. O que voces contariam?"


class _CountingHearing:
    def __init__(self) -> None:
        self.calls = 0

    async def __call__(self, *_: Any, **__: Any) -> HeardSpeech:
        self.calls += 1
        return HeardSpeech(text=TEAM_ANSWER)


class _CountingModel:
    """A Guide that always drafts one line and a Validator that always passes it."""

    def __init__(self) -> None:
        self.calls = 0

    async def __call__(self, *, system_prompt: str, **_: Any) -> str:
        self.calls += 1
        if "corrected_response" in system_prompt:
            return json.dumps({"verdict": "pass", "issues": []})
        return GUIDE_LINE


class _CountingVoice:
    def __init__(self) -> None:
        self.calls = 0

    async def __call__(self, text: str, **_: Any) -> tuple[SynthesizedSpeech, bool]:
        self.calls += 1
        entry = SynthesizedSpeech(
            audio=b"audio",
            mime_type="audio/mpeg",
            etag="e",
            cached=False,
            key=f"tts/voice/turno-{self.calls}.mp3",
        )
        return entry, False


async def _noop_settle(**_: Any) -> None:
    return None


@pytest.fixture()
async def client(db_session, monkeypatch):
    async with room_client(db_session, monkeypatch) as c:
        yield c


@pytest.fixture()
def fan_out(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """The three legs of the fan-out the ticket names, each counted, none of them real."""
    hearing = _CountingHearing()
    monkeypatch.setattr(sessions_api, "heard_speech", hearing)

    model = _CountingModel()
    monkeypatch.setattr(
        sys.modules["app.services.internalization_room.run_turn"], "call_agent", model
    )

    voice = _CountingVoice()
    monkeypatch.setattr(sessions_api.room, "synthesize_facilitator_speech", voice)

    monkeypatch.setattr(sessions_api, "settle_coverage", _noop_settle)

    return {"hearing": hearing, "model": model, "voice": voice}


async def _post_a_turn(client, session_id: str, *, turn_id: str):
    return await client.post(
        f"{PREFIX}/sessions/{session_id}/turns",
        headers={"X-Room-Key": KEY},
        data={"turn_id": turn_id},
        files={"file": ("resposta.m4a", b"audio", "audio/m4a")},
    )


async def test_the_same_turn_id_posted_twice_runs_the_fan_out_once_and_appends_one_exchange(
    client, db_session, fan_out
) -> None:
    session = await create_session(db_session, language="pt", pericope=P)

    first = await _post_a_turn(client, session.id, turn_id="turno-1")
    assert first.status_code == 200, first.text[:300]

    second = await _post_a_turn(client, session.id, turn_id="turno-1")
    assert second.status_code == 200, second.text[:300]

    assert second.json() == first.json(), "a resend must answer with the turn already given"
    assert fan_out["hearing"].calls == 1, "the audio was transcribed twice"
    assert fan_out["model"].calls == 2, "the Guide or the Validator ran a second time"
    assert fan_out["voice"].calls == 1, "the line was synthesized twice"

    reread = await get_session(db_session, session.id)
    guide_lines = [m for m in (reread.messages or []) if m.get("role") == "guide"]
    assert guide_lines == [{"role": "guide", "text": GUIDE_LINE}], (
        "the resend appended a second exchange to the transcript"
    )


async def test_two_different_turn_ids_each_run_their_own_fan_out(
    client, db_session, fan_out
) -> None:
    """The counterweight: dedupe keys on the id, not on the session alone."""
    session = await create_session(db_session, language="pt", pericope=P)

    first = await _post_a_turn(client, session.id, turn_id="turno-1")
    assert first.status_code == 200, first.text[:300]

    second = await _post_a_turn(client, session.id, turn_id="turno-2")
    assert second.status_code == 200, second.text[:300]

    assert fan_out["hearing"].calls == 2
    assert fan_out["voice"].calls == 2
