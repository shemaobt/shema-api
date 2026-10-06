"""What the room says back: the Guide speaks, or exact app-owned wording stands in for it."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from app.core.config import Settings
from app.db.models.internalization_room import IRSession
from app.services.internalization_room.fail_safe import inaudible_ladder
from app.services.internalization_room.languages import LANGUAGE_NAMES
from app.services.internalization_room.run_turn import (
    TurnOutcome,
    run_turn,
)


def mother_tongue_note(language_code: str, take_ms: float | None) -> str:
    """Her note for a take in the team's own language, verbatim (`src/turn/openingNote.ts`).

    The seconds are said as her note says a number: `2.5` stays `2.5` and `40` is never
    `40.0`. A take the tablet measured arrives already rounded to the second.
    """
    seconds = f"{take_ms / 1000:g}" if take_ms else ""
    if language_code == "pt":
        held = f" por cerca de {seconds} segundos" if seconds else ""
        return (
            f"[A equipe falou na língua materna{held}; sem transcrição — nenhuma palavra "
            "chegou até você.]"
        )
    held = f" for about {seconds} seconds" if seconds else ""
    return f"[The team spoke in their own language{held}; no transcription — no words reached you.]"


def interrupted_note(language_code: str) -> str:
    """Her note for a team that cut the Guide's previous reply short, verbatim."""
    if language_code == "pt":
        return "[A equipe interrompeu a sua fala anterior neste ponto.]"
    return "[The team interrupted your previous turn at this point.]"


async def speak_back(
    *,
    mother_tongue: bool,
    take_ms: float | None,
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
    interrupted: bool = False,
) -> TurnOutcome:
    """The Guide's reply to the team's turn, or the inaudible ladder's line in its place.

    The room's notes — the team cut the Guide short, the team spoke in the mother tongue —
    are handed to the Guide in front of the team's words, and come back as the room's, apart
    from them, so the conversation keeps them as the room's entry and only the team's words
    are ever settled. Words the recognizer made of a mother-tongue take never travel.

    A take with no words that is not the mother tongue is a miss, and draws the ladder's line
    whether or not it followed a cut: nothing reaches the Guide.
    """
    if not opening and not mother_tongue and empty:
        line, fixed = inaudible_ladder(messages, session.language)
        return TurnOutcome(
            speech=line, transcript="", used_fail_safe=True, degraded=True, fixed_line=fixed
        )
    words = "" if mother_tongue else transcript
    note = " ".join(
        part
        for part in (
            interrupted_note(session.language) if interrupted else "",
            mother_tongue_note(session.language, take_ms) if mother_tongue else "",
        )
        if part
    )
    outcome = await run_turn(
        transcript=" ".join(part for part in (note, words) if part),
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
        mother_tongue=mother_tongue,
        earlier_passages=session.earlier_passages,
    )
    if note:
        return replace(outcome, transcript=words, room_note=note)
    return outcome
