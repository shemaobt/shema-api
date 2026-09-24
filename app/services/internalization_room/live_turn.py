"""The comprehension-aware passage turn.

The Guide speaks, or is bypassed entirely with exact app-owned speech where safety demands
fixed wording.

The room asks nothing about recording. It used to voice its own yes/no consent question
here and re-offer it every third turn the team kept working, which is the nag ENG-777 is
named after; what invites the rehearsal now is the Guide's own send-off, and the record
entry has been open the whole session, so the team decides when.

The Guide checks the retelling itself, item by item against the pinned map, with the whole
conversation in context. Nothing here tells it what it may say next.

The opening turn always belongs to the Guide, because the Voice must open the passage
before anything is asked of the team — frame first, elicit second.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.models.internalization_room import IRSession
from app.services.internalization_room.canon.parse_map import load_map
from app.services.internalization_room.comprehension.state import ComprehensionState
from app.services.internalization_room.hearing import HeardSpeech
from app.services.internalization_room.run_turn import TurnOutcome
from app.services.internalization_room.sessions import comprehension_of
from app.services.internalization_room.turn.scene_view import current_scene_id
from app.services.internalization_room.turn.speech import speak_back


@dataclass
class ComprehensionTurn:
    outcome: TurnOutcome
    state: ComprehensionState


async def run_comprehension_turn(
    db: AsyncSession,
    session: IRSession,
    *,
    speech: HeardSpeech,
    opening: bool,
    guide_prompt: str,
    validator_prompt: str,
    settings: Settings,
) -> ComprehensionTurn:
    """One comprehension turn: what was heard, and what the room says back.

    Only the session's very first line is told in two movements. A file-less POST on a session
    that has already spoken is a re-open, and repeating the panorama there would say the whole
    passage twice and pull the necklace apart again.
    """
    pericope = session.pericope
    book = load_map(pericope).book
    messages: list[dict[str, Any]] = list(session.messages or [])
    state = comprehension_of(session)

    transcript = speech.text
    uncertain = speech.uncertain
    mother_tongue = speech.mother_tongue
    empty = not transcript.strip()

    outcome = await speak_back(
        mother_tongue=mother_tongue,
        take_ms=speech.take_ms,
        session=session,
        messages=messages,
        transcript=transcript,
        opening=opening,
        empty=empty,
        uncertain=uncertain,
        book=book,
        guide_prompt=guide_prompt,
        validator_prompt=validator_prompt,
        pericope=pericope,
        settings=settings,
    )

    return ComprehensionTurn(outcome=outcome, state=state)


__all__ = ["ComprehensionTurn", "current_scene_id", "run_comprehension_turn"]
