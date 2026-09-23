"""ENG-991: transcription starts beside the session read, not after it.

Two SELECTs to Neon — `get_session` and, on a resend, `answered_turn` — used to finish before
the audio was even handed to the transcriber. Neon is a 20-30 ms round trip away, and nothing
about those two reads needs to happen before the recording starts moving. Once a session's
language has been seen once in this process, a later turn starts transcription right beside
the reads instead of behind them, and gives it up if the reads turn out to mean a replay or a
session that no longer exists.
"""

from __future__ import annotations

import json
import sys
from collections import OrderedDict
from typing import Any

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.internalization_room import sessions as sessions_api
from app.services.internalization_room.hearing import HeardSpeech
from app.services.internalization_room.sessions import create_session
from app.services.platform.tts import SynthesizedSpeech
from tests.release_harness import KEY, PREFIX, P

TEAM_ANSWER = "Noemi voltou para Belém com Rute no tempo da colheita"
GUIDE_LINE = "Vamos ficar nesta cena. O que vocês contariam?"


class _Model:
    """A Guide that always drafts one line and a Validator that always passes it."""

    async def __call__(self, *, system_prompt: str, **_: Any) -> str:
        if "corrected_response" in system_prompt:
            return json.dumps({"verdict": "pass", "issues": []})
        return GUIDE_LINE


class _Voice:
    def __init__(self) -> None:
        self.calls = 0

    async def __call__(self, text: str, **_: Any) -> tuple[SynthesizedSpeech, bool]:
        self.calls += 1
        entry = SynthesizedSpeech(
            audio=b"audio", mime_type="audio/mpeg", etag="e", cached=False, key=f"tts/v/{self.calls}.mp3"
        )
        return entry, False


async def _hearing(*_: Any, **__: Any) -> HeardSpeech:
    return HeardSpeech(text=TEAM_ANSWER)


async def _noop_settle(**_: Any) -> None:
    return None


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    from fastapi import FastAPI

    from app.api.internalization_room import router
    from app.core.config import get_settings
    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers

    monkeypatch.setattr(get_settings(), "internalization_room_api_key", KEY, raising=False)
    monkeypatch.setattr(sys.modules["app.services.internalization_room.run_turn"], "call_agent", _Model())
    monkeypatch.setattr(sessions_api.room, "synthesize_facilitator_speech", _Voice())
    monkeypatch.setattr(sessions_api, "heard_speech", _hearing)
    monkeypatch.setattr(sessions_api, "settle_coverage", _noop_settle)

    test_app = FastAPI()
    test_app.include_router(router, prefix=PREFIX)
    register_exception_handlers(test_app)

    async def _get_db():
        yield db_session

    test_app.dependency_overrides[get_db] = _get_db
    transport = ASGITransport(app=test_app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _an_opening_turn(client: httpx.AsyncClient, session_id: str) -> httpx.Response:
    """A turn with no audio — the shape the app sends first, which reads the session too."""
    return await client.post(f"{PREFIX}/sessions/{session_id}/turns", headers={"X-Room-Key": KEY})


async def _a_spoken_turn(
    client: httpx.AsyncClient, session_id: str, *, turn_id: str | None = None
) -> httpx.Response:
    data = {"turn_id": turn_id} if turn_id else {}
    return await client.post(
        f"{PREFIX}/sessions/{session_id}/turns",
        headers={"X-Room-Key": KEY},
        data=data,
        files={"file": ("resposta.m4a", b"audio", "audio/m4a")},
    )


async def test_the_session_language_is_remembered_once_the_session_has_been_read(
    client: httpx.AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sessions_api, "_LANGUAGE_MEMO", OrderedDict())
    session = await create_session(db_session, language="pt", pericope=P)

    opened = await _an_opening_turn(client, session.id)

    assert opened.status_code == 200, opened.text[:300]
    assert sessions_api._LANGUAGE_MEMO.get(session.id) == "pt", (
        "a sessão foi lida e a língua dela não ficou guardada para o próximo turno"
    )


def test_the_memo_holds_at_most_a_thousand_and_twenty_four_sessions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sessions_api, "_LANGUAGE_MEMO", OrderedDict())

    for n in range(sessions_api._LANGUAGE_MEMO_MAX + 5):
        sessions_api._remember_language(f"session-{n}", "pt")

    assert len(sessions_api._LANGUAGE_MEMO) == sessions_api._LANGUAGE_MEMO_MAX
    assert "session-0" not in sessions_api._LANGUAGE_MEMO, (
        "o memo cresceu sem teto, e a entrada mais antiga sobreviveu"
    )
    newest = f"session-{sessions_api._LANGUAGE_MEMO_MAX + 4}"
    assert newest in sessions_api._LANGUAGE_MEMO
