"""Session-level readiness over the ledger plus the mother-tongue practice record.

Consent remains a separate, exact spoken handoff cue: this evaluation answers whether
semantic/process evidence is ready for the Voice to ask that final consent question.
Ported from ``src/comprehension/sessionReadiness.ts``.
"""

from __future__ import annotations

from pydantic import BaseModel

from app.services.internalization_room.comprehension.checkpoints import Checkpoint
from app.services.internalization_room.comprehension.evidence import (
    ComprehensionUnit,
    EvidenceEvent,
    ReadinessEvaluation,
    evaluate_readiness,
)


class SessionComprehension(BaseModel):
    evaluation: ReadinessEvaluation
    all_scenes_practiced_in_mother_tongue: bool
    missing_practice_scene_ids: list[str]


def evaluate_session_comprehension(
    *,
    checkpoints: list[Checkpoint],
    scene_ids: list[str],
    ledger: list[EvidenceEvent],
    practiced_scene_ids: list[str],
) -> SessionComprehension:
    """Readiness over the ledger and the mother-tongue practice the team actually reported."""
    practiced = set(practiced_scene_ids)
    missing = [scene_id for scene_id in scene_ids if scene_id not in practiced]
    all_practiced = bool(scene_ids) and not missing
    return SessionComprehension(
        evaluation=evaluate_readiness(
            ledger,
            units=[ComprehensionUnit(id=c.id, critical=c.critical) for c in checkpoints],
            all_scenes_practiced_in_mother_tongue=all_practiced,
            team_wants_to_proceed=True,
        ),
        all_scenes_practiced_in_mother_tongue=all_practiced,
        missing_practice_scene_ids=missing,
    )
