import json
from typing import Any

import pytest

from app.core.config import Settings
from app.db.models.internalization_room import IRPromptKey
from app.services.internalization_room._default_prompts import default_prompt
from app.services.internalization_room.coverage import initial_state
from app.services.internalization_room.llm import CACHE_BREAK
from app.services.internalization_room.prompt_blocks import coverage_status_block
from app.services.internalization_room.run_turn import run_turn
from tests.turn_harness import the_room_agent_is

GUIDE = default_prompt(IRPromptKey.GUIDE)["prompt"]
VALIDATOR = default_prompt(IRPromptKey.VALIDATOR)["prompt"]
P = "P01"
EM = "\N{EM DASH}"
FAMILIARIZATION = f"MOMENT: Familiarization {EM} the whole passage; no part has been opened yet."


class _Recording:
    def __init__(self) -> None:
        self.guide: list[str] = []

    async def __call__(self, *, system_prompt: str, user_content: str, **kwargs: Any) -> str:
        if "corrected_response" in system_prompt:
            return json.dumps({"verdict": "pass", "issues": []})
        self.guide.append(system_prompt)
        return "Vamos começar pela Familiarização. Primeiro eu conto a passagem inteira."


@pytest.fixture
def recording(monkeypatch: pytest.MonkeyPatch) -> _Recording:
    models = _Recording()
    the_room_agent_is(monkeypatch, turn=models)
    return models


async def _turn(messages: list[dict[str, Any]], *, opening: bool = False) -> None:
    await run_turn(
        transcript="" if opening else "estamos prontos",
        coverage_state=initial_state(P),
        messages=messages,
        guide_prompt=GUIDE,
        validator_prompt=VALIDATOR,
        pericope_num=P,
        language_code="pt",
        opening=opening,
        settings=Settings(database_url="sqlite+aiosqlite:///./test.db", google_api_key="fake"),
    )


async def test_the_opening_tells_the_guide_the_room_is_in_the_familiarization(
    recording: _Recording,
) -> None:
    await _turn([], opening=True)

    ledger = coverage_status_block(initial_state(P), P)
    assert recording.guide[0].partition(CACHE_BREAK)[2] == f"{ledger}\n\n{FAMILIARIZATION}", (
        "a abertura não dizia ao Guia que a sala estava na Familiarização"
    )


async def test_the_turn_after_scene_two_opened_tells_the_guide_its_internalization_is_open(
    recording: _Recording,
) -> None:
    opened = {
        "role": "guide",
        "text": "Vamos pra Internalização da cena 2. Na segunda cena, Noemi decide voltar.",
        "moment": {
            "before": {"at": "familiarization"},
            "after": {"at": "internalization", "part": 2},
            "by": ["entrance"],
        },
    }

    await _turn([{"role": "team", "text": "estamos prontos"}, opened])

    assert recording.guide[0].endswith(
        f"\n\nMOMENT: Internalization of part 2 of 4 {EM} the part is open."
    ), "o Guia continuava ouvindo Familiarização depois de abrir a cena 2"


def _left_at(moment: dict[str, Any]) -> list[dict[str, Any]]:
    return [{"role": "guide", "text": "", "moment": {"after": moment}}]


async def test_after_her_familiarization_closing_the_guide_hears_it_has_been_said(
    recording: _Recording,
) -> None:
    await _turn(_left_at({"at": "familiarization", "closed": True}))

    assert recording.guide[0].endswith(
        f"\n\nMOMENT: Familiarization {EM} its closing has been said; no part has been opened yet."
    ), "o Guia não sabia que o fechamento da Familiarização já tinha sido dito"
