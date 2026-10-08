import json
from typing import Any

import pytest

from app.db.models.internalization_room import IRSession
from app.services.internalization_room import back_translation_of, check_the_telling_back
from app.services.internalization_room.llm import CACHE_BREAK
from tests.turn_harness import settings, the_room_agent_is

NOTHING_TOLD_PT = "(a equipe ainda não traduziu nada)"
NOTHING_TOLD_EN = "(the team has not translated anything yet)"


class _Recording:
    def __init__(self) -> None:
        self.validator: list[str] = []

    async def turn(self, *, system_prompt: str, **_: Any) -> str:
        if "corrected_response" in system_prompt:
            self.validator.append(system_prompt.replace(CACHE_BREAK, ""))
            return json.dumps({"verdict": "pass", "issues": []})
        return "Contem de novo, por favor."

    async def analyst(self, **_: Any) -> str:
        return json.dumps({"findings": []})


@pytest.fixture
def recording(monkeypatch: pytest.MonkeyPatch) -> _Recording:
    models = _Recording()
    the_room_agent_is(monkeypatch, turn=models.turn, analyst=models.analyst)
    return models


def _session(language: str) -> IRSession:
    return IRSession(
        id=f"sessao-{language}", pericope="P03", project_id="equipe", language=language
    )


async def test_a_portuguese_session_with_nothing_told_back_has_the_validator_read_portuguese(
    recording: _Recording,
) -> None:
    session = _session("pt")

    await check_the_telling_back(
        session,
        state=back_translation_of(session),
        told=[],
        takes=[],
        settings=settings(),
    )

    assert NOTHING_TOLD_PT in recording.validator[0], (
        "o Validador lia a nota em inglês dentro de um material em português"
    )
    assert NOTHING_TOLD_EN not in recording.validator[0]


async def test_an_english_session_with_nothing_told_back_has_the_validator_read_english(
    recording: _Recording,
) -> None:
    session = _session("en")

    await check_the_telling_back(
        session,
        state=back_translation_of(session),
        told=[],
        takes=[],
        settings=settings(),
    )

    assert NOTHING_TOLD_EN in recording.validator[0], (
        "a sessão em inglês deixou de ler a nota em inglês"
    )
    assert NOTHING_TOLD_PT not in recording.validator[0]


async def test_the_telling_back_the_session_keeps_is_the_note_in_its_own_language(
    recording: _Recording,
) -> None:
    session = _session("pt")

    verdict = await check_the_telling_back(
        session,
        state=back_translation_of(session),
        told=[],
        takes=[],
        settings=settings(),
    )

    assert verdict.told_back == NOTHING_TOLD_PT, (
        "o registro do turno guardava a nota em inglês de uma sessão em português"
    )
