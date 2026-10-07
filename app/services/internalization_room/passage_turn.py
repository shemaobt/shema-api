from __future__ import annotations

from typing import Any

from app.core.config import Settings, get_settings
from app.services.internalization_room.fail_safe import inaudible_ladder
from app.services.internalization_room.languages import FLOOR, LANGUAGE_NAMES
from app.services.internalization_room.llm import cache_break_before
from app.services.internalization_room.prompt_blocks import (
    coverage_status_block,
    earlier_passages_line,
    meaning_map_block,
    validator_map_block,
)
from app.services.internalization_room.render import render
from app.services.internalization_room.turn_instructions import opening_note
from app.services.internalization_room.validated_turn import TurnOutcome, _voiced_after_validation


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
    settings: Settings | None = None,
    session_id: str = "?",
    ask_for_movements: bool = False,
    prepared_pericope: str | None = None,
    earlier_passages: dict[str, str] | None = None,
) -> TurnOutcome:
    """One exchange of a passage session: the Guide drafts, the Validator gates.

    `opening` is the session's first turn, where the Guide speaks before the team has.
    The coverage block is the whole of what the app tells the Guide, and the Validator is
    handed none of it — it judges the draft against the map and the team's own words, or, on
    a take in the mother tongue, the room's note that stands for them.

    `prepared_pericope` names this call as `prepare_opening`'s own background run, so the
    `[llm-turn]` line can say which pericope it wrote ahead for. It is set nowhere else:
    a live turn's `session_id` is that session's own, but a prepared one runs under the
    panorama's, and without the tag the two are indistinguishable in the log (ENG-968,
    ENG-1107).

    `earlier_passages` is the session's stamp of this team's status on the earlier passages;
    its fact line rides beside the coverage block, after the cache break, as in her app.
    """
    cfg = settings or get_settings()

    if not opening and not transcript.strip():
        speech, line = inaudible_ladder(messages, language_code)
        return TurnOutcome(
            speech=speech,
            transcript="",
            used_fail_safe=True,
            degraded=True,
            fixed_line=line,
        )

    map_block = meaning_map_block(pericope_num, book, earlier_passages)
    earlier = earlier_passages_line(pericope_num, book, earlier_passages)
    coverage_status = "\n\n".join(
        block for block in (coverage_status_block(coverage_state, pericope_num), earlier) if block
    )
    return await _voiced_after_validation(
        speaker_system=render(
            cache_break_before(guide_prompt, "{{COVERAGE_STATUS}}"),
            SESSION_LANGUAGE=session_language,
            MEANING_MAP=map_block,
            COVERAGE_STATUS=coverage_status,
        ),
        validator_prompt=validator_prompt,
        standard_of_truth=validator_map_block(pericope_num, book, earlier_passages),
        transcript=transcript,
        messages=messages,
        session_language=session_language,
        language_code=language_code,
        opening=opening,
        opening_instruction=opening_note(pericope_num, language_code),
        settings=cfg,
        session_id=session_id,
        ask_for_movements=ask_for_movements,
        prepared_pericope=prepared_pericope,
        earlier_passages=earlier,
    )
