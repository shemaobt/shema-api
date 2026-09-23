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
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.internalization_room import sessions as sessions_api
from app.services.internalization_room.hearing import HeardSpeech
from app.services.internalization_room.sessions import append_exchange, create_session, get_session
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
    client, db_session, test_engine, fan_out
) -> None:
    """The Guide, the Validator and the voice stay once-only; the transcriber does not.

    ENG-991 has a resend hand its audio to the transcriber before the resend check can be
    read, so it can start beside that check instead of behind it — the fake here has no
    network hop to be cancelled out of, so unlike a real one it always finishes. The turn
    those two calls point at is still answered once, which is what `answered_turn` guards.
    """
    session = await create_session(db_session, language="pt", pericope=P)

    first = await _post_a_turn(client, session.id, turn_id="turno-1")
    assert first.status_code == 200, first.text[:300]

    second = await _post_a_turn(client, session.id, turn_id="turno-1")
    assert second.status_code == 200, second.text[:300]

    assert second.json() == first.json(), "a resend must answer with the turn already given"
    assert fan_out["hearing"].calls == 2, "a resend's audio starts transcription beside the resend check"
    assert fan_out["model"].calls == 2, "the Guide or the Validator ran a second time"
    assert fan_out["voice"].calls == 1, "the line was synthesized twice"

    async with async_sessionmaker(test_engine, class_=AsyncSession)() as fresh_db:
        reread = await get_session(fresh_db, session.id)
    guide_lines = [m["text"] for m in (reread.messages or []) if m.get("role") == "guide"]
    assert guide_lines == [GUIDE_LINE], "the resend appended a second exchange to the transcript"


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


async def test_a_turn_id_over_the_column_width_is_refused_before_any_work_runs(
    client, db_session, fan_out
) -> None:
    session = await create_session(db_session, language="pt", pericope=P)
    too_long = "x" * 65

    refused = await client.post(
        f"{PREFIX}/sessions/{session.id}/turns",
        headers={"X-Room-Key": KEY},
        data={"turn_id": too_long},
        files={"file": ("resposta.m4a", b"audio", "audio/m4a")},
    )

    assert refused.status_code == 422, refused.text[:300]
    assert fan_out["hearing"].calls == 0
    assert fan_out["model"].calls == 0
    assert fan_out["voice"].calls == 0


async def test_the_audio_less_walk_back_in_echoes_the_turn_id_too(
    client, db_session, fan_out
) -> None:
    """The third door out of the route, and the one the PR's own note to ENG-627 forgot."""
    session = await create_session(db_session, language="pt", pericope=P)
    session = await append_exchange(
        db_session, session, team_utterance="", guide_response=GUIDE_LINE
    )

    again = await client.post(
        f"{PREFIX}/sessions/{session.id}/turns",
        headers={"X-Room-Key": KEY},
        data={"turn_id": "turno-de-volta"},
    )

    assert again.status_code == 200, again.text[:300]
    assert again.json()["turn_id"] == "turno-de-volta"
    assert fan_out["hearing"].calls == 0
    assert fan_out["model"].calls == 0
