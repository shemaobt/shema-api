import json
from typing import Any

import pytest

from app.db.models.internalization_room import IRSession
from app.services.internalization_room import back_translation_of, check_the_telling_back
from app.services.internalization_room.languages import ROOM_LANGUAGES
from app.services.internalization_room.llm import CACHE_BREAK
from tests.test_internalization_room_speech_placeholder_language import (
    _EXPECTED_NOTHING_TOLD_BACK as NOTHING_TOLD_BACK,
)
from tests.turn_harness import settings, the_room_agent_is


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


@pytest.mark.parametrize("language_code", ROOM_LANGUAGES)
async def test_a_session_with_nothing_told_back_has_the_validator_read_its_own_language(
    recording: _Recording, language_code: str
) -> None:
    session = _session(language_code)

    await check_the_telling_back(
        session,
        state=back_translation_of(session),
        told=[],
        takes=[],
        settings=settings(),
    )

    assert NOTHING_TOLD_BACK[language_code] in recording.validator[0], (
        "o Validador lia a nota de uma sessão em outra língua que não a dela"
    )
    for other, sentence in NOTHING_TOLD_BACK.items():
        if other != language_code:
            assert sentence not in recording.validator[0]


@pytest.mark.parametrize("language_code", ROOM_LANGUAGES)
async def test_the_telling_back_the_session_keeps_is_the_note_in_its_own_language(
    recording: _Recording, language_code: str
) -> None:
    session = _session(language_code)

    verdict = await check_the_telling_back(
        session,
        state=back_translation_of(session),
        told=[],
        takes=[],
        settings=settings(),
    )

    assert verdict.told_back == NOTHING_TOLD_BACK[language_code], (
        "o registro do turno guardava a nota em outra língua que não a da sessão"
    )
