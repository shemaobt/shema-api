"""ENG-1303 — a live opening is one reply, voiced once, never a panorama clip and a scene clip.

Her prompt has the opening as one reply from the voice. The room used to ask the Guide for a
`[[CENA]]` mark on the session's first line and cut the reply there into two clips, the
whole passage and then the scene, synthesizing a third clip of the whole line in the
background. Her prompt never asks for the mark, so the cut only ever fired on a draft that
happened to carry it; the tablet now gets the reply as the one clip it plays.
"""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.internalization_room.sessions import create_session
from app.services.platform import tts
from tests.turn_harness import the_room_agent_is

PREFIX = "/api/internalization-room"
KEY = "sala-de-teste"

WHOLE = "O todo da passagem.\n\nA cena e o convite."
HEARD_WHOLE = "O todo da passagem. A cena e o convite."
MARKED = "O todo da passagem.\n[[CENA]]\nA cena e o convite."


class _Bucket:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    async def get(self, key: str) -> bytes | None:
        return self.objects.get(key)

    async def exists(self, key: str) -> bool:
        return key in self.objects

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        self.objects[key] = data


class _Elevenlabs:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def post(self, *_: Any, json: dict[str, Any], **__: Any) -> SimpleNamespace:
        self.calls.append(json["text"])
        return SimpleNamespace(
            status_code=200, content=f"audio-for-{json['text']}".encode(), text=""
        )


@pytest.fixture()
def bucket() -> _Bucket:
    return _Bucket()


@pytest.fixture()
def elevenlabs() -> _Elevenlabs:
    return _Elevenlabs()


async def _client(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    elevenlabs: _Elevenlabs,
    bucket: _Bucket,
) -> httpx.AsyncClient:
    from fastapi import FastAPI

    from app.api.internalization_room import router
    from app.core.config import get_settings
    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers

    monkeypatch.setattr(get_settings(), "internalization_room_api_key", KEY, raising=False)
    monkeypatch.setattr(get_settings(), "elevenlabs_api_key", "fake-elevenlabs", raising=False)
    monkeypatch.setattr(tts, "_make_client", lambda: elevenlabs)
    monkeypatch.setattr(tts, "_default_store", lambda _: bucket)

    test_app = FastAPI()
    test_app.include_router(router, prefix=PREFIX)
    register_exception_handlers(test_app)

    async def _get_db():
        yield db_session

    test_app.dependency_overrides[get_db] = _get_db
    transport = ASGITransport(app=test_app, raise_app_exceptions=False)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


async def _opened(client: httpx.AsyncClient, session_id: str) -> httpx.Response:
    return await asyncio.wait_for(
        client.post(f"{PREFIX}/sessions/{session_id}/turns", headers={"X-Room-Key": KEY}),
        timeout=5,
    )


async def test_a_passage_opening_the_guide_cut_with_the_old_scene_mark_is_still_one_clip(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    bucket: _Bucket,
    elevenlabs: _Elevenlabs,
) -> None:
    async def guide(*, system_prompt: str, **_: Any) -> str:
        if "corrected_response" in system_prompt:
            return json.dumps({"verdict": "pass", "issues": []})
        return MARKED

    the_room_agent_is(monkeypatch, turn=guide)
    session = await create_session(db_session, language="pt", pericope="P03")

    async with await _client(db_session, monkeypatch, elevenlabs, bucket) as client:
        opened = await _opened(client, session.id)

    assert opened.status_code == 200, opened.text
    assert opened.json().get("segments", []) == [], (
        "a abertura chegava ao tablet cortada em panorama e cena"
    )
    assert len(elevenlabs.calls) == 1, (
        f"a abertura foi sintetizada em {len(elevenlabs.calls)} pedaços: {elevenlabs.calls}"
    )


async def test_a_one_reply_opening_is_synthesized_once_in_the_words_the_team_hears(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    bucket: _Bucket,
    elevenlabs: _Elevenlabs,
) -> None:
    from app.api.internalization_room import sessions as sessions_api
    from app.services.internalization_room.run_turn import TurnOutcome

    async def _opening(**_: Any) -> TurnOutcome:
        return TurnOutcome(speech=WHOLE, transcript="")

    monkeypatch.setattr(sessions_api.room, "run_panorama_turn", _opening)
    session = await create_session(db_session, language="pt", pericope="OV")

    async with await _client(db_session, monkeypatch, elevenlabs, bucket) as client:
        opened = await _opened(client, session.id)

    assert opened.status_code == 200, opened.text
    assert elevenlabs.calls == [HEARD_WHOLE], (
        "a abertura de uma fala só passou a sintetizar mais do que a fala inteira"
    )
