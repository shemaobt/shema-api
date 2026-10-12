from __future__ import annotations

from app.core.room_enums import CoverageStatus
from app.db.models.internalization_room import IRSession
from app.models.internalization_room import (
    BeadState,
    SessionCoverageBead,
    SessionCoverageGroup,
    SessionCoverageResponse,
)
from app.services.internalization_room.canon.elements import ElementKind, elements_for
from app.services.internalization_room.coverage import initial_state

_STATE_OF = {
    CoverageStatus.ENGAGED: BeadState.ENGAGED,
    CoverageStatus.SURFACED: BeadState.SURFACED,
    CoverageStatus.PARTIALLY_ENGAGED: BeadState.SURFACED,
    CoverageStatus.NOT_ENCOUNTERED: BeadState.UNTOUCHED,
}


def coverage_of(session: IRSession) -> SessionCoverageResponse:
    elements = elements_for(session.pericope)
    stored = {**initial_state(session.pericope), **(session.coverage_state or {})}
    groups = []
    for kind in ElementKind:
        beads = [
            SessionCoverageBead(
                key=element.key,
                label=element.label,
                state=_STATE_OF[CoverageStatus(stored[element.key])],
            )
            for element in elements
            if element.kind is kind
        ]
        if beads:
            groups.append(SessionCoverageGroup(kind=kind, beads=beads))
    return SessionCoverageResponse(session_id=session.id, groups=groups)
