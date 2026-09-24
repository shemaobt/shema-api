"""Her prompt files carry notes for a reader around the prompt, and only the body is the prompt.

Her `extractPromptBody` (`src/turn/prompts.ts:14-27`, byte-identical at 533b6e3, 17ba6fc and
a3f3c69) matches the first standalone BEGIN and END marker lines, optionally in backticks,
trims what sits between them, and throws on a missing marker or an empty body. Every prompt
her room loads goes through it, so the room reads hers the same way or it is not reading hers.
"""

from __future__ import annotations

import pytest

from app.services.internalization_room.prompt_body import extract_prompt_body

HER_SHAPE = """# System Prompt — Something

> **How to use it.** Everything between the `=== BEGIN SYSTEM PROMPT ===` and
> `=== END SYSTEM PROMPT ===` markers is the prompt.

`=== BEGIN SYSTEM PROMPT ===`

You are the facilitator.

Speak plainly.

`=== END SYSTEM PROMPT ===`

## Worked examples (not part of the prompt)
"""


def test_the_body_is_what_sits_between_the_standalone_marker_lines_trimmed() -> None:
    assert extract_prompt_body(HER_SHAPE, "guide") == "You are the facilitator.\n\nSpeak plainly."


def test_marker_lines_without_backticks_are_markers_too() -> None:
    text = "notes\n=== BEGIN SYSTEM PROMPT ===\n  body  \n=== END SYSTEM PROMPT ===\n"

    assert extract_prompt_body(text, "judge") == "body"


def test_the_first_standalone_pair_wins_when_a_marker_line_repeats() -> None:
    text = (
        "`=== BEGIN SYSTEM PROMPT ===`\nfirst\n`=== END SYSTEM PROMPT ===`\n"
        "`=== BEGIN SYSTEM PROMPT ===`\nsecond\n`=== END SYSTEM PROMPT ===`\n"
    )

    assert extract_prompt_body(text, "guide") == "first"


@pytest.mark.parametrize(
    "text",
    [
        "`=== BEGIN SYSTEM PROMPT ===`\nbody with no end\n",
        "body with no begin\n`=== END SYSTEM PROMPT ===`\n",
        "`=== END SYSTEM PROMPT ===`\nbackwards\n`=== BEGIN SYSTEM PROMPT ===`\n",
        "only an inline `=== BEGIN SYSTEM PROMPT ===` and `=== END SYSTEM PROMPT ===` mention\n",
    ],
)
def test_a_file_without_a_standalone_pair_in_order_is_refused_not_read_whole(text: str) -> None:
    with pytest.raises(ValueError, match="classifier: missing standalone BEGIN/END"):
        extract_prompt_body(text, "classifier")


def test_an_empty_body_is_refused_rather_than_sent_as_a_prompt_of_nothing() -> None:
    text = "`=== BEGIN SYSTEM PROMPT ===`\n   \n\n`=== END SYSTEM PROMPT ===`\n"

    with pytest.raises(ValueError, match="validator: empty system prompt body"):
        extract_prompt_body(text, "validator")
