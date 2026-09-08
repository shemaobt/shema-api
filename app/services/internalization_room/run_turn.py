from __future__ import annotations

import logging
from typing import Any

from app.core.config import Settings, get_settings
from app.core.exceptions import ValidationError
from app.services.internalization_room.bridge_language import strays_from
from app.services.internalization_room.fail_safe import FailSafe, choose
from app.services.internalization_room.languages import FLOOR, LANGUAGE_NAMES
from app.services.internalization_room.llm import call_agent
from app.services.internalization_room.peer_cue import detects_peer_cue
from app.services.internalization_room.prompt_blocks import (
    coverage_status_block,
    meaning_map_block,
)
from app.services.internalization_room.redraft_note import (
    _DESCRIBED_ISSUES_NOTE,
    _NO_ISSUES_NOTE,
    _OFF_BRIDGE_LANGUAGE_NOTE,
    _redraft_note,
)
from app.services.internalization_room.render import render
from app.services.internalization_room.turn_instructions import (
    ALREADY_MET_INSTRUCTION,
    OPENING_INSTRUCTION,
    OPENING_MOVEMENT_MARK,
    split_opening_movements,
)
from app.services.internalization_room.validated_turn import TurnOutcome, _voiced_after_validation

__all__ = [
    "OPENING_MOVEMENT_MARK",
    "_DESCRIBED_ISSUES_NOTE",
    "_NO_ISSUES_NOTE",
    "_OFF_BRIDGE_LANGUAGE_NOTE",
    "TurnOutcome",
    "_redraft_note",
    "call_agent",
    "detects_peer_cue",
    "split_opening_movements",
    "strays_from",
]

logger = logging.getLogger(__name__)

MAX_REDRAFTS = 2


async def run_turn(
    *,
    transcript: str,
    coverage_state: dict[str, str],
    messages: list[dict[str, Any]],
    guide_prompt: str,
    validator_prompt: str,
    pericope_num: str,
    book: str = "Ruth",
    session_language: str = LANGUAGE_NAMES[FLOOR],
    language_code: str = FLOOR,
    opening: bool = False,
    already_met: bool = False,
    settings: Settings | None = None,
    session_id: str = "?",
    app_context: str = "",
    validator_context: str = "",
    ask_for_movements: bool = False,
) -> TurnOutcome:
    """One exchange of a passage session: the Guide drafts, the Validator gates.

    `opening` is the session's first turn, where the Guide speaks before the team has.
    `app_context` rides inside the Guide's COVERAGE_STATUS slot and `validator_context`
    is appended to the Validator's system — both are app-owned state (bridge mode,
    comprehension evidence, the active probe contract), never team speech.
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

    map_block = meaning_map_block(pericope_num, book)
    coverage_status = coverage_status_block(coverage_state, pericope_num)
    if app_context:
        coverage_status = f"{coverage_status}\n\n{app_context}"
    return await _voiced_after_validation(
        speaker_system=render(
            guide_prompt,
            SESSION_LANGUAGE=session_language,
            MEANING_MAP=map_block,
            COVERAGE_STATUS=coverage_status,
        ),
        validator_prompt=validator_prompt,
        standard_of_truth=map_block,
        transcript=transcript,
        messages=messages,
        session_language=session_language,
        language_code=language_code,
        opening=opening,
        opening_instruction=(ALREADY_MET_INSTRUCTION if already_met else OPENING_INSTRUCTION),
        settings=cfg,
        session_id=session_id,
        validator_context=validator_context,
        ask_for_movements=ask_for_movements,
    )


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
            panorama_prompt,
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


#: The slot a stored prompt row must carry for the closing to reach the Speaker.
CLOSING_SLOT = "{{CLOSING}}"

#: The slots a stored Validator row must carry for the verdict's own context to reach it.
#: Their absence is how this failed the first time: `render` drops a value whose placeholder
#: is not in the template without a word, so the Validator went on judging a verdict it could
#: not see the evidence for, and the team heard a fail-safe line with nothing to say why.
VALIDATOR_CONTEXT_SLOTS = ("{{TELLING_BACK}}", "{{FINDING}}", "{{ORDERED_CLOSING}}")


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

    The Validator is handed the same three things the Speaker was: the finding, the telling-back
    and the closing it was ordered to end with. Without them it judged a draft that spoke of a
    telling-back against evidence saying nobody had spoken, and refused it — correctly, on what
    it had. This is stricter than what it replaced, not looser: a claim about the telling-back
    now has a record to be measured against, and a navigation instruction is legitimate only as
    far as the closing block goes.

    A missing slot is refused rather than rendered around, on both sides. A speaker prompt file
    saved before a slot existed would not carry it, and `render` drops a value whose placeholder
    is absent without a word — so the closing would never reach the Speaker and the turn would
    ask for a spoken answer while the screen waits for a tap, or the context would never reach
    the Validator and the verdict would fall to a fail-safe line in front of a team. Nothing
    anywhere would say so.
    """
    cfg = settings or get_settings()
    map_block = meaning_map_block(pericope_num, book)
    if CLOSING_SLOT not in speaker_prompt:
        raise ValidationError(
            f"The verdict speaker prompt has no {CLOSING_SLOT}: the closing would be dropped "
            "and the turn would ask for an answer the screen no longer collects"
        )
    absent = [slot for slot in VALIDATOR_CONTEXT_SLOTS if slot not in validator_prompt]
    if absent:
        raise ValidationError(
            f"The validator prompt has no {', '.join(absent)}: the verdict would be judged "
            "without the telling-back, the finding or the closing that was ordered, and a "
            "team would hear a fail-safe line instead of what was found"
        )

    spoken_closing = closing.format(session_language=session_language)

    return await _voiced_after_validation(
        speaker_system=render(
            speaker_prompt,
            SESSION_LANGUAGE=session_language,
            SCOPE=scope,
            MEANING_MAP=map_block,
            FINDINGS=findings_text,
            CLOSING=spoken_closing,
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
        finding=findings_text,
        ordered_closing=spoken_closing,
    )
