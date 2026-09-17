"""The oral pacing budget is an application gate, not a prompt suggestion."""

import json
import sys
from typing import Any

import pytest

from app.core.config import Settings
from app.db.models.internalization_room import IRPromptKey
from app.services.internalization_room._default_prompts import default_prompt
from app.services.internalization_room.comprehension.practice import (
    guide_invited_mother_tongue_practice,
)
from app.services.internalization_room.run_turn import (
    MAX_SPOKEN_PANORAMA_WORDS,
    MAX_SPOKEN_TURN_WORDS,
    OPENING_BUDGET,
    OPENING_MOVEMENT_MARK,
    PANORAMA_BUDGET,
    SCENE_MOVEMENT_BUDGET,
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
    ceiling for the panorama, and one for the scene that has the invitation counted into
    it, keeps both true.
    """
    panorama = "palavra " * (MAX_SPOKEN_TURN_WORDS + 5)

    assert not TURN_BUDGET.fits(panorama)
    assert PANORAMA_BUDGET.fits(panorama)
    assert not PANORAMA_BUDGET.fits("palavra " * (MAX_SPOKEN_PANORAMA_WORDS + 1))
    assert OPENING_BUDGET.words == MAX_SPOKEN_PANORAMA_WORDS + SCENE_MOVEMENT_BUDGET.words


class OpeningThatInvitesAgent:
    """The opening of session bc9c71c2, with the invitation it was supposed to end on.

    The panorama and the scene are the Guide's own words from that session, kept verbatim.
    Only the closing sentence is different: the room said "Try rehearsing it together, and
    then tell me what you said." and this says what the contract asks for instead.
    """

    async def __call__(self, *, system_prompt: str, user_content: str, **kwargs: Any) -> str:
        if "corrected_response" in system_prompt:
            return json.dumps({"verdict": "pass", "issues": []})
        return (
            "This story begins with a family leaving home because of hunger, only to face "
            "deep sadness in a foreign land. It is a quiet, heavy account of a household "
            "slowly shrinking until only one woman remains.\n"
            f"{OPENING_MOVEMENT_MARK}\n"
            "Long ago, when judges ruled Israel, a famine forced Elimelech and Naomi to move "
            "from Bethlehem to Moab with their two sons. Let's start with this first part. "
            "Now rehearse this scene together in your own language; when you have finished, "
            "come back and tell me in English what you understood."
        )


@pytest.mark.asyncio
async def test_the_scene_movement_has_room_for_the_invitation_it_must_end_on(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Session bc9c71c2: the opening that fit was the one that dropped half the contract.

    The Guide is told to close the second movement with the invitation, and the invitation
    is twenty-two words. The movement answered to a turn's ceiling — forty-five words, the
    same one an ordinary turn gets for carrying nothing but itself — so the scene and the
    invitation were made to share it. What came out was "Try rehearsing it together, and
    then tell me what you said.": no phrase naming the language, no bridge language named
    either. The room economised on the half nobody was measuring.

    That session's own opening, with the sentence it was asked for put back, is fifty-one
    words in three sentences. The scene it opens with is the Guide's, unedited.
    """
    module = sys.modules["app.services.internalization_room.run_turn"]
    monkeypatch.setattr(module, "call_agent", OpeningThatInvitesAgent())

    outcome = await run_turn(
        session_language="English",
        language_code="en",
        transcript="",
        coverage_state={},
        messages=[],
        guide_prompt=GUIDE,
        validator_prompt=VALIDATOR,
        pericope_num=P,
        opening=True,
        settings=_settings(),
        budget=OPENING_BUDGET,
        ask_for_movements=True,
    )

    assert not outcome.used_fail_safe, outcome.fixed_line
    assert len(outcome.movements) == 2
    assert guide_invited_mother_tongue_practice(outcome.speech), outcome.speech
