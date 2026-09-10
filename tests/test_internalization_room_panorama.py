import json
import sys
from typing import Any

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.models.internalization_room import IRPromptKey, IRSessionStatus
from app.services.internalization_room._default_prompts import default_prompt
from app.services.internalization_room.canon.book_material import build_book_material
from app.services.internalization_room.coverage import counts
from app.services.internalization_room.fail_safe import FailSafe, utterances
from app.services.internalization_room.hearing import HeardSpeech
from app.services.internalization_room.run_turn import TurnOutcome, run_panorama_turn
from app.services.internalization_room.sessions import (
    book_of,
    create_session,
    is_panorama,
    resolve_pericope,
)
from app.services.platform.tts import SynthesizedSpeech

PANORAMA = default_prompt(IRPromptKey.BOOK_PANORAMA)["prompt"]
VALIDATOR = default_prompt(IRPromptKey.VALIDATOR)["prompt"]
OV = "OV-Ruth"
PREFIX = "/api/internalization-room"
KEY = "sala-de-teste"


def _settings() -> Settings:
    return Settings(database_url="sqlite+aiosqlite:///./test.db", google_api_key="fake")


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    """The turn endpoint as the tablet reaches it, in a panorama session.

    `run_panorama_turn` is patched per test at `sessions_api.room`, the same seam
    `test_internalization_room_api.py` uses — the endpoint reads it off the `room` module,
    not by name, so a bare-function monkeypatch there is what the route actually calls.
    """
    from fastapi import FastAPI

    from app.api.internalization_room import router
    from app.api.internalization_room import sessions as sessions_api
    from app.core.config import get_settings
    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers

    monkeypatch.setattr(get_settings(), "internalization_room_api_key", KEY, raising=False)

    async def _speech(text: str, **_: object) -> tuple[SynthesizedSpeech, bool]:
        entry = SynthesizedSpeech(
            audio=b"audio",
            mime_type="audio/mpeg",
            etag="e",
            cached=False,
            key=f"tts/v/m/f/{abs(hash(text))}.mp3",
        )
        return entry, False

    async def _no_prepared_opening(*_: Any, **__: Any) -> None:
        return None

    monkeypatch.setattr(sessions_api.room, "synthesize_facilitator_speech", _speech)
    monkeypatch.setattr(sessions_api, "prepare_opening", _no_prepared_opening)

    test_app = FastAPI()
    test_app.include_router(router, prefix=PREFIX)
    register_exception_handlers(test_app)

    async def _get_db():
        yield db_session

    test_app.dependency_overrides[get_db] = _get_db
    transport = ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _open_panorama(client: httpx.AsyncClient) -> str:
    created = await client.post(
        f"{PREFIX}/sessions", headers={"X-Room-Key": KEY}, json={"pericope": "OV", "language": "pt"}
    )
    session_id: str = created.json()["session_id"]
    await client.post(f"{PREFIX}/sessions/{session_id}/turns", headers={"X-Room-Key": KEY})
    return session_id


async def _speak(client: httpx.AsyncClient, session_id: str, filename: str) -> httpx.Response:
    return await client.post(
        f"{PREFIX}/sessions/{session_id}/turns",
        headers={"X-Room-Key": KEY},
        files={"file": (filename, b"audio", "audio/m4a")},
    )


class FakeAgent:
    def __init__(self, verdict: dict[str, Any], draft: str = "Vamos conhecer o livro."):
        self.verdict = verdict
        self.draft = draft
        self.systems: list[str] = []

    async def __call__(self, *, system_prompt: str, user_content: str, **kwargs: Any) -> str:
        self.systems.append(system_prompt)
        if "corrected_response" in system_prompt:
            return json.dumps(self.verdict)
        return self.draft


@pytest.fixture
def patch_agent(monkeypatch: pytest.MonkeyPatch):
    module = sys.modules["app.services.internalization_room.run_turn"]

    def _install(agent: FakeAgent) -> FakeAgent:
        monkeypatch.setattr(module, "call_agent", agent)
        return agent

    return _install


def test_a_book_id_is_recognised_as_a_panorama() -> None:
    assert is_panorama(OV)
    assert book_of(OV) == "Ruth"
    assert not is_panorama("P03")
    assert book_of("P03") == "Ruth"


def test_the_bare_alias_resolves_to_the_book_the_room_serves() -> None:
    """A client asks for `OV` and never learns which book it is — the canon stays here."""
    assert resolve_pericope("OV") == OV
    assert resolve_pericope("P03") == "P03"


@pytest.mark.asyncio
async def test_the_alias_opens_a_real_panorama_session(db_session: AsyncSession) -> None:
    session = await create_session(db_session, pericope="OV")

    assert session.pericope == OV
    assert is_panorama(session.pericope)


@pytest.mark.asyncio
async def test_a_panorama_session_has_no_coverage_spine(db_session: AsyncSession) -> None:
    """It prepares the team to enter the book; it asks no retelling and never completes."""
    session = await create_session(db_session, pericope=OV)

    assert session.coverage_state == {}
    assert counts(session.coverage_state) == {"engaged": 0, "surfaced": 0, "total": 0}
    assert session.status is IRSessionStatus.IN_PROGRESS


@pytest.mark.asyncio
async def test_the_panorama_is_grounded_on_the_book_material(patch_agent) -> None:
    agent = patch_agent(FakeAgent({"verdict": "pass", "issues": []}))
    material = build_book_material("Ruth")

    outcome = await run_panorama_turn(
        session_language="Portuguese",
        language_code="pt",
        transcript="",
        messages=[],
        panorama_prompt=PANORAMA,
        validator_prompt=VALIDATOR,
        book="Ruth",
        book_material=material,
        opening=True,
        settings=_settings(),
    )

    assert outcome.speech == "Vamos conhecer o livro."
    speaker_system = agent.systems[0]
    assert "THE BOOK OF RUTH" in speaker_system
    assert "PRESERVATION NOTES" in speaker_system


@pytest.mark.asyncio
async def test_the_validator_judges_against_the_same_material(patch_agent) -> None:
    """Containment is enforced twice in a panorama too, with the book as the standard."""
    agent = patch_agent(FakeAgent({"verdict": "pass", "issues": []}))

    await run_panorama_turn(
        session_language="Portuguese",
        language_code="pt",
        transcript="o que é esse livro?",
        messages=[],
        panorama_prompt=PANORAMA,
        validator_prompt=VALIDATOR,
        book="Ruth",
        book_material=build_book_material("Ruth"),
        settings=_settings(),
    )

    validator_system = agent.systems[1]
    assert "THE BOOK OF RUTH" in validator_system
    assert "{{" not in validator_system


@pytest.mark.asyncio
async def test_a_panorama_that_could_not_hear_the_team_is_a_degraded_turn(patch_agent) -> None:
    """The book session counts toward a facilitator the same way a passage does.

    Its fail-safe is a second copy of the one in `run_turn`, and a room that cannot hear the
    team is a room that is not working whichever session it is standing in."""
    agent = patch_agent(FakeAgent({"verdict": "pass", "issues": []}))

    outcome = await run_panorama_turn(
        session_language="Portuguese",
        language_code="pt",
        transcript="   ",
        messages=[{"role": "guide", "text": "vamos conhecer o livro"}],
        panorama_prompt=PANORAMA,
        validator_prompt=VALIDATOR,
        book="Ruth",
        book_material=build_book_material("Ruth"),
        settings=_settings(),
    )

    assert outcome.speech in utterances(FailSafe.INAUDIBLE, "pt")
    assert outcome.used_fail_safe is True
    assert outcome.degraded is True
    assert agent.systems == []


@pytest.mark.asyncio
async def test_a_rejected_panorama_turn_is_never_voiced(patch_agent) -> None:
    patch_agent(
        FakeAgent(
            {"verdict": "regenerate", "issues": [{"problem": "imported_knowledge"}]},
            draft="Rute se casa com Boaz no fim.",
        )
    )

    outcome = await run_panorama_turn(
        session_language="Portuguese",
        language_code="pt",
        transcript="como termina?",
        messages=[],
        panorama_prompt=PANORAMA,
        validator_prompt=VALIDATOR,
        book="Ruth",
        book_material=build_book_material("Ruth"),
        settings=_settings(),
    )

    assert outcome.used_fail_safe is True
    assert "Boaz" not in outcome.speech


async def test_a_panorama_past_its_opening_takes_a_second_and_a_third_utterance(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A panorama does not stop after the opening — the team keeps talking, turn after turn."""
    from app.api.internalization_room import sessions as sessions_api

    heard = ["pergunta dois", "pergunta três"]
    routed: list[str] = []

    async def _panorama(*, transcript: str, **_: Any) -> TurnOutcome:
        routed.append(transcript)
        return TurnOutcome(speech=f"resposta {len(routed)}.", transcript=transcript)

    async def _heard(_audio: bytes, **_: Any) -> HeardSpeech:
        return HeardSpeech(text=heard.pop(0))

    monkeypatch.setattr(sessions_api.room, "run_panorama_turn", _panorama)
    monkeypatch.setattr(sessions_api, "heard_speech", _heard)

    session_id = await _open_panorama(client)
    second = await _speak(client, session_id, "q2.m4a")
    third = await _speak(client, session_id, "q3.m4a")

    assert second.status_code == 200
    assert third.status_code == 200
    assert routed == ["", "pergunta dois", "pergunta três"], (
        "as duas falas seguintes à abertura têm de chegar ao motor do panorama"
    )
    for turn in (second, third):
        body = turn.json()
        assert body["audio_url"].startswith(f"{PREFIX}/voice/")
        assert body["transcript"]


async def test_the_third_turn_still_carries_the_sessions_first_exchange(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every call gets the whole conversation — no window drops the session's opening.

    A six-turn window would still hold this session's first exchange by the third turn, so
    it is asserted directly rather than merely counted: the opening's own line has to be the
    oldest entry the third call sees, word for word.
    """
    from app.api.internalization_room import sessions as sessions_api

    heard = ["pergunta dois", "pergunta três"]
    seen_messages: list[list[dict[str, Any]]] = []

    async def _panorama(
        *, transcript: str, messages: list[dict[str, Any]], **_: Any
    ) -> TurnOutcome:
        seen_messages.append(messages)
        return TurnOutcome(speech=f"resposta {len(seen_messages)}.", transcript=transcript)

    async def _heard(_audio: bytes, **_: Any) -> HeardSpeech:
        return HeardSpeech(text=heard.pop(0))

    monkeypatch.setattr(sessions_api.room, "run_panorama_turn", _panorama)
    monkeypatch.setattr(sessions_api, "heard_speech", _heard)

    session_id = await _open_panorama(client)
    await _speak(client, session_id, "q2.m4a")
    await _speak(client, session_id, "q3.m4a")

    opening_exchange = {"role": "guide", "text": "resposta 1."}
    assert seen_messages[0] == [], "a abertura não tem conversa nenhuma atrás dela"
    assert opening_exchange in seen_messages[2], (
        "o terceiro turno perdeu a primeira troca da sessão — isso é o que uma janela faria"
    )
    assert seen_messages[2] == [
        opening_exchange,
        {"role": "team", "text": "pergunta dois"},
        {"role": "guide", "text": "resposta 2."},
    ]


async def test_a_slow_panorama_turn_is_not_cut_short(patch_agent) -> None:
    """No prazo por chamada: a room speaking to a slow model still gets its answer.

    Nothing in the panorama's call path wraps the Guide or the Validator in a deadline
    of its own — the doctrine's own numbers (10-56 s, median 27 s per turn) only make
    sense with none. Each of the two real calls is made to take real time here; a
    regression that wrapped either in a short `asyncio.wait_for` would cut this turn
    to a fail-safe well before both had run.
    """
    import asyncio
    import time

    class _SlowAgent(FakeAgent):
        async def __call__(self, *, system_prompt: str, user_content: str, **kwargs: Any) -> str:
            await asyncio.sleep(0.3)
            return await super().__call__(
                system_prompt=system_prompt, user_content=user_content, **kwargs
            )

    agent = patch_agent(_SlowAgent({"verdict": "pass", "issues": []}))

    started = time.monotonic()
    outcome = await run_panorama_turn(
        session_language="Portuguese",
        language_code="pt",
        transcript="me contem mais",
        messages=[],
        panorama_prompt=PANORAMA,
        validator_prompt=VALIDATOR,
        book="Ruth",
        book_material=build_book_material("Ruth"),
        settings=_settings(),
    )
    elapsed = time.monotonic() - started

    assert elapsed >= 0.6, (
        "as duas chamadas (Guia e Validador) têm de esperar de verdade, sem atalho"
    )
    assert outcome.used_fail_safe is False
    assert outcome.speech == agent.draft
