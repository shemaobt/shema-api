"""The turn route answers or errors inside one generous bound; it never hangs.

Every call under it now carries the bound of its own, but a turn is up to three drafts
and six readings, and nine bounded calls in a row are still far past the ceiling the
deployment kills the request at. Her reference route accepts 300 s and the tablet lets go
just past it, at 305, with recovery: the error reaches the screen as the non-terminal
call-a-person affordance, the circle stays alive, and the next tap is a normal turn.
"""

import asyncio
import json
from typing import Any

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.internalization_room.hearing import HeardSpeech
from app.services.platform.tts import SynthesizedSpeech
from tests.turn_harness import the_agent_answers

PREFIX = "/api/internalization-room"
KEY = "sala-de-teste"
P = "P03"


class _Hung:
    """A model seam that never comes back, above the client and its own clock."""

    async def __call__(self, **_: Any) -> str:
        await asyncio.Event().wait()
        raise AssertionError("unreachable: nothing sets the event")


class _Answering:
    """A model seam that answers at once — after the one yield any network call makes."""

    async def __call__(self, *, system_prompt: str, **_: Any) -> str:
        await asyncio.sleep(0)
        if "corrected_response" in system_prompt:
            return json.dumps({"verdict": "pass", "issues": []})
        return "Vamos ficar nesta cena. O que vocês contariam?"


@pytest.fixture()
async def spoken() -> list[str]:
    return []


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, spoken: list[str]):
    """The endpoint as the tablet reaches it, on a room whose bound is a tenth of a second."""
    from fastapi import FastAPI

    from app.api.internalization_room import router
    from app.api.internalization_room import sessions as sessions_api
    from app.core.config import get_settings
    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers

    monkeypatch.setattr(get_settings(), "internalization_room_api_key", KEY, raising=False)
    monkeypatch.setattr(get_settings(), "internalization_room_turn_bound_ms", 100, raising=False)

    async def _speech(text: str, **_: object) -> tuple[SynthesizedSpeech, bool]:
        spoken.append(text)
        entry = SynthesizedSpeech(
            audio=b"audio",
            mime_type="audio/mpeg",
            etag="e",
            cached=False,
            key=f"tts/voice/m/f/{abs(hash(text))}.mp3",
        )
        return entry, False

    async def _heard(audio: bytes, **_: Any) -> HeardSpeech:
        return HeardSpeech(text="Noemi voltou para Belém com Rute")

    monkeypatch.setattr(sessions_api.room, "synthesize_facilitator_speech", _speech)
    monkeypatch.setattr(sessions_api, "heard_speech", _heard)

    test_app = FastAPI()
    test_app.include_router(router, prefix=PREFIX)
    register_exception_handlers(test_app)

    async def _get_db():
        yield db_session

    test_app.dependency_overrides[get_db] = _get_db
    transport = ASGITransport(app=test_app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_a_turn_whose_models_never_answer_is_a_502_inside_the_bound_not_a_line(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch, spoken: list[str]
) -> None:
    the_agent_answers(monkeypatch, _Hung())  # type: ignore[arg-type]
    created = await client.post(
        f"{PREFIX}/sessions", headers={"X-Room-Key": KEY}, json={"pericope": P, "language": "pt"}
    )
    assert created.status_code == 200
    session_id = created.json()["session_id"]

    answered = await asyncio.wait_for(
        client.post(f"{PREFIX}/sessions/{session_id}/turns", headers={"X-Room-Key": KEY}),
        timeout=5,
    )

    assert answered.status_code == 502, (
        f"a rota ficava pendurada com o provedor: a equipe diante de um círculo que nunca "
        f"respondia nem falhava, até alguém fechar o tablet: {answered.text[:300]}"
    )
    body = answered.json()
    assert body["code"] == "UPSTREAM_ERROR"
    assert "used_fail_safe" not in body, "um limite estourado é erro, nunca a linha A"
    assert spoken == [], "um turno que estourou não tem fala para sintetizar"


async def test_the_hearing_spends_the_same_bound_the_models_do(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch, spoken: list[str]
) -> None:
    """The clock starts when the turn reaches the route, not when the models are asked.

    Armed after the hearing, the bound landed strictly later than the platform's own cut
    at the same figure — by the upload and the transcription — so on a deployed turn the
    platform always won, and the 502 that names the cause and the line that names who was
    waiting were never written.
    """
    from app.api.internalization_room import sessions as sessions_api

    the_agent_answers(monkeypatch, _Answering())  # type: ignore[arg-type]

    async def _slow_hearing(audio: bytes, **_: Any) -> HeardSpeech:
        await asyncio.sleep(0.15)
        return HeardSpeech(text="Noemi voltou para Belém com Rute")

    monkeypatch.setattr(sessions_api, "heard_speech", _slow_hearing)
    created = await client.post(
        f"{PREFIX}/sessions", headers={"X-Room-Key": KEY}, json={"pericope": P, "language": "pt"}
    )
    session_id = created.json()["session_id"]

    answered = await asyncio.wait_for(
        client.post(
            f"{PREFIX}/sessions/{session_id}/turns",
            headers={"X-Room-Key": KEY},
            files={"file": ("answer.m4a", b"audio", "audio/m4a")},
        ),
        timeout=5,
    )

    assert answered.status_code == 502, (
        f"o limite só era armado depois da escuta, e a escuta não contava: {answered.text[:300]}"
    )
    assert spoken == []
