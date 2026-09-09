from __future__ import annotations

from typing import Any

from app.core.config import Settings, get_settings
from app.services.internalization_room.fail_safe import FailSafe, choose
from app.services.internalization_room.languages import FLOOR, LANGUAGE_NAMES
from app.services.internalization_room.llm import cache_break_at_end
from app.services.internalization_room.render import render
from app.services.internalization_room.turn_instructions import OPENING_INSTRUCTION
from app.services.internalization_room.validated_turn import TurnOutcome, _voiced_after_validation


async def run_panorama_turn(
    *,
    transcript: str,
    messages: list[dict[str, Any]],
    panorama_prompt: str,
    validator_prompt: str,
    book: str,
    book_material: str,
    session_language: str = LANGUAGE_NAMES[FLOOR],
    language_code: str = FLOOR,
    opening: bool = False,
    settings: Settings | None = None,
    session_id: str = "?",
    validator_context: str = "",
    ask_for_movements: bool = False,
) -> TurnOutcome:
    """One exchange of a Book Panorama — the session before a book's first passage.

    No coverage spine: a panorama never completes. The team has not lived any passage yet,
    so every one of the book's withholdings is still ahead of them.
    """
    cfg = settings or get_settings()

    if not opening and not transcript.strip():
        speech, line = choose(FailSafe.INAUDIBLE, language_code, turn=len(messages))
        return TurnOutcome(
            speech=speech,
            transcript="",
            used_fail_safe=True,
            degraded=True,
            fixed_line=line,
        )

    return await _voiced_after_validation(
        speaker_system=render(
            cache_break_at_end(panorama_prompt),
            BOOK_NAME=book,
            SESSION_LANGUAGE=session_language,
            BOOK_MATERIAL=book_material,
        ),
        validator_prompt=validator_prompt,
        standard_of_truth=book_material,
        transcript=transcript,
        messages=messages,
        session_language=session_language,
        language_code=language_code,
        opening=opening,
        opening_instruction=OPENING_INSTRUCTION,
        settings=cfg,
        session_id=session_id,
        validator_context=validator_context,
        ask_for_movements=ask_for_movements,
    )
