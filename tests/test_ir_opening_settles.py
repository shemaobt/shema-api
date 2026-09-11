"""ENG-775 (resto) — no ceiling ever comes back, and the Guide always introduces itself.

Marcia, answer 5: there is no word ceiling, no sentence ceiling, and no reject-for-length —
length is prompt style. DOCTRINE.md forbids all three in code. `ENG-793` already emptied
`run_turn.py`, `live_turn.py` and `prepare_opening.py` of them; the first test here is the
guard that keeps them out.

`ALREADY_MET_INSTRUCTION` told the Guide, in words, not to introduce itself again after the
panorama — contradicting her own system prompt, which already covers the introduction on
every session's first utterance, and reading as an instruction rather than the fact
`session.after_panorama` actually is. The rest of this file guards its removal.
"""

from __future__ import annotations

import inspect
import json
import re
import sys
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models.internalization_room import IRPromptKey
from app.services.internalization_room import turn_instructions
from app.services.internalization_room._default_prompts import default_prompt
from app.services.internalization_room.hearing import HeardSpeech
from app.services.internalization_room.live_turn import run_comprehension_turn
from app.services.internalization_room.passage_turn import run_turn
from app.services.internalization_room.sessions import create_session
from app.services.internalization_room.turn_instructions import OPENING_INSTRUCTION

GUIDE = default_prompt(IRPromptKey.GUIDE)["prompt"]
VALIDATOR = default_prompt(IRPromptKey.VALIDATOR)["prompt"]
P = "P03"

_ROOM = Path(__file__).resolve().parent.parent / "app" / "services" / "internalization_room"
_FILES_ENG_775_OWNS = ("run_turn.py", "live_turn.py", "prepare_opening.py")

#: DOCTRINE.md §3, first rule — speech/word ceilings, sentence counts, reject-for-length.
_FORBIDDEN_LENGTH_SYMBOLS = re.compile(
    r"MAX_SPOKEN_[A-Z_]*|SpeechBudget|over_speech_budget|_broken_ceiling"
    r"|OPENING_BUDGET|speech_budget_for"
)


def test_no_word_or_sentence_budget_survives_the_turn_pipeline() -> None:
    """Guard, not red-green: these three files stayed clean once ENG-793 emptied them. A
    budget symbol reappearing here is exactly the regression DOCTRINE.md's own build-time
    grep exists to catch — this is the same check, run where the test suite reads it."""
    for name in _FILES_ENG_775_OWNS:
        text = (_ROOM / name).read_text()
        assert not _FORBIDDEN_LENGTH_SYMBOLS.search(text), name


def test_already_met_instruction_is_gone() -> None:
    """ENG-775 item 5: the instruction, the flag, and the parameter that carried it are all
    deleted — not merely unused. `session.after_panorama` remains as a fact on the model; it
    is the promotion of that fact into an instruction that had to go."""
    assert not hasattr(turn_instructions, "ALREADY_MET_INSTRUCTION")
    assert "already_met" not in inspect.signature(run_turn).parameters
    for name in ("turn_instructions.py", "passage_turn.py", *_FILES_ENG_775_OWNS[1:]):
        text = (_ROOM / name).read_text()
        assert "ALREADY_MET_INSTRUCTION" not in text, name
        assert "already_met" not in text, name


def test_no_instruction_tells_the_guide_not_to_introduce_itself() -> None:
    """Doctrine-shaped: grep for either phrasing the deleted instruction used. Her prompt
    already says the Guide introduces itself on the session's first utterance; the app must
    never say the opposite."""
    text = (_ROOM / "turn_instructions.py").read_text()
    assert "NÃO se apresente" not in text
    assert "do not introduce" not in text.lower()


async def test_a_session_after_the_panorama_is_still_told_to_introduce_itself(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The behavioural half of item 5: `after_panorama=True` used to reach the Guide as
    `ALREADY_MET_INSTRUCTION`. It must reach it as `OPENING_INSTRUCTION`, same as any other
    first turn — the flag stays a fact the room could use elsewhere; it stops being words
    telling the model what not to say."""
    captured: dict[str, str] = {}

    async def _fake_call_agent(*, system_prompt: str, user_content: str, **_: Any) -> str:
        if "corrected_response" in system_prompt:
            return json.dumps({"verdict": "pass", "issues": []})
        captured["user_content"] = user_content
        return "Bem-vindos! Vamos ficar com Rute."

    monkeypatch.setattr(
        sys.modules["app.services.internalization_room.run_turn"], "call_agent", _fake_call_agent
    )

    session = await create_session(db_session, pericope=P, after_panorama=True, language="pt")

    await run_comprehension_turn(
        db_session,
        session,
        speech=HeardSpeech(text=""),
        opening=True,
        guide_prompt=GUIDE,
        validator_prompt=VALIDATOR,
        settings=get_settings(),
    )

    assert OPENING_INSTRUCTION in captured["user_content"]
    assert "do NOT introduce yourself" not in captured["user_content"]


def test_the_prepared_opening_asks_for_one_movement_on_purpose() -> None:
    """ENG-775 item 4: settled as one movement on purpose, not left collapsed by accident.
    The app already falls back to a single clip gracefully when a turn carries no segments
    (`turn_result.dart`: "a turn whose segments are missing is simply spoken in one breath"),
    so matching the live opening's two movements here would cost a second stored audio key
    and a migration for pacing no team has a way to notice is different.

    Falsified by hand: added `ask_for_movements=True` to the `run_turn` call in
    `prepare_opening.py`, watched this test fail, then removed it again — never via git.
    """
    from app.services.internalization_room import prepare_opening as prepare_opening_module

    source = inspect.getsource(prepare_opening_module.prepare_opening)
    assert "ask_for_movements" not in source
