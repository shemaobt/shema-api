"""What the room says back: the Guide speaks, or exact app-owned wording stands in for it."""

from __future__ import annotations

import math
from dataclasses import replace
from typing import Any

from app.core.config import Settings
from app.db.models.internalization_room import IRSession
from app.services.internalization_room.fail_safe import FailSafe, choose
from app.services.internalization_room.languages import LANGUAGE_NAMES
from app.services.internalization_room.run_turn import (
    TurnOutcome,
    run_turn,
)


def mother_tongue_note(language_code: str, take_ms: int | None) -> str:
    seconds = math.floor(take_ms / 1000 + 0.5) if take_ms else 0
    if language_code == "pt":
        held = f" por cerca de {seconds} segundos" if seconds else ""
        return (
            f"[A equipe falou na língua materna{held}; sem transcrição — nenhuma palavra "
            "chegou até você.]"
        )
    held = f" for about {seconds} seconds" if seconds else ""
    return f"[The team spoke in their own language{held}; no transcription — no words reached you.]"


async def speak_back(
    *,
    mother_tongue: bool,
    take_ms: int | None,
    session: IRSession,
    messages: list[dict[str, Any]],
    transcript: str,
    opening: bool,
    empty: bool,
    book: str,
    guide_prompt: str,
    validator_prompt: str,
    pericope: str,
    settings: Settings,
) -> TurnOutcome:
    if not opening and not mother_tongue and empty:
        line, fixed = choose(FailSafe.INAUDIBLE, session.language)
        return TurnOutcome(
            speech=line, transcript="", used_fail_safe=True, degraded=True, fixed_line=fixed
        )
    note = mother_tongue_note(session.language, take_ms) if mother_tongue else ""
    outcome = await run_turn(
        transcript=note or transcript,
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
        ask_for_movements=opening and not messages,
    )
    if note:
        return replace(outcome, transcript="", room_note=note)
    return outcome
