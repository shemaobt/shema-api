"""The demolition guard for the Assessor and the probe machinery around it.

A team said *"é difícil explicar tudo isso em português"* and the room answered with a line
about the microphone. The Assessor classified the turn, the planner picked the next station,
and the Guide was handed a contract that left it nothing to do but the scripted micro-check —
so a problem about language was answered as a problem about sound. The ruling is that the
machinery which produces that should not exist.

These tests do not describe behaviour that was built. They describe absence, and they are
the only thing standing between the absence and someone rebuilding it a piece at a time:
no module of it can be imported, no field of a session remembers it, no purpose is left to
hand the Guide, no block of it reaches either model, and no count of failed calls can end
an interview. Named symbol by symbol rather than matched by prefix, the way the retired
acousteme surface is named: the package around them is alive, and a prefix guard here would
be widened until it meant nothing.
"""

import importlib
import json
import sys
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.models.internalization_room import IRPromptKey, IRSession
from app.services.internalization_room._default_prompts import default_prompt
from app.services.internalization_room.comprehension.probe import ProbePurpose
from app.services.internalization_room.comprehension.state import ComprehensionState
from app.services.internalization_room.fail_safe import FailSafe, utterances
from app.services.internalization_room.hearing import HeardSpeech
from app.services.internalization_room.live_turn import ComprehensionTurn, run_comprehension_turn
from app.services.internalization_room.sessions import (
    append_exchange,
    create_session,
    save_comprehension,
    set_bridge_mode,
)

GUIDE = default_prompt(IRPromptKey.GUIDE)["prompt"]
VALIDATOR = default_prompt(IRPromptKey.VALIDATOR)["prompt"]
GUIDE_LINE = "Vamos ficar nesta cena. O que vocês contariam?"
P = "P03"

RETIRED_MODULES = (
    "app.services.internalization_room.comprehension.assessor",
    "app.services.internalization_room.comprehension.probe_plan",
    "app.services.internalization_room.comprehension.question_contract",
    "app.services.internalization_room.comprehension.stt_recovery",
    "app.services.internalization_room.comprehension.no_report",
)


def test_no_module_of_the_probe_machinery_can_be_imported() -> None:
    alive = []
    for name in RETIRED_MODULES:
        try:
            importlib.import_module(name)
        except ModuleNotFoundError:
            continue
        alive.append(name)

    assert not alive, f"the probe machinery is back: {alive}"


def test_no_field_of_the_session_remembers_the_probe_machinery() -> None:
    retired = {
        "assessor_failures",
        "stt_recovery",
        "no_report_attempts",
        "adaptive_free_retell_attempted",
    }

    assert not retired & set(ComprehensionState.model_fields)


def test_the_one_purpose_left_is_the_recording_handoff_consent() -> None:
    """The purposes were the contract: each one told the Guide what it could and could not
    say next. The consent question is the app's own fixed sentence and the only reason a
    probe is still raised at all."""
    assert [purpose.value for purpose in ProbePurpose] == ["recording_handoff_consent"]


PROBE_BLOCK_MARKS = (
    "ACTIVE COMPREHENSION PROBE",
    "EVIDENCE METHOD:",
    "QUESTION SHAPE",
    "PROCESS DECISION:",
)


def _settings() -> Settings:
    return Settings(database_url="sqlite+aiosqlite:///./test.db", google_api_key="fake")


async def _a_room_that_has_asked_something(db: AsyncSession) -> IRSession:
    session = await create_session(db, language="pt", pericope=P, bridge_mode="guided_microchecks")
    return await append_exchange(
        db, session, team_utterance="", guide_response="Quem aparece nesta parte?"
    )


async def _the_team_answers(
    db: AsyncSession, session: IRSession, text: str
) -> tuple[ComprehensionTurn, IRSession]:
    """One whole turn as the endpoint runs it, so what one turn leaves the next one reads."""
    turn = await run_comprehension_turn(
        db,
        session,
        speech=HeardSpeech(text=text),
        opening=False,
        guide_prompt=GUIDE,
        validator_prompt=VALIDATOR,
        settings=_settings(),
    )
    session = await set_bridge_mode(db, session, turn.bridge_mode)
    session = await save_comprehension(db, session, turn.state)
    session = await append_exchange(
        db, session, team_utterance=turn.outcome.transcript, guide_response=turn.outcome.speech
    )
    return turn, session


class _RecordingModels:
    """A Guide and a Validator that keep everything they were handed, prompt and message.

    Both halves matter: the contract rode into the Guide inside the coverage-status slot of
    the user message and into the Validator appended to its system prompt, so a guard that
    read only one of the two would stay green with the block still reaching the other.
    """

    def __init__(self) -> None:
        self.guide: list[str] = []
        self.validator: list[str] = []

    async def __call__(self, *, system_prompt: str, user_content: str, **kwargs: Any) -> str:
        if "corrected_response" in system_prompt:
            self.validator.append(f"{system_prompt}\n\n{user_content}")
            return json.dumps({"verdict": "pass", "issues": []})
        self.guide.append(f"{system_prompt}\n\n{user_content}")
        return GUIDE_LINE


def _marks_the_app_added(handed: list[str], written: str) -> list[str]:
    """The marks a call carries beyond the ones the written prompt already names.

    Both prompt documents still describe the contract in prose, and a prompt is reviewed by
    the person who writes it rather than by a grep — what this asks is only that the app
    stops appending the block itself.
    """
    return [
        mark
        for mark in PROBE_BLOCK_MARKS
        if any(one.count(mark) > written.count(mark) for one in handed)
    ]


@pytest.mark.asyncio
async def test_no_probe_block_reaches_the_guide_or_the_validator(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The block is what answered a language problem with a microphone line: holding a
    contract that authorized only the scripted micro-check, the Guide had nothing else it
    was allowed to do with what the team had just said.

    A turn with no probe standing is the one that shows it plainest — the block was written
    even then, and its four lines were pure instruction: invent no other semantic test,
    authorize exactly one move, follow the app-owned instruction only.
    """
    models = _RecordingModels()
    monkeypatch.setattr(
        sys.modules["app.services.internalization_room.run_turn"], "call_agent", models
    )
    session = await _a_room_that_has_asked_something(db_session)

    await _the_team_answers(db_session, session, text="é difícil explicar isso em português")

    assert models.guide and models.validator
    to_the_guide = _marks_the_app_added(models.guide, GUIDE)
    to_the_validator = _marks_the_app_added(models.validator, VALIDATOR)

    assert not to_the_guide, f"a probe block is still handed to the Guide: {to_the_guide}"
    assert not to_the_validator, f"and to the Validator: {to_the_validator}"


class _BrokenModels:
    """Every model call this room places goes nowhere."""

    async def __call__(self, **kwargs: Any) -> str:
        raise RuntimeError("the model transport is down")


@pytest.mark.asyncio
async def test_a_room_whose_model_keeps_failing_is_never_stopped_for_a_person(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A component that no longer exists cannot decide a session is over.

    The failures the ladder counted were the Assessor's own, and three in a row ended the
    interview and called somebody. What still asks for a person lives outside the turn —
    the tablet asking, the retelling ceiling, the back-translation ceiling, the device
    halt — and none of it counts model calls.
    """
    monkeypatch.setattr(
        sys.modules["app.services.internalization_room.run_turn"], "call_agent", _BrokenModels()
    )
    session = await _a_room_that_has_asked_something(db_session)

    spoken = []
    for _ in range(6):
        turn, session = await _the_team_answers(db_session, session, text="Noemi voltou a Belém")
        spoken.append(turn.outcome.speech)
        assert not turn.outcome.needs_person

    hard_stop = utterances(FailSafe.HARD_STOP, "pt")
    assert not any(line in hard_stop for line in spoken)
