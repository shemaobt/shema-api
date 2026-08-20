"""A team's necklace, bead by bead, for the facilitator's panel.

The opposite of `CoverageView`. That one answers four aggregate numbers, and the product
forbids putting any of them in front of a facilitator: a count invites comparing two teams,
and these teams are not in a race. This answers the beads themselves — named, typed, placed
in their scene, each carrying its own state and the session that last moved it.

Three sources meet here and each one owns exactly one part of the answer. The canon owns the
spine and its order. The label catalogue owns the words a facilitator reads. The events table
owns everything that is this particular team's. Nothing here recomputes another's part.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.models.internalization_room import ElementCoverage, TouchedInSession
from app.services.internalization_room.canon.labels import labelled_elements
from app.services.internalization_room.coverage import CoverageStatus
from app.services.internalization_room.coverage_events import necklace_with_touches


async def team_necklace(db: AsyncSession, *, team_id: str, pericope: str) -> list[ElementCoverage]:
    """Every element of one passage, as this team stands on it, in the canon's bead order.

    Raises `NotFoundError` when the passage has no labels written. The canon serves all
    fourteen of Ruth and the pilot has written labels for four, so a facilitator reaching P03
    through the Desk's selector has made a **well-formed** request for a representation this
    deploy cannot produce. `ValidationError` — which is answered 400 — would blame the caller
    for our gap and send somebody to debug their own code. Serving the bead with an empty
    label would be worse still: it puts `preserved:R3` in front of a facilitator, which is
    the one outcome the label catalogue exists to prevent.

    A catalogue that is present but holed stays `ElementLabelsBroken` and stays a 500. That
    is our file being wrong, not this passage being outside the pilot, and the two must not
    arrive at the same door.
    """
    try:
        beads = labelled_elements(pericope)
    except ValidationError as unwritten:
        raise NotFoundError(str(unwritten)) from unwritten

    history = await necklace_with_touches(db, project_id=team_id, pericope=pericope)
    return [
        ElementCoverage(
            key=bead.key,
            label_pt=bead.label_pt,
            label_en=bead.label_en,
            label_es=bead.label_es,
            kind=bead.kind,
            scene=bead.scene,
            status=(
                history[bead.key].status
                if bead.key in history
                else CoverageStatus.NOT_ENCOUNTERED.value
            ),
            touched_in_session=(
                TouchedInSession(session_id=history[bead.key].session_id, at=history[bead.key].at)
                if bead.key in history
                else None
            ),
        )
        for bead in beads
    ]
