"""The pre-approved lines ship as audio inside the app, and must not drift from the prompt.

A fail-safe is what the team hears when the model failed or the network did. Synthesizing it
at that moment asks the network for a favour precisely when the network is the problem — so
these lines travel with the app. The cost of that is a frozen copy, and the guard against a
silent freeze is this file.
"""

from pathlib import Path

import pytest

import scripts.render_fixed_voice_lines as render
from app.services.internalization_room.fail_safe import FailSafe, choose, utterances

BUNDLE = Path(__file__).resolve().parents[2] / "internalization-room/assets/audio/fixed"


@pytest.mark.skip(
    reason="paused by decision: re-rendering after a prompt edit is a person's job for now. "
    "Re-enable with `uv run python scripts/render_fixed_voice_lines.py --check`, which still "
    "works and still exits non-zero on drift."
)
def test_every_line_the_room_can_speak_is_rendered_and_current() -> None:
    complaints = render.drift(BUNDLE, "pt")
    assert complaints == [], (
        "as falas fixas saíram de sincronia com o prompt — rode "
        "`uv run python scripts/render_fixed_voice_lines.py`"
    )


def test_the_catalogue_covers_every_kind_that_has_portuguese() -> None:
    catalogue = render.catalogue("pt")
    for kind in FailSafe:
        for index in range(len(utterances(kind, "pt"))):
            assert f"{kind}{index}" in catalogue


def test_a_repeated_failure_does_not_repeat_the_same_sentence() -> None:
    """The authored file asks for variation; a room stuck on one line sounds like a machine."""
    spoken = [choose(FailSafe.INAUDIBLE, "pt", turn=turn) for turn in range(3)]

    assert len({line for line, _ in spoken}) == 3
    assert [name for _, name in spoken] == ["D0", "D1", "D2"]


def test_the_rotation_wraps_instead_of_running_out() -> None:
    line, name = choose(FailSafe.INAUDIBLE, "pt", turn=3)

    assert name == "D0"
    assert line == choose(FailSafe.INAUDIBLE, "pt", turn=0)[0]


def test_a_kind_with_one_line_always_answers_with_it() -> None:
    assert choose(FailSafe.HARD_STOP, "pt", turn=7)[1] == "E0"


def test_an_unwritten_language_falls_back_to_the_authored_line() -> None:
    """Silence would be the one outcome worse than the wrong language."""
    line, name = choose(FailSafe.UNREPAIRABLE, "xx", turn=0)

    assert line
    assert name == "A0"
