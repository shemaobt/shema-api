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
from app.services.internalization_room.prompt_blocks import coverage_status_block
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


def test_the_first_turn_reads_her_headings_with_every_element_not_yet_touched() -> None:
    lines = coverage_status_block(initial_state(P), P).splitlines()

    assert lines[:5] == [
        "LEDGER (the app's notes — information only; you decide what comes next)",
        "",
        "WORKED WITH BY THE TEAM (engaged): (nothing yet — the session is just beginning)",
        "",
        "NOT YET TOUCHED (still deserve a visit before the session ends):",
    ], "o ledger vinha como lista de tarefas, COVERED e REMAINING, sem o cabeçalho dela"
    assert [line.split(":")[0] for line in lines[5:]] == [
        "  arc",
        "  context",
        "  tone",
        "  function",
        "  scene",
        "  being",
        "  place",
        "  object",
        "  time",
        "  significant_absence",
        "  preserved_element",
    ], "os tipos saíam com os nomes nossos, 'absence' e 'preserved', não com os dela"


def test_what_the_voice_raised_is_listed_apart_from_what_nobody_has_touched() -> None:
    state = merge(initial_state(P), pericope_num=P, surfaced=["arc", "preserved:R5"])

    lines = coverage_status_block(state, P).splitlines()

    assert lines[4:9] == [
        "RAISED BY YOU, NOT YET TAKEN UP BY THE TEAM:",
        "  arc: Level-1 arc",
        "  preserved_element: R5",
        "",
        "NOT YET TOUCHED (still deserve a visit before the session ends):",
    ], "o que a voz levantou e a equipe não pegou ia junto com o que ninguém tocou"
    assert lines[9] == "  context: Level-1 context"
    assert lines[-1] == "  preserved_element: R3, R10"
