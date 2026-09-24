"""The durable comprehension side of a session, serialized into one JSON column.

Follows the ``BackTranslationState`` pattern: a Pydantic model the service folds and
saves whole. It is session-local by design — never a proficiency score, and discarded
with the session.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.services.internalization_room.comprehension.evidence import EvidenceEvent


class ComprehensionState(BaseModel):
    ledger: list[EvidenceEvent] = Field(default_factory=list)
    practiced_scene_ids: list[str] = Field(default_factory=list)
    invited_scene_id: str | None = None
