from __future__ import annotations

import json
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.models.internalization_room import IRPromptKey
from app.services.internalization_room._default_prompts import default_prompt
from app.services.internalization_room.hearing import HeardSpeech
from app.services.internalization_room.live_turn import run_comprehension_turn
from app.services.internalization_room.sessions import create_session
from tests.turn_harness import the_room_agent_is

GUIDE = default_prompt(IRPromptKey.GUIDE)["prompt"]
VALIDATOR = default_prompt(IRPromptKey.VALIDATOR)["prompt"]
P = "P03"


def _settings() -> Settings:
    return Settings(database_url="sqlite+aiosqlite:///./test.db", google_api_key="fake")


class ListeningAgent:
    """Hears what each role is handed, drafts one line and passes it."""

    def __init__(self) -> None:
        self.guide_turns: list[str] = []
        self.validator_systems: list[str] = []

    async def __call__(self, *, system_prompt: str, user_content: str, **kwargs: Any) -> str:
        if "corrected_response" in system_prompt:
            self.validator_systems.append(system_prompt)
            return json.dumps({"verdict": "pass", "issues": []})
        self.guide_turns.append(user_content)
        return "Vamos começar pela Familiarização. Primeiro eu conto a passagem inteira."


async def test_a_portuguese_passage_opens_on_her_note_and_nothing_of_ours(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    agent = ListeningAgent()
    the_room_agent_is(monkeypatch, turn=agent)
    session = await create_session(db_session, language="pt", pericope=P)

    await run_comprehension_turn(
        db_session,
        session,
        speech=HeardSpeech(),
        opening=True,
        guide_prompt=GUIDE,
        validator_prompt=VALIDATOR,
        settings=_settings(),
    )

    assert agent.guide_turns == [
        "[A sessão acabou de começar. A equipe abriu a passagem P03 e está à mesa, "
        "pronta para começar. Fale primeiro.]"
    ], "o Guide abria com o nosso roteiro em inglês, pedindo que abrisse a primeira cena"
