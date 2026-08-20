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

    Raises `NotFoundError` for a passage name the canon never had. That is the only refusal
    left here: a passage the pilot has not translated is **served**, from the canon, with
    `label_pt` and `label_es` absent — ENG-442's decision, and the reason this no longer
    refuses P03. Answering it 400 instead would blame the caller for a name the book does not
    hold being indistinguishable from a name it does; 404 is the same word the team gate uses
    above it, which is what keeps a stranger from telling the two apart.

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
                history[bead.key].status if bead.key in history else CoverageStatus.NOT_ENCOUNTERED
            ),
            touched_in_session=(
                TouchedInSession(session_id=history[bead.key].session_id, at=history[bead.key].at)
                if bead.key in history
                else None
            ),
        )
        for bead in beads
    ]
