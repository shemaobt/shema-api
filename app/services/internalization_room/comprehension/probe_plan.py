"""Deterministic selection of the next semantic probe.

The model voices the probe naturally, but it never chooses which checkpoint, evidence
method, conflict, or practice scope is authorized. Ported from the reference prototype's
``src/comprehension/probePlan.ts``.
"""

from __future__ import annotations

import json

from pydantic import BaseModel, Field

from app.services.internalization_room.calibration import BridgeMode
from app.services.internalization_room.comprehension.checkpoints import Checkpoint
from app.services.internalization_room.comprehension.evidence import (
    EvidenceEvent,
    EvidenceMethod,
    EvidenceResult,
    SupportLevel,
    assess_unit,
)
from app.services.internalization_room.comprehension.probe import ActiveProbe, ProbePurpose
from app.services.internalization_room.comprehension.question_contract import question_contract


class NoUsableReportAttempt(BaseModel):
    probe_id: str
    checkpoint_ids: list[str]
    method: EvidenceMethod


class FocusedRecovery(BaseModel):
    checkpoint_id: str
    previous_method: EvidenceMethod


class ProbePlanInput(BaseModel):
    id: str
    mode: BridgeMode
    checkpoints: list[Checkpoint]
    ledger: list[EvidenceEvent]
    scene_ids: list[str]
    current_scene: str | None = None
    practiced_scene_ids: list[str] = Field(default_factory=list)
    engaged_scene_ids: list[str] = Field(default_factory=list)
    opened_scene_ids: list[str] = Field(default_factory=list)
    returning_to_full_retell: bool = False
    skip_carry_offer_for_checkpoint_ids: list[str] = Field(default_factory=list)
    focused_recovery: FocusedRecovery | None = None
    adaptive_free_retell_attempt_completed: bool = False
    no_usable_report_attempts: list[NoUsableReportAttempt] = Field(default_factory=list)


def _is_resolved(ledger: list[EvidenceEvent], checkpoint: Checkpoint) -> bool:
    assessment = assess_unit(ledger, checkpoint.id)
    if assessment.has_conflict:
        return False
    if assessment.support is SupportLevel.DEMONSTRATED:
        return True
    if assessment.support is SupportLevel.PROMPTED and len(assessment.prompted_methods) >= 2:
        return True
    return EvidenceResult.CARRY_TO_REFINE in assessment.open_results


def _choose_scope(input_: ProbePlanInput, unresolved: list[Checkpoint]) -> list[Checkpoint]:
    if input_.current_scene:
        current = [c for c in unresolved if c.scene_id == input_.current_scene]
        if current:
            return current
    if input_.mode is not BridgeMode.FULL_RETELL:
        for scene_id in input_.scene_ids:
            scene = [c for c in unresolved if c.scene_id == scene_id]
            if scene:
                return scene
    return list(unresolved)


def _first_focused_method(checkpoint: Checkpoint) -> EvidenceMethod:
    if checkpoint.kind == "significant_absence":
        return EvidenceMethod.SIGNIFICANT_ABSENCE_CHECK
    return EvidenceMethod.MICRO_TELLBACK


def _next_independent_method(
    checkpoint: Checkpoint, previous: list[EvidenceMethod]
) -> EvidenceMethod:
    """Every checkpoint here is atomic, so a true-sequence question (two events) cannot be
    guaranteed; peer confirmation stays a genuinely independent method without asking the
    Guide to invent a second event or an unsafe distractor."""
    if checkpoint.kind == "significant_absence":
        candidates = [
            EvidenceMethod.SIGNIFICANT_ABSENCE_CHECK,
            EvidenceMethod.MICRO_TELLBACK,
            EvidenceMethod.PEER_CONFIRMATION,
        ]
    else:
        candidates = [
            EvidenceMethod.MICRO_TELLBACK,
            EvidenceMethod.PEER_CONFIRMATION,
            EvidenceMethod.ROLE_OR_PLACE_CHOICE,
        ]
    for method in candidates:
        if method not in previous:
            return method
    return EvidenceMethod.PEER_CONFIRMATION


def _next_practice_scene(input_: ProbePlanInput, blocking: list[Checkpoint]) -> str | None:
    """The next scene to rehearse in the mother tongue, among scenes the Voice has opened.

    Practice is a process-only turn — the fixed invitation may not carry passage content —
    so inviting it for a scene the team has never heard opened would ask them to rehearse
    something nobody framed. A scene qualifies only after coverage shows it was opened.

    A fully engaged scene counts as practiced here for the same reason it does in the
    readiness gate, and reading it in only one of the two was its own defect: the gate
    stopped waiting for the closing word while this planner kept naming the scene, so the
    room invited a rehearsal already finished and the Guide read the invitation beside a
    status block saying none was needed.
    """
    practiced = set(input_.practiced_scene_ids) | set(input_.engaged_scene_ids)
    opened = set(input_.opened_scene_ids)
    if input_.current_scene:
        if input_.current_scene not in practiced and input_.current_scene in opened:
            return input_.current_scene
        if any(c.scene_id == input_.current_scene for c in blocking):
            return None
    blocking_scenes = {c.scene_id for c in blocking if c.scene_id}
    for scene_id in input_.scene_ids:
        if scene_id in blocking_scenes and scene_id not in practiced and scene_id in opened:
            return scene_id
    for scene_id in input_.scene_ids:
        if scene_id not in practiced and scene_id in opened:
            return scene_id
    return None


def _probe(
    input_: ProbePlanInput,
    checkpoints: list[Checkpoint],
    method: EvidenceMethod,
    purpose: ProbePurpose,
) -> ActiveProbe:
    return ActiveProbe(
        id=input_.id,
        checkpoint_ids=[c.id for c in checkpoints],
        method=method,
        purpose=purpose,
    )


def plan_next_probe(input_: ProbePlanInput) -> ActiveProbe | None:
    blocking = [c for c in input_.checkpoints if c.critical and not _is_resolved(input_.ledger, c)]
    no_semantic_evidence_yet = not any(event.kind == "evidence" for event in input_.ledger)
    adaptive_trial_occurred = input_.adaptive_free_retell_attempt_completed or any(
        event.kind == "evidence" and event.method is EvidenceMethod.FREE_BRIDGE_RETELL
        for event in input_.ledger
    )

    def no_report_methods_for(checkpoint_id: str) -> list[EvidenceMethod]:
        return list(
            dict.fromkeys(
                attempt.method
                for attempt in input_.no_usable_report_attempts
                if checkpoint_id in attempt.checkpoint_ids
            )
        )

    if input_.focused_recovery:
        target = next((c for c in blocking if c.id == input_.focused_recovery.checkpoint_id), None)
        if target:
            return _probe(
                input_,
                [target],
                _next_independent_method(target, [input_.focused_recovery.previous_method]),
                ProbePurpose.INITIAL_CHECK,
            )

    if (
        input_.mode is BridgeMode.FULL_RETELL
        and (
            (
                no_semantic_evidence_yet
                and not any(
                    attempt.method is EvidenceMethod.FREE_BRIDGE_RETELL
                    for attempt in input_.no_usable_report_attempts
                )
            )
            or input_.returning_to_full_retell
        )
        and blocking
    ):
        return _probe(
            input_,
            _choose_scope(input_, input_.checkpoints),
            EvidenceMethod.FREE_BRIDGE_RETELL,
            ProbePurpose.FREE_RETELL,
        )

    practice_scene_id = _next_practice_scene(input_, blocking)
    if practice_scene_id:
        return ActiveProbe(
            id=input_.id,
            checkpoint_ids=[],
            method=EvidenceMethod.MICRO_TELLBACK,
            purpose=ProbePurpose.MOTHER_TONGUE_PRACTICE,
            practice_scene_ids=[practice_scene_id],
        )
    if not blocking:
        return None

    scoped = _choose_scope(input_, blocking)
    conflict = next(
        (c for c in scoped if assess_unit(input_.ledger, c.id).has_conflict), None
    ) or next((c for c in blocking if assess_unit(input_.ledger, c.id).has_conflict), None)
    if conflict:
        return _probe(
            input_, [conflict], EvidenceMethod.MICRO_TELLBACK, ProbePurpose.CLARIFY_CONFLICT
        )

    skip_carry = set(input_.skip_carry_offer_for_checkpoint_ids)

    def open_limited(checkpoint: Checkpoint) -> bool:
        assessment = assess_unit(input_.ledger, checkpoint.id)
        return (
            checkpoint.id not in skip_carry
            and not assessment.has_conflict
            and (
                EvidenceResult.UNCLEAR_DUE_BRIDGE in assessment.open_results
                or EvidenceResult.UNCLEAR_DUE_TRANSCRIPT in assessment.open_results
                or EvidenceResult.STT_UNCERTAIN in assessment.open_results
            )
            and EvidenceResult.CARRY_TO_REFINE not in assessment.open_results
        )

    open_limit = next((c for c in scoped if open_limited(c)), None) or next(
        (c for c in blocking if open_limited(c)), None
    )
    if open_limit:
        return ActiveProbe(
            id=input_.id,
            checkpoint_ids=[open_limit.id],
            method=_first_focused_method(open_limit),
            purpose=ProbePurpose.CARRY_TO_REFINE_CHOICE,
        )

    if (
        input_.mode is BridgeMode.ADAPTIVE
        and no_semantic_evidence_yet
        and not adaptive_trial_occurred
    ):
        scene = scoped[0].scene_id if scoped else None
        comfortable = [c for c in input_.checkpoints if c.scene_id == scene] if scene else scoped
        return _probe(
            input_, comfortable, EvidenceMethod.FREE_BRIDGE_RETELL, ProbePurpose.FREE_RETELL
        )

    target = scoped[0] if scoped else blocking[0]
    assessment = assess_unit(input_.ledger, target.id)
    no_report_methods = no_report_methods_for(target.id)
    if no_report_methods:
        return _probe(
            input_,
            [target],
            _next_independent_method(target, no_report_methods),
            ProbePurpose.INITIAL_CHECK,
        )
    if target.id in skip_carry:
        return _probe(
            input_,
            [target],
            _next_independent_method(target, [item.method for item in assessment.active_evidence]),
            ProbePurpose.INITIAL_CHECK,
        )
    if assessment.support is SupportLevel.PROMPTED and len(assessment.prompted_methods) < 2:
        return _probe(
            input_,
            [target],
            _next_independent_method(target, assessment.prompted_methods),
            ProbePurpose.TRIANGULATE,
        )
    return _probe(input_, [target], _first_focused_method(target), ProbePurpose.INITIAL_CHECK)


_PURPOSE_INSTRUCTION: dict[ProbePurpose, tuple[str, str]] = {
    ProbePurpose.MOTHER_TONGUE_PRACTICE: (
        "This is a PROCESS-ONLY turn and it ENDS with the invitation, in your own words. "
        "Open only this one scene from the map in a sentence or two, then close by asking "
        "the team to rehearse this scene together in its own language and, when it has "
        "finished, to come back and tell you in the session language what it understood. "
        "Both halves, every time. Do not end on a passage question instead, and do not ask "
        "a passage-content question in the same turn.",
        "The next turn may record only that this scene practice finished — the telling the "
        "team brings back closes it, and so does the closing word; neither can ever become "
        "semantic evidence.",
    ),
    ProbePurpose.CARRY_TO_REFINE_CHOICE: (
        "This is a PROCESS-ONLY turn about the one authorized open point. Say that "
        "difficulty reporting it does not prove misunderstanding. Ask whether the team "
        "wants to carry this point openly into Refine or try one different, smaller "
        "question now, then STOP. Make clear that 'sim' means carry it to Refine. Do not "
        "reveal the canonical answer.",
        "The next contextual yes/no may decide only whether this exact open point travels "
        "to Refine; it can never be semantic support.",
    ),
    ProbePurpose.RECORDING_HANDOFF_CONSENT: (
        "This is a PROCESS-ONLY recording-handoff consent turn. The app voices its exact "
        "fixed yes/no question. Do not add, paraphrase, answer, or replace it; do not ask "
        "passage content.",
        "The next reliable bridge-language answer may decide only whether the team wants "
        "to open the first-rehearsal recorder; it can never be passage evidence.",
    ),
    ProbePurpose.FREE_RETELL: (
        "Invite one natural telling of this comfortable scope; do not turn it into a checklist.",
        "Ask for the bridge-language telling-back without claiming to understand the "
        "mother-tongue words.",
    ),
}


def render_active_probe_contract(
    probe: ActiveProbe | None,
    checkpoints: list[Checkpoint],
    *,
    coverage_complete: bool | None = None,
    semantic_ready: bool | None = None,
    handoff_paused: bool = False,
    practiced_scene_ids: list[str] | None = None,
) -> str:
    """The block injected into BOTH the Guide and the Validator, so a question that
    silently switches points, over-asks, or invents a new semantic test is rejected.

    A scene closes its practice on the telling the team brings back, and until this block
    said so nothing told the Guide where it could read it. Holding a finished report against
    a contract that named no finished practice, it went back to the only instruction it had
    and sent the team to rehearse the same scene again — which the Validator refuses, so the
    turn died as a fail-safe with the team having done everything it was asked.
    """
    contract = _probe_contract(
        probe,
        checkpoints,
        coverage_complete=coverage_complete,
        semantic_ready=semantic_ready,
        handoff_paused=handoff_paused,
    )
    if not practiced_scene_ids:
        return contract
    return contract + (
        f"\nPRACTICE DONE: {', '.join(practiced_scene_ids)} — "
        "do not invite it again; ask only about the report the team already gave."
    )


def _probe_contract(
    probe: ActiveProbe | None,
    checkpoints: list[Checkpoint],
    *,
    coverage_complete: bool | None,
    semantic_ready: bool | None,
    handoff_paused: bool,
) -> str:
    if probe is None:
        if handoff_paused:
            return (
                "ACTIVE COMPREHENSION PROBE (APP-OWNED): none; recording handoff is paused "
                "by the team.\n"
                "Continue its ordinary grounded conversation or mother-tongue rehearsal. Do "
                "not ask about recording again and do not imply that it must proceed.\n"
                "The app itself voices the exact consent question again when the team has "
                "had room to keep working; you never ask, and you never say that it is "
                "coming."
            )
        if semantic_ready is False:
            return (
                "ACTIVE COMPREHENSION PROBE (APP-OWNED): none for this process turn.\n"
                "Do not invent a semantic test and do not ask recording readiness. Follow "
                "the app-owned calibration, recovery, or current process instruction only."
            )
        if semantic_ready is True and coverage_complete is False:
            return (
                "ACTIVE COMPREHENSION PROBE (APP-OWNED): none.\n"
                "The critical semantic spine is ready, but passage COVERAGE still has "
                "unfinished material.\n"
                "Authorize exactly one INTERNALIZATION-ONLY move about one remaining "
                "coverage item: open it from the Meaning Map, invite brief mother-tongue "
                "discussion or rehearsal, then accept a short bridge-language report.\n"
                "This move may advance engagement coverage only. It creates NO semantic "
                "comprehension evidence, must not re-test an already resolved checkpoint, "
                "and must not trigger recording readiness yet."
            )
        return (
            "ACTIVE COMPREHENSION PROBE (APP-OWNED): none.\n"
            "Do not invent another semantic test. If the readiness block is ready, ask only "
            "whether the team wants to move to its first mother-tongue rehearsal for Refine."
        )

    allowed = set(probe.checkpoint_ids)
    material = [
        {"kind": c.kind, "scene": c.scene_id, "canonical": c.canonical}
        for c in checkpoints
        if c.id in allowed
    ]
    if probe.purpose in _PURPOSE_INSTRUCTION:
        instruction, evidence_rule = _PURPOSE_INSTRUCTION[probe.purpose]
    else:
        instruction = (
            "Ask exactly one short, answerable question about only this one semantic unit. "
            "Do not reveal the answer in the question."
        )
        evidence_rule = (
            "Ask for the bridge-language telling-back without claiming to understand the "
            "mother-tongue words."
        )
    process_only = probe.purpose in (
        ProbePurpose.MOTHER_TONGUE_PRACTICE,
        ProbePurpose.CARRY_TO_REFINE_CHOICE,
        ProbePurpose.RECORDING_HANDOFF_CONSENT,
    )
    method_line = (
        "PROCESS DECISION: authorize no semantic evidence."
        if process_only
        else question_contract(probe.method)
    )
    return "\n".join(
        [
            "ACTIVE COMPREHENSION PROBE (APP-OWNED; applies to the NEXT team answer):",
            f"PURPOSE: {probe.purpose.value}",
            f"EVIDENCE METHOD: {probe.method.value}",
            "MOTHER-TONGUE PRACTICE SCENES: "
            + (", ".join(probe.practice_scene_ids) if probe.practice_scene_ids else "none"),
            f"AUTHORIZED CANONICAL MATERIAL: {json.dumps(material, ensure_ascii=False)}",
            instruction,
            evidence_rule,
            method_line,
            "Do not voice internal ids. The candidate response must activate this probe "
            "unless it is the exact app-owned recording-readiness cue.",
        ]
    )
