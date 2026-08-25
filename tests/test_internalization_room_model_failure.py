"""What the room says when the Guide or the Validator cannot be reached.

Read from the endpoint, because the failure being described is an HTTP one: a model or
transport error used to leave `take_turn` as a 500, which the tablet shows as a broken
room and which stops a session over an outage that lasted seconds. The fail-safe line the
policy already promises is the answer, and the endpoint names it in `fixed_line` — those
lines ship as audio inside the app, so a failing network costs no synthesis.
"""

import asyncio
import json
import logging
import sys
from typing import Any

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.internalization_room.fail_safe import FailSafe, utterances
from app.services.internalization_room.hearing import HeardSpeech
from app.services.platform.tts import SynthesizedSpeech

PREFIX = "/api/internalization-room"
KEY = "sala-de-teste"
P = "P03"
GUIDE_LINE = "Vamos ficar nesta cena. O que vocês contariam?"
CORRECTED_LINE = "Fiquem nesta cena. O que vocês contariam?"
TEAM_ANSWER = "Noemi voltou para Belém com Rute no tempo da colheita"


def _unrepairable_lines() -> set[str]:
    """The names the app plays for a turn nothing could repair, straight from the policy."""
    return {
        f"{FailSafe.UNREPAIRABLE}{index}"
        for index in range(len(utterances(FailSafe.UNREPAIRABLE, "pt")))
    }


class _Agent:
    """The Guide and the Validator answering as this test's script says.

    One entry per call, in the order the turn makes them: draft, verdict, draft, verdict.
    ``raise`` breaks the transport. Once the script runs out both work and agree, so a call
    the test did not plan for can only make the turn healthier, never manufacture the
    failure the test is looking for.
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


@pytest.fixture()
async def spoken() -> list[str]:
    return []


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, spoken: list[str]):
    """The endpoint as the tablet reaches it, answering with whatever the handlers produce.

    ``raise_app_exceptions=False`` because these tests are about the response a failing turn
    produces: re-raising would hide the 500 behind the exception that caused it, and there
    would be no status code left to assert on.
    """
    from fastapi import FastAPI

    from app.api.internalization_room import router
    from app.api.internalization_room import sessions as sessions_api
    from app.core.config import get_settings
    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers

    monkeypatch.setattr(get_settings(), "internalization_room_api_key", KEY, raising=False)

    async def _speech(text: str) -> tuple[SynthesizedSpeech, bool]:
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


def _the_models_answer(monkeypatch: pytest.MonkeyPatch, *script: Any) -> None:
    module = sys.modules["app.services.internalization_room.run_turn"]
    monkeypatch.setattr(module, "call_agent", _Agent(list(script)))


def _the_assessor_finds_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep the assessor out of the way on turns that carry a team answer."""
    module = sys.modules["app.services.internalization_room.comprehension.assessor"]

    async def _empty(**_: Any) -> str:
        return json.dumps(
            {
                "observations": [],
                "mother_tongue_practice_reported": False,
                "practice_evidence_excerpt": "",
            }
        )

    monkeypatch.setattr(module, "call_agent", _empty)


async def _a_room_opening_a_passage(client: httpx.AsyncClient) -> str:
    created = await client.post(
        f"{PREFIX}/sessions", headers={"X-Room-Key": KEY}, json={"pericope": P}
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


async def test_a_guide_that_cannot_be_reached_answers_the_room_not_the_tablet(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A timeout on the Guide is a bad minute, not a broken room.

    The tablet reads a 500 as the room itself failing and the session stops for a person,
    over an outage that was over before anyone reached the door.
    """
    _the_models_answer(monkeypatch, RuntimeError("the model is unreachable"))
    session_id = await _a_room_opening_a_passage(client)

    answered = await _the_room_takes_a_turn(client, session_id)

    assert answered.status_code == 200, answered.text[:300]
    assert answered.json()["fixed_line"] in _unrepairable_lines()


async def test_a_validator_that_cannot_be_reached_degrades_the_same_turn(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two call sites, one turn: covering the Guide and leaving the Validator is half a fix."""
    _the_models_answer(monkeypatch, GUIDE_LINE, RuntimeError("the validator is unreachable"))
    session_id = await _a_room_opening_a_passage(client)

    answered = await _the_room_takes_a_turn(client, session_id)

    assert answered.status_code == 200, answered.text[:300]
    assert answered.json()["fixed_line"] in _unrepairable_lines()


async def test_a_validator_listing_its_issues_as_plain_strings_still_gets_a_second_draft(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`issues` comes from a model, so its rows are whatever the model wrote.

    A rejection whose reasons arrive as bare strings still has to reach the Guide as a
    redraft note. Losing the whole turn over the shape of that list spends a fail-safe on
    a draft the room could simply have asked for again.
    """
    _the_models_answer(
        monkeypatch,
        GUIDE_LINE,
        json.dumps({"verdict": "regenerate", "issues": ["longo demais", "fora do mapa"]}),
        CORRECTED_LINE,
        _passes(),
    )
    session_id = await _a_room_opening_a_passage(client)

    answered = await _the_room_takes_a_turn(client, session_id)

    body = answered.json()
    assert answered.status_code == 200, answered.text[:300]
    assert not body["used_fail_safe"], (
        "a segunda tentativa passou; a sala não precisa de linha enlatada"
    )
    assert body["fixed_line"] == ""


async def test_a_turn_the_models_answer_is_spoken_as_the_guide_wrote_it(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch, spoken: list[str]
) -> None:
    """The counterweight: a working turn must not be swallowed into a fail-safe.

    A blanket rescue around the generative path turns every turn into a canned line without
    saying so, and a room that answers everything with the same sentence is worse than a
    500 — the 500 at least shows up.
    """
    _the_models_answer(monkeypatch, GUIDE_LINE, _passes())
    session_id = await _a_room_opening_a_passage(client)

    answered = await _the_room_takes_a_turn(client, session_id)

    body = answered.json()
    assert answered.status_code == 200, answered.text[:300]
    assert not body["used_fail_safe"]
    assert body["fixed_line"] == ""
    assert spoken == [GUIDE_LINE]


async def test_a_failed_call_is_logged_without_repeating_what_the_team_said(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """An outage the operation cannot see is the one it cannot fix.

    The team's words are not part of what it needs to see: the room degrading is an
    infrastructure fact, and a transcript in an operations log is the team's speech kept
    somewhere nobody agreed to.
    """
    _the_assessor_finds_nothing(monkeypatch)
    _the_models_answer(monkeypatch, GUIDE_LINE, _passes(), RuntimeError("the model is gone"))
    session_id = await _a_room_opening_a_passage(client)
    await _the_room_takes_a_turn(client, session_id)

    with caplog.at_level(logging.ERROR, logger="app.services.internalization_room.run_turn"):
        answered = await _the_team_answers(client, session_id)

    assert answered.status_code == 200, answered.text[:300]
    failures = [
        record
        for record in caplog.records
        if record.name == "app.services.internalization_room.run_turn" and record.exc_info
    ]
    assert failures, "uma falha do modelo tem de deixar rastro com o traceback"
    assert TEAM_ANSWER not in caplog.text


async def test_a_bug_in_the_rooms_own_checks_is_not_dressed_up_as_an_outage(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The rescue is for the model, not for us.

    Both models answered here; what broke is one of the room's own checks over the reply.
    Answering that with an outage line spends the team's turn hiding a defect, and leaves
    it in a log nobody is watching instead of where someone would see it.
    """
    _the_models_answer(monkeypatch, GUIDE_LINE, _passes())
    module = sys.modules["app.services.internalization_room.run_turn"]

    def _explodes(*_args: Any, **_kwargs: Any) -> bool:
        raise AssertionError("a defect in the room's own bridge-language check")

    monkeypatch.setattr(module, "strays_from", _explodes)
    session_id = await _a_room_opening_a_passage(client)

    answered = await _the_room_takes_a_turn(client, session_id)

    assert answered.status_code == 500, (
        "um defeito nosso tem de continuar aparecendo, não virar linha de fail-safe"
    )


async def test_a_cancelled_turn_is_never_dressed_up_as_a_fail_safe(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Shutdown is not an outage. A cancelled turn has no team left to answer.

    Catching it would make a stopping server look to the room like a model that failed, and
    would keep the turn running past the point the runtime asked it to stop.
    """
    _the_models_answer(monkeypatch, asyncio.CancelledError())
    session_id = await _a_room_opening_a_passage(client)

    with pytest.raises(asyncio.CancelledError):
        await _the_room_takes_a_turn(client, session_id)
