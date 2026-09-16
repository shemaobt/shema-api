"""The comprehension turn is a sequencer over `turn/`, and every phase answers on its own."""

from __future__ import annotations

import dataclasses
import json
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.internalization_room import live_turn
from app.services.internalization_room.canon.parse_map import load_map
from app.services.internalization_room.comprehension.checkpoints import (
    checkpoints_for,
    scene_ids_for,
)
from app.services.internalization_room.comprehension.state import ComprehensionState
from app.services.internalization_room.sessions import create_session
from app.services.internalization_room.turn import scene_view
from app.services.internalization_room.turn.context import render_context
from app.services.internalization_room.turn.speech import speak_back
from tests.turn_harness import GUIDE, VALIDATOR, P, settings, the_agent_answers

SECOND_INAUDIBLE_LINE = "Essa me escapou. Podem dizer de novo?"
STATUS_BLOCK = "BLOCO DE TESTE: o que a sala sabe"


class RecordingAgent:
    """Speaks one draft, passes it, and keeps every system prompt it was handed."""

    def __init__(self, draft: str):
        self.draft = draft
        self.systems: list[str] = []
        self.calls = 0

    async def __call__(self, *, system_prompt: str, user_content: str, **kwargs: Any) -> str:
        self.calls += 1
        self.systems.append(system_prompt)
        if "corrected_response" in system_prompt:
            return json.dumps({"verdict": "pass", "issues": []})
        return self.draft


@pytest.fixture
def agent(monkeypatch: pytest.MonkeyPatch) -> RecordingAgent:
    return the_agent_answers(monkeypatch, RecordingAgent("A fome chegou a Belém."))  # type: ignore[arg-type]


def test_the_scene_pointer_lives_in_its_own_module_and_live_turn_still_names_it() -> None:
    assert live_turn.current_scene_id is scene_view.current_scene_id
    assert "current_scene_id" in live_turn.__all__


def test_the_context_phase_hands_the_models_the_status_block_and_nothing_can_rewrite_it() -> None:
    checkpoints = list(checkpoints_for(P, load_map(P).book))
    context = render_context(
        checkpoints=checkpoints,
        scene_ids=scene_ids_for(P),
        state=ComprehensionState(),
        projected_practice=["S1"],
        scene_pointer="S2",
    )

    assert context.app_context.startswith("COMPREHENSION EVIDENCE (APP-OWNED;")
    assert "MOTHER-TONGUE PRACTICE REPORTED: S1" in context.app_context.splitlines()
    with pytest.raises(dataclasses.FrozenInstanceError):
        context.app_context = ""  # type: ignore[misc]


async def _speak(session: Any, **overrides: Any) -> Any:
    given: dict[str, Any] = {
        "mother_tongue": False,
        "take_ms": None,
        "session": session,
        "messages": [],
        "transcript": "a fome chegou",
        "opening": False,
        "empty": False,
        "uncertain": False,
        "book": load_map(P).book,
        "guide_prompt": GUIDE,
        "validator_prompt": VALIDATOR,
        "pericope": P,
        "settings": settings(),
        "app_context": STATUS_BLOCK,
    }
    return await speak_back(**{**given, **overrides})


async def test_speech_the_room_could_not_hear_draws_the_d_line_the_turn_count_points_at(
    db_session: AsyncSession, agent: RecordingAgent
) -> None:
    session = await create_session(db_session, language="pt", pericope=P)
    four_exchanges = [{"role": "guide", "text": "…"}] * 4

    outcome = await _speak(session, uncertain=True, transcript="mmm ne", messages=four_exchanges)

    assert outcome.speech == SECOND_INAUDIBLE_LINE
    assert outcome.fixed_line == "D1"
    assert outcome.degraded is True
    assert agent.calls == 0


async def test_everything_else_reaches_the_guide_with_the_status_block_in_hand(
    db_session: AsyncSession, agent: RecordingAgent
) -> None:
    session = await create_session(db_session, language="pt", pericope=P)

    outcome = await _speak(session)

    assert outcome.speech == "A fome chegou a Belém."
    assert outcome.used_fail_safe is False
    assert STATUS_BLOCK in agent.systems[0]
