"""The durable comprehension side of a session, serialized into one JSON column.

Follows the ``BackTranslationState`` pattern: a Pydantic model the service folds and
saves whole. It is session-local by design — never a proficiency score, and discarded
with the session. ``bridge_mode`` itself lives in its own column so intake validation and
inheritance stay queryable.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.services.internalization_room.comprehension.evidence import EvidenceEvent
from app.services.internalization_room.comprehension.probe import ActiveProbe
from app.services.internalization_room.comprehension.probe_plan import NoUsableReportAttempt
from app.services.internalization_room.comprehension.stt_recovery import SttRecoveryState


class ComprehensionState(BaseModel):
    ledger: list[EvidenceEvent] = Field(default_factory=list)
    active_probe: ActiveProbe | None = None
    practiced_scene_ids: list[str] = Field(default_factory=list)
    adaptive_free_retell_attempted: bool = False
    no_report_attempts: list[NoUsableReportAttempt] = Field(default_factory=list)
    stt_recovery: SttRecoveryState | None = None
    recording_consent_given: bool = False
    recording_handoff_paused: bool = False
    recording_handoff_paused_turns: int = 0
