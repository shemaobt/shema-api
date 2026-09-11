"""ENG-775 (resto) — no ceiling ever comes back, and the Guide always introduces itself.

Marcia, answer 5: there is no word ceiling, no sentence ceiling, and no reject-for-length —
length is prompt style. DOCTRINE.md forbids all three in code. `ENG-793` already emptied
`run_turn.py`, `live_turn.py` and `prepare_opening.py` of them; the first test here is the
guard that keeps them out.
"""

from __future__ import annotations

import re
from pathlib import Path

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
