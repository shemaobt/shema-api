"""What the room says back: the Guide speaks, or exact app-owned wording stands in for it."""

from __future__ import annotations

from typing import Any

from app.core.config import Settings
from app.db.models.internalization_room import IRSession
from app.services.internalization_room.fail_safe import FailSafe, choose, inaudible_ladder
from app.services.internalization_room.languages import LANGUAGE_NAMES
from app.services.internalization_room.run_turn import (
    TurnOutcome,
    run_turn,
)


async def speak_back(
    *,
    mother_tongue: bool,
    session: IRSession,
    messages: list[dict[str, Any]],
    transcript: str,
    opening: bool,
    empty: bool,
    uncertain: bool,
    book: str,
    guide_prompt: str,
    validator_prompt: str,
    pericope: str,
    settings: Settings,
    app_context: str,
) -> TurnOutcome:
    if mother_tongue:
        line, fixed = choose(FailSafe.OFF_BRIDGE_LANGUAGE, session.language, turn=len(messages))
        outcome = TurnOutcome(
            speech=line, transcript=transcript, used_fail_safe=True, fixed_line=fixed
        )
    elif not opening and (empty or uncertain):
        line, fixed = inaudible_ladder(messages, session.language)
        outcome = TurnOutcome(
            speech=line,
            transcript=transcript,
            used_fail_safe=True,
            degraded=True,
            fixed_line=fixed,
        )
    else:
        outcome = await run_turn(
            transcript=transcript,
            coverage_state=session.coverage_state or {},
            messages=messages,
            session_language=LANGUAGE_NAMES[session.language],
            language_code=session.language,
            guide_prompt=guide_prompt,
            validator_prompt=validator_prompt,
            pericope_num=pericope,
            book=book,
            opening=opening,
            settings=settings,
            session_id=session.id,
            app_context=app_context,
            ask_for_movements=opening and not messages,
        )
    return outcome
