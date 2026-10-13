import json
from typing import Any

import pytest

from app.core.config import Settings
from app.db.models.internalization_room import IRPromptKey
from app.services.internalization_room._default_prompts import default_prompt
from app.services.internalization_room.canon.book_material import build_book_material
from app.services.internalization_room.hearing import HeardSpeech
from app.services.internalization_room.run_turn import run_panorama_turn
from tests.turn_harness import the_room_agent_is

LEDGER_AND_ROOM_FACTS = (
    "LEDGER (",
    "WORKED WITH BY THE TEAM",
    "RAISED BY YOU",
    "NOT YET TOUCHED",
    "SCENE REHEARSALS:",
    "KEPT REHEARSALS:",
    "EARLIER PASSAGES FOR THIS TEAM:",
    "MOMENT:",
    "ACCEPTED READINGS FOR THE SCENE",
)


class _Recording:
    def __init__(self) -> None:
        self.guide: list[str] = []

    async def __call__(self, *, system_prompt: str, user_content: str, **kwargs: Any) -> str:
        if "corrected_response" in system_prompt:
            return json.dumps({"verdict": "pass", "issues": []})
        self.guide.append(system_prompt)
        return "Vamos conhecer o livro."


@pytest.fixture
def recording(monkeypatch: pytest.MonkeyPatch) -> _Recording:
    models = _Recording()
    the_room_agent_is(monkeypatch, turn=models)
    return models


async def _turn(*, words: str, opening: bool) -> None:
    await run_panorama_turn(
        session_language="Portuguese",
        language_code="pt",
        speech=HeardSpeech(text=words),
        messages=[],
        panorama_prompt=default_prompt(IRPromptKey.BOOK_PANORAMA)["prompt"],
        validator_prompt=default_prompt(IRPromptKey.VALIDATOR)["prompt"],
        book="Ruth",
        book_material=build_book_material("Ruth"),
        opening=opening,
        settings=Settings(database_url="sqlite+aiosqlite:///./test.db", google_api_key="fake"),
    )


async def test_a_panorama_guide_reads_the_book_and_never_a_ledger_or_a_room_fact(
    recording: _Recording,
) -> None:
    await _turn(words="", opening=True)
    await _turn(words="o que é esse livro?", opening=False)

    assert len(recording.guide) == 2, "a panorama não chamou o Guia nos dois turnos"
    for system in recording.guide:
        assert "THE BOOK OF RUTH" in system, "o Guia da panorama não lia o material do livro"
        assert [marker for marker in LEDGER_AND_ROOM_FACTS if marker in system] == [], (
            "a panorama entregava ao Guia o ledger ou um fato da sala, que ela não tem"
        )
