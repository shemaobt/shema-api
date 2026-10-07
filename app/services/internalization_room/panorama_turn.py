from __future__ import annotations

from typing import Any

from app.core.config import Settings, get_settings
from app.services.internalization_room.hearing import HeardSpeech
from app.services.internalization_room.languages import FLOOR, LANGUAGE_NAMES
from app.services.internalization_room.llm import cache_break_at_end
from app.services.internalization_room.render import render
from app.services.internalization_room.turn.speech import (
    a_miss,
    stamped_with_what_was_heard,
    what_the_guide_is_handed,
)
from app.services.internalization_room.turn_instructions import panorama_note
from app.services.internalization_room.validated_turn import TurnOutcome, _voiced_after_validation


async def run_panorama_turn(
    *,
    speech: HeardSpeech,
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
    ask_for_movements: bool = False,
) -> TurnOutcome:
    """One exchange of a Book Panorama — the session before a book's first passage.

    No coverage spine: a panorama never completes. The team has not lived any passage yet,
    so every one of the book's withholdings is still ahead of them.

    ``speech`` is what the room heard of the take, and the take is read by the passage's rule
    (`turn.speech.what_the_guide_is_handed`): a short take with no words draws the ladder's
    line, and the mother tongue reaches the Guide as the room's note, apart from the team's
    words, so the Validator never reads it as the team's own speech. On every turn but the
    opening the outcome keeps the language, its probability, the mother-tongue decision and the
    take's length; the cut point is not kept.
    """
    cfg = settings or get_settings()
    handed = what_the_guide_is_handed(
        language_code=language_code,
        opening=opening,
        words=speech.text,
        mother_tongue=speech.mother_tongue,
        take_ms=speech.take_ms,
        interrupted=speech.interrupted,
    )
    if handed is None:
        outcome = a_miss(messages, language_code)
    else:
        outcome = handed.kept_apart(
            await _voiced_after_validation(
                speaker_system=render(
                    cache_break_at_end(panorama_prompt),
                    BOOK_NAME=book,
                    SESSION_LANGUAGE=session_language,
                    BOOK_MATERIAL=book_material,
                ),
                validator_prompt=validator_prompt,
                standard_of_truth=book_material,
                transcript=handed.spoken_to_the_guide,
                messages=messages,
                session_language=session_language,
                language_code=language_code,
                opening=opening,
                opening_instruction=panorama_note(book, language_code),
                settings=cfg,
                session_id=session_id,
                ask_for_movements=ask_for_movements,
                mother_tongue=speech.mother_tongue,
            )
        )
    if not opening:
        return stamped_with_what_was_heard(outcome, speech)
    return outcome
