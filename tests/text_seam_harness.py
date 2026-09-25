"""The two doors of the **Text seam**, and the models standing behind them.

Her golden runners play a script against a running server through the seam, and the cases
about what the runner exports stand in front of the very same doors as the cases about the
seam itself. What both need is the app with the seam open and a model that answers what the
case set, so it lives here rather than in whichever case file happened to write it first.

Fixtures are not exported, for the reason `room_harness` gives: what travels is the builder,
and each module keeps the three-line fixture that calls it.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.internalization_room import router
from app.core.database import get_db
from app.core.exceptions import register_exception_handlers
from app.services.internalization_room import golden_judge
from tests.room_harness import CORRECTION_MARK
from tests.turn_harness import the_room_agent_is

RUNNER_KEY = "runner-de-teste"

GUIDE_LINE = "Olá, eu sou o Facilitador Digital. Vamos começar pelo todo."
TEAM_LINE = "Bom dia. Somos a equipe Terena. Pode continuar."

THE_EXTRA_CAUSE = (
    "A tradução diz que Noemi decidiu voltar porque as noras pediram; a história conta apenas "
    "que ela ouviu a notícia do pão."
)
THE_VOICE = (
    "Vocês traduziram bem quase tudo. Na frase 1 vocês disseram que as noras pediram. Isso "
    "está no áudio de vocês, ou entrou agora na tradução?"
)


class ScriptedAgent:
    """The Guide and the Validator answering as a case's script says, one entry per call."""

    def __init__(self, script: list[Any]) -> None:
        self._script = list(script)
        self.guide_inputs: list[str] = []

    async def __call__(self, *, system_prompt: str, user_content: str, **kwargs: Any) -> str:
        validating = "corrected_response" in system_prompt
        if not validating:
            self.guide_inputs.append(user_content)
        planned = self._script.pop(0) if self._script else None
        if planned is not None:
            return planned
        if validating:
            return json.dumps({"verdict": "pass", "issues": []})
        return GUIDE_LINE


def the_models_answer(monkeypatch: pytest.MonkeyPatch, *script: Any) -> ScriptedAgent:
    agent = ScriptedAgent(list(script))
    the_room_agent_is(monkeypatch, turn=agent)
    return agent


class Analyst:
    """The analyst in its two modes, each answering what the case set.

    The whole reading answers the next entry of `readings`; the correction check answers
    `resolves` and whatever `broke` carries. The two are told apart by the heading only the
    correction prompt has, the way a reader would — not by counting calls.
    """

    def __init__(self) -> None:
        self.readings: list[dict[str, Any]] = []
        self.verifications: list[str] = []
        self.answered: list[str] = []
        self.resolves = True
        self.broke: list[dict[str, str]] = []

    async def __call__(self, *, system_prompt: str, user_content: str, **_: Any) -> str:
        if CORRECTION_MARK in system_prompt:
            self.verifications.append(system_prompt)
            return json.dumps({"resolved": self.resolves, "findings": self.broke})
        reply = json.dumps(self.readings.pop(0) if self.readings else {"findings": []})
        self.answered.append(reply)
        return reply


class Speaker:
    """The verdict Speaker and the Validator behind it, saying what the case set."""

    def __init__(self) -> None:
        self.line = THE_VOICE

    async def __call__(self, *, system_prompt: str, **_: Any) -> str:
        if "corrected_response" in system_prompt:
            return json.dumps({"verdict": "pass", "issues": []})
        return self.line


def the_analyst_reads(monkeypatch: pytest.MonkeyPatch) -> Analyst:
    from app.services.internalization_room import back_translation as bt_service

    reader = Analyst()
    monkeypatch.setattr(bt_service, "call_agent", reader)
    return reader


def the_speaker_says(monkeypatch: pytest.MonkeyPatch) -> Speaker:

    voice = Speaker()
    the_room_agent_is(monkeypatch, turn=voice)
    return voice


A_VERDICT: dict[str, Any] = {
    "scores": {
        "understands_team": 3,
        "answers_requests_to_understand": 1,
        "frames_before_eliciting": 3,
        "rehearsal_and_honest_checking": 3,
        "silences_as_content": 4,
        "containment": 4,
        "register": 3,
        "adaptivity": 2,
    },
    "incidents": [
        {
            "turn": 1,
            "severity": "blocker",
            "kind": "redirect_on_request_to_understand",
            "quote": "Vamos ficar dentro da passagem.",
            "why": "A equipe pediu para entender e o guia redirecionou.",
        }
    ],
    "pass": False,
    "summary": "O guia redirecionou um pedido de entender.",
}


class Judge:
    """The model behind the judge, answering what the case set and keeping what it was asked."""

    def __init__(self, reply: str = json.dumps(A_VERDICT)) -> None:
        self.reply = reply
        self.asked: list[dict[str, Any]] = []

    async def __call__(self, **kwargs: Any) -> str:
        self.asked.append(kwargs)
        return self.reply


def the_judge_answers(monkeypatch: pytest.MonkeyPatch, reply: str = json.dumps(A_VERDICT)) -> Judge:
    judge = Judge(reply)
    monkeypatch.setattr(golden_judge, "call_agent", judge)
    return judge


def the_app(db_session: AsyncSession):
    from fastapi import FastAPI

    test_app = FastAPI()
    test_app.include_router(router, prefix="/api/internalization-room")
    register_exception_handlers(test_app)

    async def _get_db():
        yield db_session

    test_app.dependency_overrides[get_db] = _get_db
    return test_app
