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
from app.services.internalization_room.sessions import append_exchange, create_session
from app.services.internalization_room.turn import scene_view
from app.services.internalization_room.turn.context import render_context
from app.services.internalization_room.turn.speech import speak_back
from tests.turn_harness import GUIDE, VALIDATOR, P, settings, the_agent_answers

OFF_BRIDGE_LINE = (
    "Que bom — vocês experimentaram na língua de vocês. Eu não consigo conferir essas "
    "palavras diretamente. Agora, alguém pode me contar em português o que vocês disseram?"
)
INAUDIBLE_LINES = [
    "Desculpa, não consegui ouvir direito — podem repetir?",
    "Essa me escapou. Podem dizer de novo?",
    "O som não chegou bem — podem falar mais uma vez?",
]
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


def test_the_invitation_is_about_the_scene_being_opened_or_else_the_first_still_owed() -> None:
    """While a scene is being opened the pointer names it; with the necklace full, the first
    scene not yet reported is what an invitation can be about; with every scene reported,
    nothing is."""
    scenes = scene_ids_for(P)
    assert scene_view.scene_the_invitation_is_about("S2", P, []) == "S2"
    assert scene_view.scene_the_invitation_is_about(None, P, ["S1"]) == "S2"
    assert scene_view.scene_the_invitation_is_about(None, P, scenes[:1] + scenes[2:]) == "S2"
    assert scene_view.scene_the_invitation_is_about(None, P, scenes) is None


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


async def test_speech_in_the_teams_own_language_meets_the_g_line_without_waking_a_model(
    db_session: AsyncSession, agent: RecordingAgent
) -> None:
    session = await create_session(db_session, language="pt", pericope=P)

    outcome = await _speak(
        session, mother_tongue=True, transcript="koeti yoko vitukeovo enepone itukovo"
    )

    assert outcome.speech == OFF_BRIDGE_LINE
    assert outcome.fixed_line == "G0"
    assert outcome.used_fail_safe is True
    assert outcome.degraded is False
    assert agent.calls == 0


async def _missed(db: AsyncSession, session: Any, *, times: int) -> Any:
    """That many turns the room could not hear, each written down the way the route does."""
    for _ in range(times):
        outcome = await _speak(
            session, uncertain=True, transcript="mmm ne", messages=list(session.messages or [])
        )
        session = await append_exchange(
            db,
            session,
            team_utterance=outcome.transcript,
            guide_response=outcome.speech,
            outcome=outcome,
        )
    return session


async def test_the_first_miss_after_a_heard_conversation_draws_the_first_d_line(
    db_session: AsyncSession, agent: RecordingAgent
) -> None:
    """Four exchanges the room heard used to put the first miss on the second line."""
    session = await create_session(db_session, language="pt", pericope=P)
    four_exchanges = [{"role": "guide", "text": "…", "outcome": "pass"}] * 4

    outcome = await _speak(session, uncertain=True, transcript="mmm ne", messages=four_exchanges)

    assert outcome.speech == INAUDIBLE_LINES[0]
    assert outcome.fixed_line == "D0"
    assert outcome.degraded is True
    assert agent.calls == 0


async def test_misses_in_a_row_walk_the_three_d_lines_in_order_and_stay_on_the_third(
    db_session: AsyncSession, agent: RecordingAgent
) -> None:
    session = await create_session(db_session, language="pt", pericope=P)
    session = await _missed(db_session, session, times=4)

    spoken = [m["fixed_line"] for m in session.messages if m.get("role") == "guide"]

    assert spoken == ["D0", "D1", "D2", "D2"], (
        "a escada rodava com o tamanho da conversa: dois turnos por erro, então a segunda "
        "falha pulava para D2 e a quarta voltava para D0"
    )


async def test_a_turn_the_room_heard_starts_the_d_ladder_over(
    db_session: AsyncSession, agent: RecordingAgent
) -> None:
    session = await create_session(db_session, language="pt", pericope=P)
    session = await _missed(db_session, session, times=2)
    heard = await _speak(session, messages=list(session.messages))
    session = await append_exchange(
        db_session,
        session,
        team_utterance=heard.transcript,
        guide_response=heard.speech,
        outcome=heard,
    )

    outcome = await _speak(
        session, uncertain=True, transcript="mmm ne", messages=list(session.messages)
    )

    assert heard.used_fail_safe is False
    assert outcome.fixed_line == "D0"
    assert outcome.speech == INAUDIBLE_LINES[0]


async def test_everything_else_reaches_the_guide_with_the_status_block_in_hand(
    db_session: AsyncSession, agent: RecordingAgent
) -> None:
    session = await create_session(db_session, language="pt", pericope=P)

    outcome = await _speak(session)

    assert outcome.speech == "A fome chegou a Belém."
    assert outcome.used_fail_safe is False
    assert STATUS_BLOCK in agent.systems[0]
