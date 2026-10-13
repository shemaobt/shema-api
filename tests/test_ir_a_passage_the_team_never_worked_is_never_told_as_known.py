import json
from typing import Any

import pytest

from app.core.config import Settings
from app.db.models.internalization_room import IRPromptKey
from app.services.internalization_room._default_prompts import default_prompt
from app.services.internalization_room.coverage import initial_state
from app.services.internalization_room.run_turn import run_turn
from tests.turn_harness import the_room_agent_is

EARLIER = "EARLIER PASSAGES FOR THIS TEAM:"
HER_VALIDATOR_BLOCK = "## EARLIER PASSAGES FOR THIS TEAM (the app's fact about this team"
NOTICE = (
    "(This team has not worked this passage yet. If you speak of anything below, tell it as "
    "the story's — 'a história conta que…' (English sessions: 'the story tells that…') — only "
    "what is needed, in a few words; never 'lembrem', never 'na última parte'.)"
)
HER_P10_LINE = (
    "EARLIER PASSAGES FOR THIS TEAM: Approved: Ruth 1:1\N{EN DASH}5, Ruth 1:6\N{EN DASH}14, "
    "Ruth 1:15\N{EN DASH}18, Ruth 1:19\N{EN DASH}22, Ruth 2:1\N{EN DASH}7, Ruth 2:8-16, "
    "Ruth 3:1-5. Started, not approved yet: Ruth 2:17-23. Not worked yet: Ruth 3:6-13."
)
P09_UNDER_HER_NOTICE = (
    "**Ruth 3:6-13** — The threshing-floor night: the wing asked for, the word redeemer "
    f"spoken, the oath\n{NOTICE}\n"
)
THE_24_SEPTEMBER_TEAM = {
    "P01": "approved",
    "P02": "approved",
    "P03": "approved",
    "P04": "approved",
    "P05": "approved",
    "P06": "approved",
    "P07": "started",
    "P08": "approved",
    "P09": "not_worked",
}


class _Readers:
    def __init__(self) -> None:
        self.guide: list[str] = []
        self.validator: list[str] = []

    async def __call__(self, *, system_prompt: str, user_content: str, **_: Any) -> str:
        if "corrected_response" in system_prompt:
            self.validator.append(system_prompt)
            return json.dumps({"verdict": "pass", "issues": []})
        self.guide.append(system_prompt)
        return "Vamos ouvir a passagem."


@pytest.fixture
def readers(monkeypatch: pytest.MonkeyPatch) -> _Readers:
    models = _Readers()
    the_room_agent_is(monkeypatch, turn=models)
    return models


async def opened(pericope: str, earlier_passages: dict[str, str] | None) -> None:
    await run_turn(
        transcript="",
        coverage_state=initial_state(pericope),
        messages=[],
        guide_prompt=default_prompt(IRPromptKey.GUIDE)["prompt"],
        validator_prompt=default_prompt(IRPromptKey.VALIDATOR)["prompt"],
        pericope_num=pericope,
        language_code="pt",
        opening=True,
        settings=Settings(database_url="sqlite+aiosqlite:///./test.db", google_api_key="fake"),
        earlier_passages=earlier_passages,
    )


def earlier_line(system_prompt: str) -> str | None:
    lines = [line for line in system_prompt.splitlines() if line.startswith(EARLIER)]
    return lines[0] if lines else None


async def test_the_team_of_24_september_working_p10_is_told_her_three_groups_by_both_readers(
    readers,
) -> None:
    await opened("P10", THE_24_SEPTEMBER_TEAM)

    for reader, prompt in (("Guide", readers.guide[0]), ("Validator", readers.validator[0])):
        assert earlier_line(prompt) == HER_P10_LINE, (
            f"o {reader} não recebia a linha dela com os três grupos, em ordem da história"
        )
        assert prompt.count(NOTICE) == 1 and P09_UNDER_HER_NOTICE in prompt, (
            f"o aviso dela não ficava só sob a passagem que a equipe nunca trabalhou ({reader})"
        )


async def test_the_first_passage_of_a_book_tells_neither_reader_of_any_earlier_passage(
    readers,
) -> None:
    await opened("P01", None)

    for reader, prompt in (("Guide", readers.guide[0]), ("Validator", readers.validator[0])):
        assert not any(told in prompt for told in (EARLIER, HER_VALIDATOR_BLOCK, NOTICE)), (
            f"a primeira passagem do livro chegava ao {reader} com passagens anteriores"
        )
