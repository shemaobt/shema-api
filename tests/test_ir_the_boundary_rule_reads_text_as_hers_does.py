"""ENG-1650 — the boundary rule reads a Guide line's characters as her JavaScript does.

The answers are those of her `isBoundaryTurn` (`src/observe/dossier.ts` at 18fa7c4) run under
node on the same strings: Python's `\\s`, `\\b` and ignore-case are not JavaScript's.
"""

from __future__ import annotations

import pytest

from app.services.internalization_room.session_turns import is_boundary_turn

JS_SPACES = [
    "\t",
    "\n",
    "\x0b",
    "\x0c",
    "\r",
    " ",
    "\xa0",
    "\u1680",
    "\u2000",
    "\u2001",
    "\u2002",
    "\u2003",
    "\u2004",
    "\u2005",
    "\u2006",
    "\u2007",
    "\u2008",
    "\u2009",
    "\u200a",
    "\u2028",
    "\u2029",
    "\u202f",
    "\u205f",
    "\u3000",
    "\ufeff",
]
PYTHON_ONLY_SPACES = ["\x85", "\x1c", "\x1d", "\x1e", "\x1f", "\u180e"]


@pytest.mark.parametrize("space", JS_SPACES, ids=[f"U+{ord(each):04X}" for each in JS_SPACES])
def test_a_space_her_javascript_counts_joins_the_words_of_a_hand_off(space: str) -> None:
    assert is_boundary_turn("validated", f"ao{space}consultor", opening=False) is True


@pytest.mark.parametrize(
    "space", PYTHON_ONLY_SPACES, ids=[f"U+{ord(each):04X}" for each in PYTHON_ONLY_SPACES]
)
def test_a_character_only_python_counts_as_a_space_does_not_join_them(space: str) -> None:
    assert is_boundary_turn("validated", f"ao{space}consultor", opening=False) is False


def test_the_guides_name_is_taken_out_across_a_space_only_her_javascript_counts() -> None:
    line = "pro facilitador\ufeffDIGITAL FACILITATOR"

    assert is_boundary_turn("validated", line, opening=False) is False
