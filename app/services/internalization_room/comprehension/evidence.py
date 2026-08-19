"""Session-local comprehension evidence ledger and readiness rule.

``demonstrated`` means the semantic content appeared without an answer-revealing cue.
``supported_prompted`` is useful but weaker evidence: the team selected or confirmed the
content after structured support. The remaining values are explicit limits or open
questions, never synonyms for "the team did not understand".

The ledger is append-only. Reopening creates a new assessment epoch for one unit: earlier
observations remain in history for audit, but readiness uses only evidence recorded after
the latest reopen — which is how a later contradiction genuinely reopens a previously
supported unit. Ported from the reference prototype's ``src/comprehension/evidence.ts``.
"""

from __future__ import annotations

import enum
from typing import Annotated, Literal

from pydantic import BaseModel, Field

from app.core.exceptions import ValidationError


class EvidenceMethod(enum.StrEnum):
    FREE_BRIDGE_RETELL = "free_bridge_retell"
    MICRO_TELLBACK = "micro_tellback"
    TRUE_EVENT_SEQUENCE = "true_event_sequence"
    ROLE_OR_PLACE_CHOICE = "role_or_place_choice"
    SIGNIFICANT_ABSENCE_CHECK = "significant_absence_check"
    PEER_CONFIRMATION = "peer_confirmation"


class EvidenceResult(enum.StrEnum):
    DEMONSTRATED = "demonstrated"
    SUPPORTED_PROMPTED = "supported_prompted"
    UNCLEAR_DUE_BRIDGE = "unclear_due_bridge"
    STT_UNCERTAIN = "stt_uncertain"
    CONFLICT = "conflict"
    CARRY_TO_REFINE = "carry_to_refine"


OPEN_RESULTS = frozenset(
    {
        EvidenceResult.UNCLEAR_DUE_BRIDGE,
        EvidenceResult.STT_UNCERTAIN,
        EvidenceResult.CARRY_TO_REFINE,
    }
)


class EvidenceObservation(BaseModel):
    kind: Literal["evidence"] = "evidence"
    id: str
    unit_id: str
    probe_id: str
    method: EvidenceMethod
    result: EvidenceResult
    respondent_slot: str | None = None
    note: str | None = None


class ReopenedEvent(BaseModel):
    kind: Literal["reopened"] = "reopened"
    id: str
    unit_id: str
    reason: Literal["later_conflict", "team_reconsidered", "new_recording", "validator_request"]


EvidenceEvent = Annotated[EvidenceObservation | ReopenedEvent, Field(discriminator="kind")]


class SupportLevel(enum.StrEnum):
    NONE = "none"
    PROMPTED = "prompted"
    DEMONSTRATED = "demonstrated"


class UnitAssessment(BaseModel):
    unit_id: str
    status: str
    support: SupportLevel
    prompted_methods: list[EvidenceMethod]
    open_results: list[EvidenceResult]
    has_conflict: bool
    active_evidence: list[EvidenceObservation]


def append_evidence(
    events: list[EvidenceEvent], observation: EvidenceObservation
) -> list[EvidenceEvent]:
    _assert_new_id(events, observation.id, observation.unit_id)
    if not observation.probe_id.strip():
        raise ValidationError("Evidence observation needs a probe id")
    return [*events, observation]


def append_reopened(events: list[EvidenceEvent], reopened: ReopenedEvent) -> list[EvidenceEvent]:
    _assert_new_id(events, reopened.id, reopened.unit_id)
    return [*events, reopened]


def _assert_new_id(events: list[EvidenceEvent], event_id: str, unit_id: str) -> None:
    if not event_id.strip() or not unit_id.strip():
        raise ValidationError("Comprehension events need non-empty ids")
    if any(event.id == event_id for event in events):
        raise ValidationError(f"Duplicate comprehension event id: {event_id}")


def _active_evidence(events: list[EvidenceEvent], unit_id: str) -> list[EvidenceObservation]:
    reopened_at = -1
    for index, event in enumerate(events):
        if event.kind == "reopened" and event.unit_id == unit_id:
            reopened_at = index
    return [
        event
        for event in events[reopened_at + 1 :]
        if event.kind == "evidence" and event.unit_id == unit_id
    ]


def assess_unit(events: list[EvidenceEvent], unit_id: str) -> UnitAssessment:
    active = _active_evidence(events, unit_id)
    has_conflict = any(item.result is EvidenceResult.CONFLICT for item in active)
    has_demonstrated = any(item.result is EvidenceResult.DEMONSTRATED for item in active)
    prompted_methods = list(
        dict.fromkeys(
            item.method for item in active if item.result is EvidenceResult.SUPPORTED_PROMPTED
        )
    )
    open_results = list(
        dict.fromkeys(item.result for item in active if item.result in OPEN_RESULTS)
    )

    if has_demonstrated:
        support = SupportLevel.DEMONSTRATED
    elif prompted_methods:
        support = SupportLevel.PROMPTED
    else:
        support = SupportLevel.NONE

    status = "unchecked"
    if has_conflict:
        status = EvidenceResult.CONFLICT.value
    elif has_demonstrated:
        status = EvidenceResult.DEMONSTRATED.value
    elif prompted_methods:
        status = EvidenceResult.SUPPORTED_PROMPTED.value
    elif EvidenceResult.CARRY_TO_REFINE in open_results:
        status = EvidenceResult.CARRY_TO_REFINE.value
    elif open_results:
        status = open_results[-1].value

    return UnitAssessment(
        unit_id=unit_id,
        status=status,
        support=support,
        prompted_methods=prompted_methods,
        open_results=open_results,
        has_conflict=has_conflict,
        active_evidence=active,
    )


class ComprehensionUnit(BaseModel):
    id: str
    critical: bool


class ReadinessOutcome(enum.StrEnum):
    READY_SUPPORTED = "ready_supported"
    READY_WITH_OPEN_POINTS = "ready_with_open_points"
    NEEDS_MORE_WORK = "needs_more_work"


class ReadinessBlocker(BaseModel):
    code: str
    unit_id: str | None = None
    reasons: list[str] = Field(default_factory=list)
    methods_found: int | None = None
    methods_required: int | None = None


class ReadinessOpenPoint(BaseModel):
    unit_id: str
    reason: str


class ReadinessEvaluation(BaseModel):
    outcome: ReadinessOutcome
    blockers: list[ReadinessBlocker]
    open_points: list[ReadinessOpenPoint]
    supported_unit_ids: list[str]


CRITICAL_PROMPTED_METHODS_REQUIRED = 2


def evaluate_readiness(
    events: list[EvidenceEvent],
    *,
    units: list[ComprehensionUnit],
    all_scenes_practiced_in_mother_tongue: bool,
    team_wants_to_proceed: bool,
    critical_prompted_methods_required: int = CRITICAL_PROMPTED_METHODS_REQUIRED,
) -> ReadinessEvaluation:
    seen_units: set[str] = set()
    for unit in units:
        if not unit.id.strip():
            raise ValidationError("Comprehension unit id must not be empty")
        if unit.id in seen_units:
            raise ValidationError(f"Duplicate comprehension unit id: {unit.id}")
        seen_units.add(unit.id)

    blockers: list[ReadinessBlocker] = []
    open_points: list[ReadinessOpenPoint] = []
    supported_unit_ids: list[str] = []

    if not team_wants_to_proceed:
        blockers.append(ReadinessBlocker(code="team_not_ready"))
    if not all_scenes_practiced_in_mother_tongue:
        blockers.append(ReadinessBlocker(code="mother_tongue_practice_incomplete"))
    if not units:
        blockers.append(ReadinessBlocker(code="no_comprehension_units"))

    for unit in units:
        assessment = assess_unit(events, unit.id)
        has_explicit_open_limit = bool(assessment.open_results)
        is_explicitly_deferred = EvidenceResult.CARRY_TO_REFINE in assessment.open_results
        prompted_sufficient = (
            assessment.support is SupportLevel.PROMPTED
            and len(assessment.prompted_methods) >= critical_prompted_methods_required
        )
        supported = not assessment.has_conflict and (
            assessment.support is SupportLevel.DEMONSTRATED
            or (
                prompted_sufficient
                if unit.critical
                else assessment.support is SupportLevel.PROMPTED
            )
        )
        if supported:
            supported_unit_ids.append(unit.id)

        if unit.critical:
            if assessment.has_conflict:
                blockers.append(ReadinessBlocker(code="critical_unit_conflict", unit_id=unit.id))
            elif assessment.support is SupportLevel.NONE and not has_explicit_open_limit:
                blockers.append(ReadinessBlocker(code="critical_unit_unchecked", unit_id=unit.id))
            elif (
                assessment.support is SupportLevel.NONE
                and has_explicit_open_limit
                and not is_explicitly_deferred
            ):
                blockers.append(
                    ReadinessBlocker(
                        code="critical_open_point_not_carried_to_refine",
                        unit_id=unit.id,
                        reasons=[
                            result.value
                            for result in assessment.open_results
                            if result is not EvidenceResult.CARRY_TO_REFINE
                        ],
                    )
                )
            elif (
                assessment.support is SupportLevel.PROMPTED
                and not prompted_sufficient
                and not is_explicitly_deferred
            ):
                blockers.append(
                    ReadinessBlocker(
                        code="critical_prompted_support_needs_another_method",
                        unit_id=unit.id,
                        methods_found=len(assessment.prompted_methods),
                        methods_required=critical_prompted_methods_required,
                    )
                )
        elif assessment.has_conflict:
            open_points.append(ReadinessOpenPoint(unit_id=unit.id, reason="noncritical_conflict"))

        for result in assessment.open_results:
            open_points.append(ReadinessOpenPoint(unit_id=unit.id, reason=result.value))

    deduped: list[ReadinessOpenPoint] = []
    seen_points: set[tuple[str, str]] = set()
    for point in open_points:
        key = (point.unit_id, point.reason)
        if key not in seen_points:
            seen_points.add(key)
            deduped.append(point)

    if blockers:
        outcome = ReadinessOutcome.NEEDS_MORE_WORK
    elif deduped:
        outcome = ReadinessOutcome.READY_WITH_OPEN_POINTS
    else:
        outcome = ReadinessOutcome.READY_SUPPORTED

    return ReadinessEvaluation(
        outcome=outcome,
        blockers=blockers,
        open_points=deduped,
        supported_unit_ids=supported_unit_ids,
    )
