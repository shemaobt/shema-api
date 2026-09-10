"""Three things reach the Validator: the map, the team's own words, and the draft.

The bounded conversation window and the `[APP-OWNED SESSION STATE — not team speech]` block
came from the abandoned August branch. Her rebuilt Validator takes neither: the state that
block carried — bridge mode, comprehension status, the active probe contract — no longer
exists, and the conversation is the Guide's to hold (ENG-749).
"""

import json
import sys
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.models.internalization_room import IRPromptKey
from app.services.internalization_room._default_prompts import default_prompt
from app.services.internalization_room.coverage import initial_state
from app.services.internalization_room.hearing import HeardSpeech
from app.services.internalization_room.run_turn import run_turn

GUIDE = default_prompt(IRPromptKey.GUIDE)["prompt"]
VALIDATOR = default_prompt(IRPromptKey.VALIDATOR)["prompt"]
P = "P03"

#: The map's own pericope title, read off the canon rather than re-rendered here.
MAP_HEADING = "Naomi's last appeal; Ruth's vow; Naomi's silence"

#: The label that told the Validator the block below was the app talking.
APP_OWNED = "[APP-OWNED SESSION STATE — not team speech]"

#: The two placeholders this ticket names, both of them Portuguese literals served to
#: every session whatever language it speaks.
OPENING_PLACEHOLDER = "(início da sessão — ainda não houve troca)"
NO_UTTERANCE_PLACEHOLDER = "(a equipe ainda não falou — abertura da sessão)"

EARLIER_TEAM = "a fome levou eles embora de Belém"
EARLIER_GUIDE = "isso mesmo, e a família sai de casa"
DRAFT = "Fiquemos nesta cena mais um pouco."


def _settings() -> Settings:
    return Settings(database_url="sqlite+aiosqlite:///./test.db", google_api_key="fake")


class _Recording:
    """Lets the Guide draft through and keeps the system prompt the Validator judged by."""

    def __init__(self) -> None:
        self.validator: list[str] = []

    async def __call__(self, *, system_prompt: str, user_content: str, **_: Any) -> str:
        if "corrected_response" in system_prompt:
            self.validator.append(system_prompt)
            return json.dumps({"verdict": "pass", "issues": []})
        return DRAFT


@pytest.fixture
def recording(monkeypatch: pytest.MonkeyPatch) -> _Recording:
    models = _Recording()
    monkeypatch.setattr(
        sys.modules["app.services.internalization_room.run_turn"], "call_agent", models
    )
    return models


async def test_the_map_the_teams_words_and_the_draft_last_and_nothing_else(
    recording: _Recording,
) -> None:
    """And no window: nine exchanges of team speech used to ride in ahead of the utterance."""
    await run_turn(
        transcript="e a fome, por que ela veio?",
        coverage_state=initial_state(P),
        messages=[
            {"role": "guide", "text": EARLIER_GUIDE},
            {"role": "team", "text": EARLIER_TEAM},
        ],
        guide_prompt=GUIDE,
        validator_prompt=VALIDATOR,
        pericope_num=P,
        language_code="pt",
        settings=_settings(),
    )

    judged = recording.validator[0]
    assert judged.index(MAP_HEADING) < judged.index("e a fome, por que ela veio?"), (
        "o mapa é o padrão de verdade e vem antes da evidência"
    )
    assert judged.index("e a fome, por que ela veio?") < judged.index(DRAFT), (
        "o rascunho é a última coisa que o Validador lê"
    )
    assert EARLIER_TEAM not in judged, (
        f"a janela de conversa continuava chegando ao Validador: {judged[-1500:]}"
    )
    assert EARLIER_GUIDE not in judged


async def test_no_app_owned_state_block_is_appended_to_what_it_judges(
    db_session: AsyncSession, recording: _Recording, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The live path is the only one that built the block, so it is where it has to be gone."""
    from app.services.internalization_room.live_turn import run_comprehension_turn
    from app.services.internalization_room.sessions import append_exchange, create_session

    session = await create_session(db_session, language="pt", pericope=P)
    session = await append_exchange(
        db_session, session, team_utterance="", guide_response="Quem aparece nesta parte?"
    )

    await run_comprehension_turn(
        db_session,
        session,
        speech=HeardSpeech(text="A fome chegou e eles partiram."),
        opening=False,
        guide_prompt=GUIDE,
        validator_prompt=VALIDATOR,
        settings=get_settings(),
    )

    judged = recording.validator[0]
    assert APP_OWNED not in judged, (
        f"o estado do app continuava colado depois do rascunho: {judged[-1500:]}"
    )


async def test_an_english_session_reads_neither_portuguese_placeholder(
    recording: _Recording,
) -> None:
    await run_turn(
        transcript="",
        coverage_state=initial_state(P),
        messages=[],
        guide_prompt=GUIDE,
        validator_prompt=VALIDATOR,
        pericope_num=P,
        session_language="English",
        language_code="en",
        opening=True,
        settings=_settings(),
    )

    judged = recording.validator[0]
    assert OPENING_PLACEHOLDER not in judged
    assert NO_UTTERANCE_PLACEHOLDER not in judged
    assert "(the team has not spoken yet — session opening)" in judged
