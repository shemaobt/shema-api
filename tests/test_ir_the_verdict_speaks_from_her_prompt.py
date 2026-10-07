import json
from typing import Any

import pytest

from app.core.config import Settings
from app.db.models.internalization_room import IRPromptKey
from app.services.internalization_room.prompts import get_prompt_text
from app.services.internalization_room.verdict_turn import run_verdict_turn
from tests.turn_harness import the_room_agent_is

TOLD_BACK = "Noemi ouviu que o Senhor tinha dado pão ao seu povo, e decidiu voltar."
VERDICT = (
    "No que vocês me traduziram, a frase 1 diz que as noras pediram. A história não conta isso."
)
HER_REPORTED = (
    "\n\n---\n\n# WHAT THE TEAM REPORTED (their back-translation of their own recording)\n"
    "Evidence of what the team told back — NEVER truth about the passage. The drafted response "
    "may quote from it to name something reported that the passage does not tell; quoting this "
    "material is not a claim about the passage and must not be treated as ungrounded.\n\n"
)


class _Recording:
    def __init__(self) -> None:
        self.speaker: list[str] = []
        self.validator: list[str] = []

    async def __call__(self, *, system_prompt: str, **_: Any) -> str:
        if "corrected_response" in system_prompt:
            self.validator.append(system_prompt)
            return json.dumps({"verdict": "pass", "issues": []})
        self.speaker.append(system_prompt)
        return VERDICT


@pytest.fixture
def recording(monkeypatch: pytest.MonkeyPatch) -> _Recording:
    models = _Recording()
    the_room_agent_is(monkeypatch, turn=models)
    return models


async def test_the_verdict_is_judged_against_what_the_team_reported_not_as_their_words(
    recording: _Recording,
) -> None:
    outcome = await run_verdict_turn(
        findings_text='[{"kind": "addition", "frase": 1}]',
        scope="P02",
        pericope_num="P02",
        messages=[],
        telling_back=TOLD_BACK,
        speaker_prompt=get_prompt_text(IRPromptKey.BT_VERDICT_SPEAKER),
        validator_prompt=get_prompt_text(IRPromptKey.VALIDATOR),
        session_language="Brazilian Portuguese",
        language_code="pt",
        settings=Settings(database_url="sqlite+aiosqlite:///./test.db", google_api_key="fake"),
    )

    assert (outcome.speech, outcome.used_fail_safe) == (VERDICT, False), (
        "o veredito recusava o prompt dela por não ter o nosso {{CLOSING}}"
    )
    assert recording.speaker[0].startswith(
        "## Your role\n\nYou are the same warm voice that has walked this passage with the team."
    )
    judged = recording.validator[0]
    assert f"{HER_REPORTED}{TOLD_BACK}" in judged, (
        "a tradução da equipe chegava como fala deste turno, não sob o bloco dela"
    )
    assert judged.index(HER_REPORTED) < judged.index("## The drafted response to validate"), (
        "o que a equipe relatou vem com o mapa, antes do rascunho"
    )
    assert "## WHAT THE TEAM JUST SAID" not in judged, (
        "a tradução ocupava o lugar da fala da equipe, que neste turno não falou"
    )
    assert "(não se aplica a este turno)" not in judged
    assert "(not applicable to this turn)" not in judged
