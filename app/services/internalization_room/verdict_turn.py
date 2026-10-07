from __future__ import annotations

from typing import Any

from app.core.config import Settings, get_settings
from app.services.internalization_room.languages import FLOOR, LANGUAGE_NAMES
from app.services.internalization_room.llm import cache_break_before
from app.services.internalization_room.prompt_blocks import validator_map_block
from app.services.internalization_room.render import render
from app.services.internalization_room.validated_turn import TurnOutcome, _voiced_after_validation


async def run_verdict_turn(
    *,
    findings_text: str,
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
    """
    cfg = settings or get_settings()
    map_block = validator_map_block(pericope_num, book)
    return await _voiced_after_validation(
        speaker_system=render(
            cache_break_before(speaker_prompt, "{{FINDINGS}}"),
            SESSION_LANGUAGE=session_language,
            SCOPE=scope,
            MEANING_MAP=map_block,
            FINDINGS=findings_text,
        ),
        validator_prompt=validator_prompt,
        standard_of_truth=map_block,
        transcript="",
        messages=messages,
        session_language=session_language,
        language_code=language_code,
        opening=True,
        settings=cfg,
        session_id=session_id,
        telling_back=telling_back,
    )
