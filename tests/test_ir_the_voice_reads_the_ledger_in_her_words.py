import json
import re
from typing import Any

import pytest

from app.core.config import Settings
from app.db.models.internalization_room import IRPromptKey
from app.services.internalization_room._default_prompts import default_prompt
from app.services.internalization_room.canon.elements import elements_for
from app.services.internalization_room.coverage import initial_state, merge
from app.services.internalization_room.llm import CACHE_BREAK
from app.services.internalization_room.run_turn import run_turn
from tests.turn_harness import the_room_agent_is

P = "P01"


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


def _engaged(*keys: str) -> dict[str, str]:
    return merge(initial_state(P), pericope_num=P, engaged=list(keys))


def _scene_keys(scene: int) -> list[str]:
    return [element.key for element in elements_for(P) if element.scene == scene]


async def test_with_scene_one_closed_no_line_the_guide_reads_points_at_an_open_scene(
    recording: _Recording,
) -> None:
    await run_turn(
        transcript="a fome veio e eles foram para Moabe",
        coverage_state=_engaged(*_scene_keys(1)),
        messages=[],
        guide_prompt=default_prompt(IRPromptKey.GUIDE)["prompt"],
        validator_prompt=default_prompt(IRPromptKey.VALIDATOR)["prompt"],
        pericope_num=P,
        language_code="pt",
        settings=Settings(database_url="sqlite+aiosqlite:///./test.db", google_api_key="fake"),
    )

    read = recording.guide[0].partition(CACHE_BREAK)[2].splitlines()
    pointing = [
        line for line in read if re.search(r"\bS[234]\b", line) and not line.startswith("  ")
    ]
    assert pointing == [], (
        "o ledger apontava a primeira cena com contas abertas, e a voz ia para lá"
    )
