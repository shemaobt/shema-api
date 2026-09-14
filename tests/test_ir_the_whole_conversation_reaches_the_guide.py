"""The Guide is handed every exchange of the session, as the turns they were.

Nine exchanges into Ruth 1:1-5 the Guide greeted the team and introduced itself: everything
older than six messages had never been in its prompt, so as far as it could tell the session
had started three exchanges ago. DOCTRINE §3 forbids the mechanism in as many words — the
whole conversation is in context every turn — and Marcia on who checks a retelling: "Quem
confere o reconto é o Guia, item por item contra o mapa, com a conversa inteira em contexto."
"""

import json
import sys
from typing import Any

import pytest

from app.core.config import Settings
from app.db.models.internalization_room import IRPromptKey
from app.services.internalization_room._default_prompts import default_prompt
from app.services.internalization_room.coverage import initial_state
from app.services.internalization_room.run_turn import run_turn, run_verdict_turn

GUIDE = default_prompt(IRPromptKey.GUIDE)["prompt"]
VALIDATOR = default_prompt(IRPromptKey.VALIDATOR)["prompt"]
VERDICT_SPEAKER = default_prompt(IRPromptKey.BT_VERDICT_SPEAKER)["prompt"]
P = "P03"

#: The Portuguese literal the flat conversation block served to every session.
OPENING_PLACEHOLDER = "(início da sessão — ainda não houve troca)"


def _settings() -> Settings:
    return Settings(database_url="sqlite+aiosqlite:///./test.db", google_api_key="fake")


def _exchanges(count: int) -> list[dict[str, Any]]:
    """A session as it is stored: the Guide opens, and the two sides alternate from there."""
    return [{"role": "guide" if i % 2 == 0 else "team", "text": f"fala {i}"} for i in range(count)]


class _Recording:
    def __init__(self) -> None:
        self.guide: list[dict[str, Any]] = []

    async def __call__(self, *, system_prompt: str, user_content: str, **kwargs: Any) -> str:
        if "corrected_response" in system_prompt:
            return json.dumps({"verdict": "pass", "issues": []})
        self.guide.append(
            {"user_content": user_content, "conversation": kwargs.get("conversation")}
        )
        return "Fiquemos nesta cena."


@pytest.fixture
def recording(monkeypatch: pytest.MonkeyPatch) -> _Recording:
    models = _Recording()
    monkeypatch.setattr(
        sys.modules["app.services.internalization_room.run_turn"], "call_agent", models
    )
    return models


@pytest.mark.parametrize("count", [10, 40])
async def test_every_exchange_travels_as_a_turn_however_long_the_session_is(
    recording: _Recording, count: int
) -> None:
    """Ten messages produce ten model messages plus the new utterance, and forty produce forty."""
    await run_turn(
        transcript="e a fome, por que ela veio?",
        coverage_state=initial_state(P),
        messages=_exchanges(count),
        guide_prompt=GUIDE,
        validator_prompt=VALIDATOR,
        pericope_num=P,
        language_code="pt",
        settings=_settings(),
    )

    asked = recording.guide[0]
    assert asked["conversation"] == [
        {"role": "assistant" if i % 2 == 0 else "user", "text": f"fala {i}"} for i in range(count)
    ], "a equipe fala como user e o Guia como assistant, da mais velha para a mais nova"
    assert asked["user_content"] == "e a fome, por que ela veio?", (
        "a fala nova da equipe é a última mensagem, e é só ela"
    )


async def test_the_opening_asks_in_the_sessions_own_language_with_nothing_behind_it(
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

    asked = recording.guide[0]
    assert asked["conversation"] == []
    assert OPENING_PLACEHOLDER not in asked["user_content"], (
        f"o literal em português continuava servido a toda sessão: {asked['user_content']}"
    )


async def test_a_turn_nobody_spoke_in_still_ends_on_a_user_message(
    recording: _Recording,
) -> None:
    """The verdict turn: the API refuses a request that ends on the Guide's own last speech."""
    await run_verdict_turn(
        findings_text="(nenhum achado)",
        closing="\nPeça o próximo trecho.",
        scope=P,
        pericope_num=P,
        messages=_exchanges(5),
        speaker_prompt=VERDICT_SPEAKER,
        validator_prompt=VALIDATOR,
        telling_back="a fome chegou e eles partiram",
        language_code="pt",
        settings=_settings(),
    )

    asked = recording.guide[0]
    assert asked["conversation"][-1]["role"] == "assistant", (
        "uma sessão termina na fala do Guia, que é onde o turno de veredito a encontra"
    )
    assert asked["user_content"].strip() != "", (
        "sem uma última mensagem user a chamada volta 400 e a equipe ouve uma linha enlatada"
    )
