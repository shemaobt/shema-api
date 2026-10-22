import json
from typing import Any

import pytest

from app.core.config import Settings
from app.db.models.internalization_room import IRPromptKey
from app.services.internalization_room.coverage import initial_state
from app.services.internalization_room.prompts import get_prompt_text
from app.services.internalization_room.run_turn import run_turn
from tests.turn_harness import the_room_agent_is

HER_NOTES = (
    "# System Prompt — Meaning Map Internalization Guide",
    "> **What this is.** The system prompt for an oral, conversational bot",
    "> **How to use it.** Everything between the",
    "> Voice formatting rule — Marcia's ruling 2026-09-09 (pilot day 1)",
)


class _Recording:
    def __init__(self) -> None:
        self.guide: list[str] = []

    async def __call__(self, *, system_prompt: str, **_: Any) -> str:
        if "corrected_response" in system_prompt:
            return json.dumps({"verdict": "pass", "issues": []})
        self.guide.append(system_prompt)
        return "Fiquemos nesta cena mais um pouco."


@pytest.fixture
def recording(monkeypatch: pytest.MonkeyPatch) -> _Recording:
    models = _Recording()
    the_room_agent_is(monkeypatch, turn=models)
    return models


async def test_a_turn_sends_the_guide_her_body_and_no_line_from_above_her_begin_marker(
    recording: _Recording,
) -> None:
    await run_turn(
        transcript="e a fome, por que ela veio?",
        coverage_state=initial_state("P03"),
        messages=[],
        guide_prompt=get_prompt_text(IRPromptKey.GUIDE),
        validator_prompt=get_prompt_text(IRPromptKey.VALIDATOR),
        pericope_num="P03",
        language_code="pt",
        settings=Settings(database_url="sqlite+aiosqlite:///./test.db", google_api_key="fake"),
    )

    sent = recording.guide[0]
    assert sent.startswith("## Who you are\n\nYou are the team's **Digital Facilitator**")
    for note in HER_NOTES:
        assert note not in sent, f"uma nota dela, acima do BEGIN, chegou à voz: {note}"
