"""Her notice under each earlier passage this team has not worked, where the voice reads it.

The stamp told the voice which earlier passages the team had worked, in a line after the
cache mark, far from the digests it reads those passages' content in. Her app puts her
approved notice right under the heading of each digest the stamp marks not worked, and both
the Guide and the Validator read it there.
"""

import json
from typing import Any

import pytest

from app.core.config import Settings
from app.db.models.internalization_room import IRPromptKey
from app.services.internalization_room._default_prompts import default_prompt
from app.services.internalization_room.coverage import initial_state
from app.services.internalization_room.run_turn import run_turn
from tests.turn_harness import the_room_agent_is

GUIDE = default_prompt(IRPromptKey.GUIDE)["prompt"]
VALIDATOR = default_prompt(IRPromptKey.VALIDATOR)["prompt"]
P = "P03"

#: Her notice, word for word as the ticket and her `NOT_WORKED_NOTICE` give it.
NOTICE = (
    "(This team has not worked this passage yet. If you speak of anything below, tell it as "
    "the story's — 'a história conta que…' (English sessions: 'the story tells that…') — only "
    "what is needed, in a few words; never 'lembrem', never 'na última parte'.)"
)

#: The two digest headings, typed from the maps' own titles.
P01_HEADING = (
    "**Ruth 1:1\N{EN DASH}5** — The famine, the family's sojourn, and the emptying of the household"
)
P02_HEADING = (
    "**Ruth 1:6\N{EN DASH}14** — The return road begins; Naomi urges her daughters-in-law "
    "back; Orpah turns, Ruth clings"
)


def _settings() -> Settings:
    return Settings(database_url="sqlite+aiosqlite:///./test.db", google_api_key="fake")


class _Recording:
    def __init__(self) -> None:
        self.guide: list[str] = []
        self.validator: list[str] = []

    async def __call__(self, *, system_prompt: str, user_content: str, **kwargs: Any) -> str:
        if "corrected_response" in system_prompt:
            self.validator.append(system_prompt)
            return json.dumps({"verdict": "pass", "issues": []})
        self.guide.append(system_prompt)
        return "Vamos ouvir a passagem."


@pytest.fixture
def recording(monkeypatch: pytest.MonkeyPatch) -> _Recording:
    models = _Recording()
    the_room_agent_is(monkeypatch, turn=models)
    return models


async def _turn(earlier_passages: dict[str, str]) -> None:
    await run_turn(
        transcript="",
        coverage_state=initial_state(P),
        messages=[],
        guide_prompt=GUIDE,
        validator_prompt=VALIDATOR,
        pericope_num=P,
        language_code="pt",
        opening=True,
        settings=_settings(),
        earlier_passages=earlier_passages,
    )


async def test_the_guide_reads_her_notice_under_the_passage_the_team_never_worked(
    recording: _Recording,
) -> None:
    await _turn({"P01": "approved", "P02": "not_worked"})

    guide = recording.guide[0]
    assert f"{P02_HEADING}\n{NOTICE}\n" in guide, (
        "a voz lia o resumo de uma passagem que a equipe nunca fez sem o aviso dela"
    )
    assert f"{P01_HEADING}\n{NOTICE}" not in guide and guide.count(NOTICE) == 1, (
        "uma passagem aprovada recebia o aviso de não trabalhada"
    )
