"""The comprehension-aware passage turn.

Order matters — this is the state machine the handoff document calls "app-owned": resolve
the bridge mode (explicit switches only), read what the team's telling settles about
practice, and only then let the Guide speak — or bypass it entirely with exact app-owned
speech where safety demands fixed wording.

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
from app.services.internalization_room.comprehension.practice import (
    scenes_practiced_by_the_telling_the_guide_invited,
)
from app.services.internalization_room.comprehension.probe import (
    select_probe_after_oral_turn,
)
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
    """One comprehension turn: what was heard, what it settles, and what the room says back.

    Only the session's very first line is told in two movements. A file-less POST on a session
    that has already spoken is a re-open, and repeating the panorama there would say the whole
    passage twice and pull the necklace apart again.
    """
    pericope = session.pericope
    book = load_map(pericope).book
    messages: list[dict[str, Any]] = list(session.messages or [])
    last_guide = next(
        (m.get("text", "") for m in reversed(messages) if m.get("role") == "guide"), ""
    )
    state = comprehension_of(session)
    prior_probe = state.active_probe

    transcript = speech.text
    uncertain = speech.uncertain
    mother_tongue = speech.mother_tongue
    empty = not transcript.strip()
    reliable = not uncertain and not mother_tongue

    scene_pointer = current_scene_id(session.coverage_state or {}, pericope, messages)
    practiced_now = scenes_practiced_by_the_telling_the_guide_invited(
        prior_probe, last_guide, transcript, reliable, scene_pointer
    )
    projected_practice = list(dict.fromkeys([*state.practiced_scene_ids, *practiced_now]))

    outcome = await speak_back(
        mother_tongue=mother_tongue,
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

    final_probe = select_probe_after_oral_turn(
        outcome="fail_safe" if outcome.used_fail_safe else "pass",
        prior_probe=prior_probe,
        next_probe=None,
        transcript_uncertain=uncertain,
        transcript_was_mother_tongue=mother_tongue,
        transcript_empty=empty,
    )

    new_state = ComprehensionState(
        ledger=state.ledger,
        active_probe=final_probe,
        practiced_scene_ids=projected_practice,
    )
    return ComprehensionTurn(outcome=outcome, state=new_state)


__all__ = ["ComprehensionTurn", "current_scene_id", "run_comprehension_turn"]
