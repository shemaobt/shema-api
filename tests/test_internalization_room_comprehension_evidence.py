"""The append-only evidence ledger and the deterministic readiness rule."""

import pytest

from app.core.exceptions import ValidationError
from app.services.internalization_room.comprehension.evidence import (
    ComprehensionUnit,
    EvidenceMethod,
    EvidenceObservation,
    EvidenceResult,
    ReadinessOutcome,
    ReopenedEvent,
    SupportLevel,
    append_evidence,
    append_reopened,
    assess_unit,
    evaluate_readiness,
)


def _obs(
    event_id: str,
    unit: str = "u1",
    result: EvidenceResult = EvidenceResult.DEMONSTRATED,
    method: EvidenceMethod = EvidenceMethod.MICRO_TELLBACK,
) -> EvidenceObservation:
    return EvidenceObservation(
        id=event_id, unit_id=unit, probe_id=f"probe-{event_id}", method=method, result=result
    )


def test_duplicate_event_ids_are_refused() -> None:
    ledger = append_evidence([], _obs("a"))
    with pytest.raises(ValidationError):
        append_evidence(ledger, _obs("a"))


def test_conflict_outranks_demonstration_in_the_summary() -> None:
    ledger = [
        _obs("a", result=EvidenceResult.DEMONSTRATED),
        _obs("b", result=EvidenceResult.CONFLICT),
    ]
    assessment = assess_unit(ledger, "u1")
    assert assessment.status == "conflict"
    assert assessment.has_conflict
    assert assessment.support is SupportLevel.DEMONSTRATED


def test_reopening_starts_a_new_epoch_for_readiness() -> None:
    ledger = [
        _obs("a", result=EvidenceResult.DEMONSTRATED),
        ReopenedEvent(id="r1", unit_id="u1", reason="later_conflict"),
    ]
    assessment = assess_unit(ledger, "u1")
    assert assessment.status == "unchecked"
    assert assessment.support is SupportLevel.NONE


def test_history_before_a_reopen_remains_in_the_ledger() -> None:
    ledger = append_reopened(
        append_evidence([], _obs("a")),
        ReopenedEvent(id="r1", unit_id="u1", reason="team_reconsidered"),
    )
    assert len(ledger) == 2


def test_a_critical_unit_needs_two_distinct_prompted_methods() -> None:
    units = [ComprehensionUnit(id="u1", critical=True)]
    one_method = [
        _obs("a", result=EvidenceResult.SUPPORTED_PROMPTED),
        _obs("b", result=EvidenceResult.SUPPORTED_PROMPTED),
    ]
    partial = evaluate_readiness(
        one_method,
        units=units,
        all_scenes_practiced_in_mother_tongue=True,
        team_wants_to_proceed=True,
    )
    assert partial.outcome is ReadinessOutcome.NEEDS_MORE_WORK
    assert any(
        blocker.code == "critical_prompted_support_needs_another_method"
        for blocker in partial.blockers
    )

    two_methods = [
        _obs("a", result=EvidenceResult.SUPPORTED_PROMPTED),
        _obs(
            "b",
            result=EvidenceResult.SUPPORTED_PROMPTED,
            method=EvidenceMethod.PEER_CONFIRMATION,
        ),
    ]
    ready = evaluate_readiness(
        two_methods,
        units=units,
        all_scenes_practiced_in_mother_tongue=True,
        team_wants_to_proceed=True,
    )
    assert ready.outcome is ReadinessOutcome.READY_SUPPORTED


def test_a_noncritical_unit_is_supported_by_one_prompted_method() -> None:
    evaluation = evaluate_readiness(
        [_obs("a", result=EvidenceResult.SUPPORTED_PROMPTED)],
        units=[ComprehensionUnit(id="u1", critical=False)],
        all_scenes_practiced_in_mother_tongue=True,
        team_wants_to_proceed=True,
    )
    assert evaluation.supported_unit_ids == ["u1"]


def test_an_unresolved_central_conflict_blocks() -> None:
    evaluation = evaluate_readiness(
        [_obs("a", result=EvidenceResult.CONFLICT)],
        units=[ComprehensionUnit(id="u1", critical=True)],
        all_scenes_practiced_in_mother_tongue=True,
        team_wants_to_proceed=True,
    )
    assert evaluation.outcome is ReadinessOutcome.NEEDS_MORE_WORK
    assert evaluation.blockers[0].code == "critical_unit_conflict"


def test_a_carried_point_travels_instead_of_blocking() -> None:
    evaluation = evaluate_readiness(
        [_obs("a", result=EvidenceResult.CARRY_TO_REFINE)],
        units=[ComprehensionUnit(id="u1", critical=True)],
        all_scenes_practiced_in_mother_tongue=True,
        team_wants_to_proceed=True,
    )
    assert evaluation.outcome is ReadinessOutcome.READY_WITH_OPEN_POINTS
    assert evaluation.open_points[0].reason == "carry_to_refine"


def test_a_bridge_limit_without_an_explicit_carry_still_blocks() -> None:
    evaluation = evaluate_readiness(
        [_obs("a", result=EvidenceResult.UNCLEAR_DUE_BRIDGE)],
        units=[ComprehensionUnit(id="u1", critical=True)],
        all_scenes_practiced_in_mother_tongue=True,
        team_wants_to_proceed=True,
    )
    assert evaluation.outcome is ReadinessOutcome.NEEDS_MORE_WORK
    assert evaluation.blockers[0].code == "critical_open_point_not_carried_to_refine"


def test_missing_mother_tongue_practice_blocks_readiness() -> None:
    evaluation = evaluate_readiness(
        [_obs("a")],
        units=[ComprehensionUnit(id="u1", critical=True)],
        all_scenes_practiced_in_mother_tongue=False,
        team_wants_to_proceed=True,
    )
    assert evaluation.outcome is ReadinessOutcome.NEEDS_MORE_WORK
    assert any(
        blocker.code == "mother_tongue_practice_incomplete" for blocker in evaluation.blockers
    )


def test_full_demonstration_with_practice_is_ready_supported() -> None:
    evaluation = evaluate_readiness(
        [_obs("a")],
        units=[ComprehensionUnit(id="u1", critical=True)],
        all_scenes_practiced_in_mother_tongue=True,
        team_wants_to_proceed=True,
    )
    assert evaluation.outcome is ReadinessOutcome.READY_SUPPORTED
    assert evaluation.blockers == []
