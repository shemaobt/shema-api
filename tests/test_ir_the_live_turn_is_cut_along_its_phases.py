"""The comprehension turn is a sequencer over `turn/`, and every phase answers on its own."""

from __future__ import annotations

import json
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.internalization_room import live_turn
from app.services.internalization_room.canon.parse_map import load_map
from app.services.internalization_room.sessions import append_exchange, create_session
from app.services.internalization_room.turn import scene_view
from app.services.internalization_room.turn.speech import speak_back
from tests.turn_harness import GUIDE, VALIDATOR, P, settings, the_agent_answers

INAUDIBLE_LINES = [
    "Desculpa, não consegui ouvir direito — podem repetir?",
    "Essa me escapou. Podem dizer de novo?",
    "O som não chegou bem — podem falar mais uma vez?",
]


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
    }
    return await speak_back(**{**given, **overrides})


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


async def test_misses_in_a_row_all_draw_the_first_d_line_never_the_second_or_third(
    db_session: AsyncSession, agent: RecordingAgent
) -> None:
    session = await create_session(db_session, language="pt", pericope=P)
    session = await _missed(db_session, session, times=4)

    spoken = [m["fixed_line"] for m in session.messages if m.get("role") == "guide"]

    assert spoken == ["D0", "D0", "D0", "D0"], (
        "a escada rodava com o tamanho da conversa: dois turnos por erro, então a segunda "
        "falha pulava para D2 e a quarta voltava para D0; agora nada conta, e toda falta "
        "pede a mesma primeira linha"
    )


async def test_everything_else_reaches_the_guide_with_the_ledger_in_hand(
    db_session: AsyncSession, agent: RecordingAgent
) -> None:
    session = await create_session(db_session, language="pt", pericope=P)

    outcome = await _speak(session)

    assert outcome.speech == "A fome chegou a Belém."
    assert outcome.used_fail_safe is False
    assert "WORKED WITH BY THE TEAM (engaged):" in agent.systems[0]
