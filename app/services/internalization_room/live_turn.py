"""The passage turn.

The Guide speaks, or is bypassed entirely with exact app-owned speech where safety demands
fixed wording. Nothing the Guide or the team says is read here for practice, an invitation
or a probe: her room tracks none of them, and the voice decides from the conversation.

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

from dataclasses import replace
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.models.internalization_room import IRSession
from app.services.internalization_room.canon.parse_map import load_map
from app.services.internalization_room.hearing import HeardSpeech
from app.services.internalization_room.run_turn import TurnOutcome
from app.services.internalization_room.turn.scene_view import current_scene_id
from app.services.internalization_room.turn.speech import speak_back, stamped_with_what_was_heard
from app.services.internalization_room.validated_turn import CutPoint


async def run_comprehension_turn(
    db: AsyncSession,
    session: IRSession,
    *,
    speech: HeardSpeech,
    opening: bool,
    guide_prompt: str,
    validator_prompt: str,
    settings: Settings,
) -> TurnOutcome:
    """One passage turn: what was heard, and what the room says back.

    Every turn but the opening carries what the room heard on its outcome — the language, its
    probability, the mother-tongue decision and the take's length — so the record keeps them.
    The opening has no take, and an outcome that names none is one the room did not hear.
    """
    pericope = session.pericope
    book = load_map(pericope).book
    messages: list[dict[str, Any]] = list(session.messages or [])
    outcome = await speak_back(
        mother_tongue=speech.mother_tongue,
        take_ms=speech.take_ms,
        interrupted=speech.interrupted,
        session=session,
        messages=messages,
        transcript=speech.text,
        opening=opening,
        book=book,
        guide_prompt=guide_prompt,
        validator_prompt=validator_prompt,
        pericope=pericope,
        settings=settings,
    )
    if not opening:
        outcome = replace(
            stamped_with_what_was_heard(outcome, speech),
            interrupted=(
                CutPoint(speech.interrupted_at_ms, speech.interrupted_of_ms)
                if speech.interrupted
                else None
            ),
        )
    return outcome


__all__ = ["current_scene_id", "run_comprehension_turn"]
