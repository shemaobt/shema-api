"""ENG-1031: a turn is answered only for the project that owns the session.

`take_turn` resolved a session by id alone, the way `approve_internalization_release` used
to before it adopted `get_session_for_room_caller`, so a device from another project's turn
ran transcription, the Guide, the Validator and synthesis against somebody else's recording
before the room ever turned it away.
"""

from __future__ import annotations

import json
import sys
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.internalization_room import sessions as sessions_api
from app.services.internalization_room.hearing import HeardSpeech
from app.services.internalization_room.sessions import create_session
from app.services.platform.tts import SynthesizedSpeech
from tests.release_harness import KEY, P, PREFIX, a_claimed_device, team_headers
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
    """The three legs of the turn's own work, each counted, none of them real."""
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


async def _post_a_turn(client, session_id: str, headers: dict[str, str]):
    return await client.post(
        f"{PREFIX}/sessions/{session_id}/turns",
        headers=headers,
        files={"file": ("resposta.m4a", b"audio", "audio/m4a")},
    )


async def test_a_turn_from_another_projects_device_is_refused_before_any_work_runs(
    client, db_session: AsyncSession, fan_out
) -> None:
    owner, credential_owner = await a_claimed_device(db_session, email="owner@example.com")
    _stranger, credential_stranger = await a_claimed_device(db_session, email="stranger@example.com")
    session = await create_session(db_session, language="pt", pericope=P, project_id=owner.id)

    stranger = await _post_a_turn(client, session.id, team_headers(credential_stranger))
    owner_reply = await _post_a_turn(client, session.id, team_headers(credential_owner))

    assert stranger.status_code == 404, stranger.text[:300]
    assert owner_reply.status_code == 200, owner_reply.text[:300]
    assert fan_out["hearing"].calls == 1, "o áudio de outro projeto chegou a ser transcrito"
    assert fan_out["model"].calls == 2, "o Guia ou o Validador rodaram para o estranho"
    assert fan_out["voice"].calls == 1, "a linha foi sintetizada para o estranho"


async def test_a_hot_language_memo_does_not_speculate_for_another_project(
    client, db_session: AsyncSession, fan_out
) -> None:
    """The memo ENG-991 reads before the session is a language, and the language alone
    used to be enough to start transcribing — so a session another project's owner had
    already warmed for the room let a stranger's turn begin work no check had cleared.
    """
    owner, credential_owner = await a_claimed_device(db_session, email="owner4@example.com")
    _stranger, credential_stranger = await a_claimed_device(db_session, email="stranger4@example.com")
    session = await create_session(db_session, language="pt", pericope=P, project_id=owner.id)

    warm = await _post_a_turn(client, session.id, team_headers(credential_owner))
    assert warm.status_code == 200, warm.text[:300]
    fan_out["hearing"].calls = 0
    fan_out["model"].calls = 0
    fan_out["voice"].calls = 0

    stranger = await _post_a_turn(client, session.id, team_headers(credential_stranger))

    assert stranger.status_code == 404, stranger.text[:300]
    assert fan_out["hearing"].calls == 0, "a transcrição especulativa rodou para outro projeto"


async def test_a_room_key_caller_is_refused_on_a_project_owned_session(
    client, db_session: AsyncSession, fan_out
) -> None:
    owner, _credential = await a_claimed_device(db_session, email="owner2@example.com")
    session = await create_session(db_session, language="pt", pericope=P, project_id=owner.id)

    refused = await _post_a_turn(
        client, session.id, {"X-Room-Key": KEY, "X-Room-Device": "tablet-sem-dono"}
    )

    assert refused.status_code == 404, refused.text[:300]
    assert fan_out["hearing"].calls == 0
    assert fan_out["model"].calls == 0
    assert fan_out["voice"].calls == 0
