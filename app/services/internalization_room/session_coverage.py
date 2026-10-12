from __future__ import annotations

from app.db.models.internalization_room import IRSession
from app.models.internalization_room import (
    SessionCoverageBead,
    SessionCoverageGroup,
    SessionCoverageResponse,
)
from app.services.internalization_room.canon.elements import ElementKind, elements_for


def coverage_of(session: IRSession) -> SessionCoverageResponse:
    elements = elements_for(session.pericope)
    groups = []
    for kind in ElementKind:
        beads = [
            SessionCoverageBead(key=element.key, label=element.label)
            for element in elements
            if element.kind is kind
        ]
        if beads:
            groups.append(SessionCoverageGroup(kind=kind, beads=beads))
    return SessionCoverageResponse(session_id=session.id, groups=groups)
