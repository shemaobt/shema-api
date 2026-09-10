"""The durable comprehension side of a session, serialized into one JSON column.

Follows the ``BackTranslationState`` pattern: a Pydantic model the service folds and
saves whole. It is session-local by design — never a proficiency score, and discarded
with the session.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.services.internalization_room.comprehension.evidence import EvidenceEvent
from app.services.internalization_room.comprehension.probe import ActiveProbe


class ComprehensionState(BaseModel):
    ledger: list[EvidenceEvent] = Field(default_factory=list)
    active_probe: ActiveProbe | None = None
    practiced_scene_ids: list[str] = Field(default_factory=list)
    recording_handoff_paused: bool = False
    recording_handoff_paused_turns: int = 0
