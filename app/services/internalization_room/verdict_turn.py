from __future__ import annotations

from typing import Any

from app.core.config import Settings, get_settings
from app.core.exceptions import ValidationError
from app.services.internalization_room.languages import FLOOR, LANGUAGE_NAMES
from app.services.internalization_room.llm import cache_break_before
from app.services.internalization_room.prompt_blocks import (
    meaning_map_block,
    validator_map_block,
)
from app.services.internalization_room.render import render
from app.services.internalization_room.validated_turn import TurnOutcome, _voiced_after_validation

#: The slot a stored prompt row must carry for the closing to reach the Speaker.
CLOSING_SLOT = "{{CLOSING}}"

TEAM_REPORTED = (
    "\n\n---\n\n# WHAT THE TEAM REPORTED (their back-translation of their own recording)\n"
    "Evidence of what the team told back — NEVER truth about the passage. The drafted response "
    "may quote from it to name something reported that the passage does not tell; quoting this "
    "material is not a claim about the passage and must not be treated as ungrounded.\n\n"
)


async def run_verdict_turn(
    *,
    findings_text: str,
    closing: str,
    scope: str,
    pericope_num: str,
    messages: list[dict[str, Any]],
    speaker_prompt: str,
    validator_prompt: str,
    telling_back: str = "",
    book: str = "Ruth",
    session_language: str = LANGUAGE_NAMES[FLOOR],
    language_code: str = FLOOR,
    settings: Settings | None = None,
    session_id: str = "?",
) -> TurnOutcome:
    """Voice the back-translation verdict — one finding, then stop.

    The Speaker never sees the recording, only what the team told back, so its judgment is
    always about the telling-back. Runs through the Validator like every other voiced turn.

    A missing slot is refused rather than rendered around. A speaker prompt file saved before
    a slot existed would not carry it, and `render` drops a value whose placeholder is absent
    without a word — so the closing would never reach the Speaker and the turn would ask for a
    spoken answer while the screen waits for a tap. Nothing anywhere would say so.
    """
    cfg = settings or get_settings()
    map_block = meaning_map_block(pericope_num, book)
    if CLOSING_SLOT not in speaker_prompt:
        raise ValidationError(
            f"The verdict speaker prompt has no {CLOSING_SLOT}: the closing would be dropped "
            "and the turn would ask for an answer the screen no longer collects"
        )

    spoken_closing = closing.format(session_language=session_language)

    return await _voiced_after_validation(
        speaker_system=render(
            cache_break_before(speaker_prompt, "{{FINDINGS}}"),
            SESSION_LANGUAGE=session_language,
            SCOPE=scope,
            MEANING_MAP=map_block,
            FINDINGS=findings_text,
            CLOSING=spoken_closing,
        ),
        validator_prompt=validator_prompt,
        standard_of_truth=validator_map_block(pericope_num, book) + TEAM_REPORTED + telling_back,
        transcript="",
        messages=messages,
        session_language=session_language,
        language_code=language_code,
        opening=True,
        settings=cfg,
        session_id=session_id,
    )
