from __future__ import annotations

import json
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.models.internalization_room import IRPromptKey
from app.services.internalization_room._default_prompts import default_prompt
from app.services.internalization_room.canon.book_material import build_book_material
from app.services.internalization_room.hearing import HeardSpeech
from app.services.internalization_room.live_turn import run_comprehension_turn
from app.services.internalization_room.panorama_turn import run_panorama_turn
from app.services.internalization_room.sessions import create_session
from tests.turn_harness import the_room_agent_is

GUIDE = default_prompt(IRPromptKey.GUIDE)["prompt"]
VALIDATOR = default_prompt(IRPromptKey.VALIDATOR)["prompt"]
PANORAMA = default_prompt(IRPromptKey.BOOK_PANORAMA)["prompt"]
P = "P03"


def _settings() -> Settings:
    return Settings(database_url="sqlite+aiosqlite:///./test.db", google_api_key="fake")


class ListeningAgent:
    """Hears what each role is handed, drafts one line and passes it."""

    def __init__(
        self,
        draft: str = "Vamos começar pela Familiarização. Primeiro eu conto a passagem inteira.",
    ) -> None:
        self.draft = draft
        self.guide_turns: list[str] = []
        self.validator_systems: list[str] = []

    async def __call__(self, *, system_prompt: str, user_content: str, **kwargs: Any) -> str:
        if "corrected_response" in system_prompt:
            self.validator_systems.append(system_prompt)
            return json.dumps({"verdict": "pass", "issues": []})
        self.guide_turns.append(user_content)
        return self.draft


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


async def test_an_english_passage_opens_on_her_english_note(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    agent = ListeningAgent(
        "Let's begin with Familiarization. First I will tell you the whole passage."
    )
    the_room_agent_is(monkeypatch, turn=agent)
    session = await create_session(db_session, language="en", pericope=P)

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
        "[The session has just begun. The team opened passage P03 and is at the table, "
        "ready to begin. Speak first.]"
    ], "uma sessão em inglês ouvia a nota em português"


async def test_a_portuguese_panorama_opens_on_her_panorama_note(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    agent = ListeningAgent()
    the_room_agent_is(monkeypatch, turn=agent)

    await run_panorama_turn(
        transcript="",
        messages=[],
        panorama_prompt=PANORAMA,
        validator_prompt=VALIDATOR,
        book="Ruth",
        book_material=build_book_material("Ruth"),
        session_language="Brazilian Portuguese",
        language_code="pt",
        opening=True,
        settings=_settings(),
    )

    assert agent.guide_turns == [
        "[A sessão acabou de começar. A equipe abriu o Panorama do Livro de Ruth e está à "
        "mesa, pronta para conversar. Fale primeiro.]"
    ], "o Panorama abria com o roteiro da passagem, falando de partes e de ensaio"


async def test_an_english_panorama_opens_on_her_english_panorama_note(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    agent = ListeningAgent("Hello, I am the Digital Facilitator.")
    the_room_agent_is(monkeypatch, turn=agent)

    await run_panorama_turn(
        transcript="",
        messages=[],
        panorama_prompt=PANORAMA,
        validator_prompt=VALIDATOR,
        book="Ruth",
        book_material=build_book_material("Ruth"),
        session_language="English",
        language_code="en",
        opening=True,
        settings=_settings(),
    )

    assert agent.guide_turns == [
        "[The session has just begun. The team opened the Book Panorama of Ruth and is at the "
        "table, ready to talk. Speak first.]"
    ], "um Panorama em inglês ouvia a nota em português"
