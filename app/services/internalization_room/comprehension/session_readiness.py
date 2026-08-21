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
    EvidenceObservation,
    EvidenceResult,
    ReadinessEvaluation,
    ReopenedEvent,
    assess_unit,
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


def render_comprehension_status(
    *,
    checkpoints: list[Checkpoint],
    scene_ids: list[str],
    ledger: list[EvidenceEvent],
    practiced_scene_ids: list[str],
    current_scene: str | None = None,
) -> str:
    readiness = evaluate_session_comprehension(
        checkpoints=checkpoints,
        scene_ids=scene_ids,
        ledger=ledger,
        practiced_scene_ids=practiced_scene_ids,
    )
    supported = set(readiness.evaluation.supported_unit_ids)
    scope = [c for c in checkpoints if (c.scene_id == current_scene if current_scene else True)]

    def still_needed(checkpoint: Checkpoint) -> bool:
        if not checkpoint.critical or checkpoint.id in supported:
            return False
        assessment = assess_unit(ledger, checkpoint.id)
        return assessment.has_conflict or (
            EvidenceResult.CARRY_TO_REFINE not in assessment.open_results
        )

    next_units = [c.id for c in scope if still_needed(c)][:8]
    conflicts = [c.id for c in checkpoints if assess_unit(ledger, c.id).has_conflict][:8]
    open_points = [
        f"{point.unit_id} ({point.reason})" for point in readiness.evaluation.open_points
    ][:8]
    practiced_sorted = sorted(set(practiced_scene_ids))

    return "\n".join(
        [
            "COMPREHENSION EVIDENCE (APP-OWNED; separate from engagement and "
            "bridge-language fluency):",
            f"READINESS: {readiness.evaluation.outcome.value}",
            f"SUPPORTED SEMANTIC UNITS: {len(supported)} of {len(checkpoints)}",
            "NEXT UNITS IN SCOPE: " + ("; ".join(next_units) if next_units else "none"),
            "OPEN POINTS FOR REFINE: " + ("; ".join(open_points) if open_points else "none"),
            "CONFLICTS TO CLARIFY: " + ("; ".join(conflicts) if conflicts else "none"),
            "MOTHER-TONGUE PRACTICE REPORTED: "
            + (", ".join(practiced_sorted) if practiced_sorted else "none"),
            "MOTHER-TONGUE PRACTICE STILL NEEDED: "
            + (
                ", ".join(readiness.missing_practice_scene_ids)
                if readiness.missing_practice_scene_ids
                else "none"
            ),
            "Never voice internal unit IDs. Use the Meaning Map to ask about one natural, "
            "grounded point.",
        ]
    )


def events_for_observations(
    ledger: list[EvidenceEvent],
    observations: list[EvidenceObservation],
    *,
    conflict_resolution_checkpoint_ids: list[str] | None = None,
) -> list[EvidenceEvent]:
    """A later positive answer to the same checkpoint can resolve an earlier
    contradiction, but only by starting a new evidence epoch. History stays append-only
    for field review."""
    events: list[EvidenceEvent] = []
    working: list[EvidenceEvent] = list(ledger)
    may_resolve = set(conflict_resolution_checkpoint_ids or [])
    for item in observations:
        positive = item.result in (
            EvidenceResult.DEMONSTRATED,
            EvidenceResult.SUPPORTED_PROMPTED,
        )
        if (
            positive
            and item.unit_id in may_resolve
            and assess_unit(working, item.unit_id).has_conflict
        ):
            reopened = ReopenedEvent(
                id=f"{item.id}:reopen", unit_id=item.unit_id, reason="team_reconsidered"
            )
            events.append(reopened)
            working.append(reopened)
        events.append(item)
        working.append(item)
    return events
