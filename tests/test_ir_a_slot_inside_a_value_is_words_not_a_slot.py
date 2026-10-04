"""What the prompt filler does with a value that looks like one of its own slots.

The team's words and the models' replies are quoted into the prompts as values. A value
that carried `{{MEANING_MAP}}` used to survive the sequential fill, be found by the
unfilled-slot check, and turn a turn into a raised error the tablet read as a broken room.
"""

import pytest

from app.core.exceptions import ValidationError
from app.services.internalization_room.render import render


def test_a_slot_quoted_inside_a_value_is_left_as_words() -> None:
    filled = render(
        "Team said: {{TEAM_UTTERANCE}}\nMap: {{MEANING_MAP}}",
        TEAM_UTTERANCE="what is {{MEANING_MAP}}?",
        MEANING_MAP="Ruth 1:1-5",
    )

    assert filled == "Team said: what is {{MEANING_MAP}}?\nMap: Ruth 1:1-5"


def test_a_value_is_never_read_as_a_template_for_a_later_slot() -> None:
    filled = render("{{FIRST}} {{SECOND}}", FIRST="{{SECOND}}", SECOND="two")

    assert filled == "{{SECOND}} two"


def test_a_slot_the_caller_did_not_fill_is_still_refused() -> None:
    with pytest.raises(ValidationError) as refused:
        render("{{A}} {{B}}", A="one")

    assert "B" in str(refused.value)
