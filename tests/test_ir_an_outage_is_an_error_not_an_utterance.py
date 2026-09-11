"""A provider that stops answering is an error the room can recover from, never a line.

An outage, a timeout, a rejected key, credits run out mid-session: the turn loop used to
treat every one of them as a turn it could not make safe and speak the family-A fail-safe.
The next tap failed the same way, and the next — the team heard the same canned sentence
over and over, with no sign that anything was wrong and no reason to fetch a person.
Marcia's own branch hit exactly this on the first golden run, when the account's credits
ran out and the billing error came out of the speaker turn after turn.

Her rule, and question 13: a provider failure rises as a 502 with the cause, the tablet
shows the needs-a-person screen, and the session is left exactly as it was — no status
changes, no exchange is written, and once the provider answers again the next tap runs a
normal turn on the same session. The circle stays alive at `done` (DOCTRINE §4).
"""

import json
import logging
import sys
from types import SimpleNamespace
from typing import Any

import anthropic
import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import UpstreamServiceError
from app.db.models.internalization_room import IRSessionStatus
from app.services.internalization_room import llm
from app.services.internalization_room.hearing import HeardSpeech
from app.services.internalization_room.sessions import get_session
from app.services.platform.tts import SynthesizedSpeech

MODEL = "claude-fable-5-1"


def _settings() -> Settings:
    return Settings(
        database_url="sqlite+aiosqlite:///./test.db",
        anthropic_api_key="sk-ant-fake",
        tripod_voice_model=MODEL,
    )


def _request() -> httpx.Request:
    return httpx.Request("POST", "https://api.anthropic.com/v1/messages")


def _status(code: int) -> httpx.Response:
    return httpx.Response(status_code=code, request=_request())


class _Refusing:
    """A provider that answers every call with the same failure."""

    def __init__(self, failure: Exception) -> None:
        self.failure = failure

    async def create(self, **_: Any) -> SimpleNamespace:
        raise self.failure


@pytest.fixture
def the_provider_fails(monkeypatch: pytest.MonkeyPatch):
    def _install(failure: Exception) -> None:
        monkeypatch.setattr(
            llm.anthropic,
            "AsyncAnthropic",
            lambda **_: SimpleNamespace(messages=_Refusing(failure)),
        )

    return _install


@pytest.mark.parametrize(
    ("failure", "reason"),
    [
        (
            anthropic.AuthenticationError("invalid x-api-key", response=_status(401), body=None),
            "invalid x-api-key",
        ),
        (
            anthropic.BadRequestError(
                "Your credit balance is too low", response=_status(400), body=None
            ),
            "Your credit balance is too low",
        ),
        (
            anthropic.InternalServerError("Overloaded", response=_status(529), body=None),
            "Overloaded",
        ),
        (anthropic.APITimeoutError(request=_request()), "timed out"),
    ],
    ids=["rejected key", "credits exhausted", "5xx", "timeout"],
)
async def test_a_provider_that_will_not_answer_rises_as_an_upstream_error_naming_the_cause(
    the_provider_fails, failure: Exception, reason: str
) -> None:
    the_provider_fails(failure)

    with pytest.raises(UpstreamServiceError) as raised:
        await llm.call_agent(system_prompt="s", user_content="u", settings=_settings())

    assert MODEL in str(raised.value) and reason in str(raised.value), (
        "a pane subia crua e o turno a engolia como fail-safe: saldo esgotado saía do "
        "alto-falante como 'Quero que a gente fique perto da passagem', turno após turno"
    )


PREFIX = "/api/internalization-room"
KEY = "sala-de-teste"
P = "P03"
GUIDE_LINE = "Vamos ficar nesta cena. O que vocês contariam?"
TEAM_ANSWER = "Noemi voltou para Belém com Rute no tempo da colheita"
OUTAGE = UpstreamServiceError(f"o modelo não respondeu em {MODEL}: invalid x-api-key")


class _Agent:
    """The Guide and the Validator answering as this test's script says.

    One entry per call, in the order the turn makes them: draft, verdict, draft, verdict.
    An exception in the script is what `call_agent` rises with when the provider refused
    the call. Once the script runs out both work and agree, so a call the test did not plan
    for can only make the turn healthier, never manufacture the failure it is looking for.
    """

    def __init__(self, script: list[Any]) -> None:
        self._script = list(script)

    async def __call__(self, *, system_prompt: str, user_content: str, **kwargs: Any) -> str:
        planned = self._script.pop(0) if self._script else None
        if isinstance(planned, BaseException):
            raise planned
        if planned is not None:
            return planned
        if "corrected_response" in system_prompt:
            return json.dumps({"verdict": "pass", "issues": []})
        return GUIDE_LINE


def _passes() -> str:
    return json.dumps({"verdict": "pass", "issues": []})


def _the_models_answer(monkeypatch: pytest.MonkeyPatch, *script: Any) -> None:
    module = sys.modules["app.services.internalization_room.run_turn"]
    monkeypatch.setattr(module, "call_agent", _Agent(list(script)))


@pytest.fixture()
async def spoken() -> list[str]:
    return []


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, spoken: list[str]):
    """The endpoint as the tablet reaches it, answering with whatever the handlers produce."""
    from fastapi import FastAPI

    from app.api.internalization_room import router
    from app.api.internalization_room import sessions as sessions_api
    from app.core.config import get_settings
    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers

    monkeypatch.setattr(get_settings(), "internalization_room_api_key", KEY, raising=False)

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
        return HeardSpeech(text=TEAM_ANSWER)

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


async def _a_room_opening_a_passage(client: httpx.AsyncClient) -> str:
    created = await client.post(
        f"{PREFIX}/sessions",
        headers={"X-Room-Key": KEY},
        json={"pericope": P, "language": "pt"},
    )
    assert created.status_code == 200
    return created.json()["session_id"]


async def _the_room_takes_a_turn(client: httpx.AsyncClient, session_id: str) -> httpx.Response:
    return await client.post(f"{PREFIX}/sessions/{session_id}/turns", headers={"X-Room-Key": KEY})


async def _the_team_answers(client: httpx.AsyncClient, session_id: str) -> httpx.Response:
    return await client.post(
        f"{PREFIX}/sessions/{session_id}/turns",
        headers={"X-Room-Key": KEY},
        files={"file": ("answer.m4a", b"audio", "audio/m4a")},
    )


async def test_a_turn_the_provider_refused_is_a_502_with_the_cause_and_speaks_nothing(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch, spoken: list[str]
) -> None:
    _the_models_answer(monkeypatch, OUTAGE)
    session_id = await _a_room_opening_a_passage(client)

    answered = await _the_room_takes_a_turn(client, session_id)

    assert answered.status_code == 502, (
        f"a pane virava linha enlatada com 200, e a equipe a ouvia de novo a cada toque: "
        f"{answered.text[:300]}"
    )
    body = answered.json()
    assert body["code"] == "UPSTREAM_ERROR"
    assert "invalid x-api-key" in body["detail"], "o corpo tem de nomear a causa"
    assert spoken == [], "um turno que falhou não tem fala para sintetizar"


async def test_a_turn_that_failed_writes_no_exchange_and_leaves_the_status_where_it_was(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch, db_session: AsyncSession
) -> None:
    """Nothing is written for a call that produced nothing.

    An exchange written for a failed turn would push a halted session back to in-progress
    on the strength of a tap that nobody answered, and a status changed on the failure
    would be exactly the terminal state Marcia refused: the circle stays alive.
    """
    _the_models_answer(monkeypatch, GUIDE_LINE, _passes(), OUTAGE)
    session_id = await _a_room_opening_a_passage(client)
    assert (await _the_room_takes_a_turn(client, session_id)).status_code == 200
    before = await get_session(db_session, session_id)
    status_before, messages_before = before.status, list(before.messages or [])
    assert status_before == "in_progress" and len(messages_before) == 1

    answered = await _the_team_answers(client, session_id)

    assert answered.status_code == 502, answered.text[:300]
    after = await get_session(db_session, session_id)
    assert after.status == status_before, "a pane não muda o estado da sessão"
    assert list(after.messages or []) == messages_before, (
        "um turno que levantou não grava a fala da equipe nem uma resposta vazia do Guia"
    )


async def test_once_the_provider_answers_again_the_next_tap_is_a_normal_turn_on_the_same_session(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    spoken: list[str],
    db_session: AsyncSession,
) -> None:
    """No state is entered that a turn cannot leave: the tap after the outage just works."""
    _the_models_answer(monkeypatch, OUTAGE, GUIDE_LINE, _passes())
    session_id = await _a_room_opening_a_passage(client)
    assert (await _the_room_takes_a_turn(client, session_id)).status_code == 502

    answered = await _the_room_takes_a_turn(client, session_id)

    assert answered.status_code == 200, answered.text[:300]
    body = answered.json()
    assert body["used_fail_safe"] is False and body["fixed_line"] == ""
    assert spoken == [GUIDE_LINE], "a batida seguinte é um turno normal, sem linha enlatada"
    session = await get_session(db_session, session_id)
    assert list(session.messages or []) == [{"role": "guide", "text": GUIDE_LINE}], (
        "a sessão é a mesma, e só o turno que respondeu ficou gravado"
    )


async def test_a_session_at_done_still_takes_a_turn_because_the_circle_is_alive(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    spoken: list[str],
    db_session: AsyncSession,
) -> None:
    """DOCTRINE §4: the ledger informs, it never ends the conversation."""
    _the_models_answer(monkeypatch, GUIDE_LINE, _passes(), GUIDE_LINE, _passes())
    session_id = await _a_room_opening_a_passage(client)
    assert (await _the_room_takes_a_turn(client, session_id)).status_code == 200
    session = await get_session(db_session, session_id)
    session.status = IRSessionStatus.DONE
    await db_session.commit()

    answered = await _the_team_answers(client, session_id)

    assert answered.status_code == 200, (
        f"uma sessão em done recusava o turno — estado terminal no servidor: {answered.text[:300]}"
    )
    assert spoken == [GUIDE_LINE, GUIDE_LINE]


async def test_a_failed_turn_logs_its_cause_and_never_what_the_team_said(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """An outage the operation cannot see is the one it cannot fix — and the team's words
    are not part of what it needs to see. A transcript in an operations log is the team's
    speech kept somewhere nobody agreed to."""
    _the_models_answer(monkeypatch, GUIDE_LINE, _passes(), OUTAGE)
    session_id = await _a_room_opening_a_passage(client)
    await _the_room_takes_a_turn(client, session_id)

    with caplog.at_level(logging.WARNING):
        answered = await _the_team_answers(client, session_id)

    assert answered.status_code == 502, answered.text[:300]
    assert "invalid x-api-key" in caplog.text, "a pane tem de deixar a causa no log"
    assert TEAM_ANSWER not in caplog.text
