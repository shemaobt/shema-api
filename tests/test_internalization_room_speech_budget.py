"""The oral pacing budget is an application gate, not a prompt suggestion."""

import json
import sys
from typing import Any

import pytest

from app.core.config import Settings
from app.db.models.internalization_room import IRPromptKey
from app.services.internalization_room._default_prompts import default_prompt
from app.services.internalization_room.run_turn import (
    MAX_SPOKEN_PANORAMA_WORDS,
    MAX_SPOKEN_TURN_WORDS,
    OPENING_BUDGET,
    PANORAMA_BUDGET,
    TURN_BUDGET,
    run_turn,
    spoken_turn_fits_budget,
)

GUIDE = default_prompt(IRPromptKey.GUIDE)["prompt"]
VALIDATOR = default_prompt(IRPromptKey.VALIDATOR)["prompt"]
P = "P03"


def _settings() -> Settings:
    return Settings(database_url="sqlite+aiosqlite:///./test.db", google_api_key="fake")


def test_short_turns_fit_the_budget() -> None:
    assert spoken_turn_fits_budget("Que bom. Agora ensaiem juntos. Depois me contem.")


def test_too_many_words_bust_the_budget() -> None:
    assert not spoken_turn_fits_budget("palavra " * (MAX_SPOKEN_TURN_WORDS + 1))


def test_too_many_sentences_bust_the_budget() -> None:
    assert not spoken_turn_fits_budget("Uma. Duas. Três. Quatro.")


class LongWindedAgent:
    """A Guide that always over-talks and a Validator that always approves it."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    async def __call__(self, *, system_prompt: str, user_content: str, **kwargs: Any) -> str:
        if "corrected_response" in system_prompt:
            self.calls.append("validator")
            return json.dumps({"verdict": "pass", "issues": []})
        self.calls.append("guide")
        return "Esta frase tem muitas palavras demais para uma sala oral. " * 10


@pytest.mark.asyncio
async def test_an_over_budget_draft_fails_safe_even_with_a_passing_verdict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = sys.modules["app.services.internalization_room.run_turn"]
    agent = LongWindedAgent()
    monkeypatch.setattr(module, "call_agent", agent)

    outcome = await run_turn(
        session_language="Portuguese",
        language_code="pt",
        transcript="a fome chegou",
        coverage_state={},
        messages=[{"role": "guide", "text": "abertura"}],
        guide_prompt=GUIDE,
        validator_prompt=VALIDATOR,
        pericope_num=P,
        settings=_settings(),
        budget=TURN_BUDGET,
    )

    assert outcome.used_fail_safe
    assert outcome.fixed_line


@pytest.mark.asyncio
async def test_the_budget_is_off_unless_asked_for(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Panorama openings and legacy callers keep today's behaviour untouched."""
    module = sys.modules["app.services.internalization_room.run_turn"]
    agent = LongWindedAgent()
    monkeypatch.setattr(module, "call_agent", agent)

    outcome = await run_turn(
        session_language="Portuguese",
        language_code="pt",
        transcript="a fome chegou",
        coverage_state={},
        messages=[],
        guide_prompt=GUIDE,
        validator_prompt=VALIDATOR,
        pericope_num=P,
        settings=_settings(),
    )

    assert not outcome.used_fail_safe


def test_the_panorama_movement_is_given_more_room_than_a_turn() -> None:
    """The whole-before-the-parts cannot be said in three sentences, and it is said once.

    Lifting the ceiling from the opening entirely produced a 232-word, ninety-second
    monologue — the thing `guide_system_prompt.md` calls "never a long speech". A wider
    ceiling for the panorama and the ordinary one for the scene keeps both true.
    """
    panorama = "palavra " * (MAX_SPOKEN_TURN_WORDS + 5)

    assert not TURN_BUDGET.fits(panorama)
    assert PANORAMA_BUDGET.fits(panorama)
    assert not PANORAMA_BUDGET.fits("palavra " * (MAX_SPOKEN_PANORAMA_WORDS + 1))
    assert OPENING_BUDGET.words == MAX_SPOKEN_PANORAMA_WORDS + MAX_SPOKEN_TURN_WORDS
