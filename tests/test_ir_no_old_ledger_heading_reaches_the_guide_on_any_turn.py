import json
from typing import Any

import pytest

from app.core.config import Settings
from app.db.models.internalization_room import IRPromptKey
from app.services.internalization_room._default_prompts import default_prompt
from app.services.internalization_room.coverage import initial_state
from app.services.internalization_room.run_turn import run_turn
from tests.turn_harness import the_room_agent_is

P = "P01"
HEADER = "LEDGER (the app's notes — information only; you decide what comes next)"
OUR_OLD_HEADINGS = ("COVERED", "REMAINING", "FIRST SCENE WHOSE BEADS ARE NOT ALL CLOSED")


class _Recording:
    def __init__(self) -> None:
        self.guide: list[str] = []

    async def __call__(self, *, system_prompt: str, user_content: str, **kwargs: Any) -> str:
        if "corrected_response" in system_prompt:
            return json.dumps({"verdict": "pass", "issues": []})
        self.guide.append(system_prompt)
        return "Vamos ouvir a passagem."


@pytest.fixture
def recording(monkeypatch: pytest.MonkeyPatch) -> _Recording:
    models = _Recording()
    the_room_agent_is(monkeypatch, turn=models)
    return models


async def _turn(*, transcript: str, opening: bool) -> None:
    await run_turn(
        transcript=transcript,
        coverage_state=initial_state(P),
        messages=[],
        guide_prompt=default_prompt(IRPromptKey.GUIDE)["prompt"],
        validator_prompt=default_prompt(IRPromptKey.VALIDATOR)["prompt"],
        pericope_num=P,
        language_code="pt",
        opening=opening,
        settings=Settings(database_url="sqlite+aiosqlite:///./test.db", google_api_key="fake"),
    )


async def test_the_opening_and_an_ordinary_turn_read_her_header_once_and_none_of_our_old_headings(
    recording: _Recording,
) -> None:
    await _turn(transcript="", opening=True)
    await _turn(transcript="a fome veio e eles foram para Moabe", opening=False)

    opening, ordinary = recording.guide
    for system in (opening, ordinary):
        assert system.count(HEADER) == 1, "o Guia não lia o cabeçalho dela, uma vez só"
        assert [word for word in OUR_OLD_HEADINGS if word in system] == [], (
            "o ledger chegava ao Guia como lista de tarefas, com COVERED e REMAINING"
        )
