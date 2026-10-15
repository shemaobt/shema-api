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
PYTHON_ONLY_SPACES = ["\x85", "\x1c", "\x1d", "\x1e", "\x1f"]
SPACES_IN_NEITHER_ENGINE = ["\u180e"]


@pytest.mark.parametrize("space", JS_SPACES, ids=[f"U+{ord(each):04X}" for each in JS_SPACES])
def test_a_space_her_javascript_counts_joins_the_words_of_a_hand_off(space: str) -> None:
    assert is_boundary_turn("validated", f"ao{space}consultor", opening=False) is True


@pytest.mark.parametrize(
    "space", PYTHON_ONLY_SPACES, ids=[f"U+{ord(each):04X}" for each in PYTHON_ONLY_SPACES]
)
def test_a_character_only_python_counts_as_a_space_does_not_join_them(space: str) -> None:
    assert is_boundary_turn("validated", f"ao{space}consultor", opening=False) is False


@pytest.mark.parametrize(
    "space",
    SPACES_IN_NEITHER_ENGINE,
    ids=[f"U+{ord(each):04X}" for each in SPACES_IN_NEITHER_ENGINE],
)
def test_a_character_that_is_a_space_in_neither_engine_does_not_join_them(space: str) -> None:
    assert is_boundary_turn("validated", f"ao{space}consultor", opening=False) is False


def test_the_guides_name_is_taken_out_across_a_space_only_her_javascript_counts() -> None:
    line = "pro facilitador\ufeffDIGITAL FACILITATOR"

    assert is_boundary_turn("validated", line, opening=False) is False


@pytest.mark.parametrize(
    "line",
    [
        pytest.param("the human consultant\xc3O?", id="capital-glued-after"),
        pytest.param("the human consultant\xe3o", id="small-glued-after"),
        pytest.param("ao consultor\xc9", id="capital-e-glued-after"),
        pytest.param("\xc3ao consultor", id="capital-glued-before"),
        pytest.param("\xe9ao consultor", id="small-e-glued-before"),
        pytest.param("ao consultor\u0663", id="arabic-indic-digit-glued-after"),
        pytest.param("ao consultor\u03b1", id="greek-letter-glued-after"),
        pytest.param("pro facilitador\xe3o", id="hers-pro-facilitador-glued"),
    ],
)
def test_a_letter_beyond_ascii_glued_to_a_hand_off_is_not_part_of_its_word(line: str) -> None:
    assert is_boundary_turn("validated", line, opening=False) is True


@pytest.mark.parametrize(
    "line",
    [
        pytest.param("ao consultors", id="ascii-letter-after"),
        pytest.param("xao consultor", id="ascii-letter-before"),
        pytest.param("ao consultor_", id="underscore-after"),
        pytest.param("ao consultor9", id="ascii-digit-after"),
    ],
)
def test_an_ascii_word_character_glued_to_a_hand_off_still_hides_it(line: str) -> None:
    assert is_boundary_turn("validated", line, opening=False) is False


def test_the_guides_name_is_taken_out_when_a_letter_beyond_ascii_follows_it() -> None:
    line = "pro facilitador digital\xc3o"

    assert is_boundary_turn("validated", line, opening=False) is False


def test_the_guides_name_is_not_taken_out_when_an_ascii_letter_follows_it() -> None:
    line = "pro facilitador digitals"

    assert is_boundary_turn("validated", line, opening=False) is True


@pytest.mark.parametrize(
    "line",
    [
        pytest.param("ao con\u017fultor", id="long-s-for-s"),
        pytest.param("AO CON\u017fULTOR", id="long-s-for-s-in-capitals"),
        pytest.param("pro fac\u0131litador", id="dotless-i-for-i"),
        pytest.param("pro fac\u0130litador", id="dotted-capital-i-for-i"),
    ],
)
def test_a_letter_her_javascript_does_not_fold_into_an_ascii_one_does_not_spell_a_hand_off(
    line: str,
) -> None:
    assert is_boundary_turn("validated", line, opening=False) is False


@pytest.mark.parametrize(
    "line",
    [
        pytest.param("ao consultor\u212a", id="kelvin-sign-after"),
        pytest.param("ao consultor\u017f", id="long-s-after"),
        pytest.param("ao consultor\u0131", id="dotless-i-after"),
        pytest.param("ao consultor\u0130", id="dotted-capital-i-after"),
        pytest.param("\u212aao consultor", id="kelvin-sign-before"),
    ],
)
def test_a_letter_her_javascript_does_not_fold_is_not_a_word_character_beside_a_hand_off(
    line: str,
) -> None:
    assert is_boundary_turn("validated", line, opening=False) is True


def test_the_guides_name_is_taken_out_when_a_kelvin_sign_follows_it() -> None:
    line = "pro facilitador digital\u212a"

    assert is_boundary_turn("validated", line, opening=False) is False
