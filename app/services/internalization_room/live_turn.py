"""The comprehension-aware passage turn.

Order matters — this is the state machine the handoff document calls "app-owned": resolve
the bridge mode (explicit switches only), plan STT recovery, resolve the process decisions
bound to the PRIOR persisted probe (carry, recovery choice, consent), assess that probe's
answer semantically, fold the evidence, plan the NEXT probe, and only then let the Guide
speak — or bypass it entirely with exact app-owned speech where safety demands fixed
wording. A probe becomes state only after its question was actually voiced, so evidence is
never bound to an unvoiced prompt.

The opening turn always belongs to the Guide: no probe is planned and no app-owned line
may hijack it, because the Voice must open the passage before anything is asked of the
team — frame first, elicit second. For the same reason, the mother-tongue practice
invitation for a scene is only planned once that scene has been opened in coverage.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.models.internalization_room import IRPromptKey, IRSession
from app.services.internalization_room.calibration import (
    BridgeMode,
    bridge_mode_status_line,
    bridge_mode_validator_context,
    resolve_bridge_mode_for_turn,
    resolve_one_shot_calibration,
)
from app.services.internalization_room.canon.elements import elements_for
from app.services.internalization_room.canon.parse_map import load_map
from app.services.internalization_room.comprehension.assessor import TurnAssessment, assess_turn
from app.services.internalization_room.comprehension.checkpoints import (
    Checkpoint,
    checkpoints_for,
    scene_ids_for,
)
from app.services.internalization_room.comprehension.evidence import (
    EvidenceMethod,
    EvidenceObservation,
    EvidenceResult,
)
from app.services.internalization_room.comprehension.no_report import resolve_no_usable_report
from app.services.internalization_room.comprehension.practice import (
    MOTHER_TONGUE_PRACTICE_PROMPT,
    confident_non_bridge_audio_completes_scoped_practice,
    confirms_completed_mother_tongue_practice,
    practiced_scenes_authorized_by_probe,
)
from app.services.internalization_room.comprehension.probe import (
    ActiveProbe,
    ProbePurpose,
    is_process_only,
    process_choice_freezes_bridge_mode,
    resolve_carry_to_refine_decision,
    select_probe_after_oral_turn,
)
from app.services.internalization_room.comprehension.probe_plan import (
    FocusedRecovery,
    ProbePlanInput,
    plan_next_probe,
    render_active_probe_contract,
)
from app.services.internalization_room.comprehension.session_readiness import (
    evaluate_session_comprehension,
    events_for_observations,
    render_comprehension_status,
)
from app.services.internalization_room.comprehension.state import ComprehensionState
from app.services.internalization_room.comprehension.stt_recovery import (
    STT_RECOVERY_REDUCE_BURDEN_LINE,
    plan_stt_recovery,
    resolve_stt_recovery_choice,
)
from app.services.internalization_room.coverage import CoverageStatus, floor_met
from app.services.internalization_room.fail_safe import FailSafe, choose
from app.services.internalization_room.hearing import HeardSpeech
from app.services.internalization_room.prompts import get_prompt_text
from app.services.internalization_room.rehearsal_readiness import (
    REHEARSAL_CONSENT_DECLINED_LINE,
    REHEARSAL_CONSENT_QUESTION,
    REHEARSAL_READINESS_CUE,
    explicitly_requests_recording_handoff,
    resolve_rehearsal_consent,
    should_offer_recording_consent,
)
from app.services.internalization_room.run_turn import (
    OPENING_BUDGET,
    TURN_BUDGET,
    TurnOutcome,
    detects_peer_cue,
    run_turn,
)
from app.services.internalization_room.sessions import comprehension_of


@dataclass
class ComprehensionTurn:
    outcome: TurnOutcome
    bridge_mode: str
    state: ComprehensionState


def current_scene_id(coverage_state: dict[str, Any], pericope: str) -> str | None:
    """The first scene whose own coverage is not fully engaged — the deterministic scene
    pointer the probe planner scopes to. The Guide never selects the scene itself."""
    by_scene: dict[int, bool] = {}
    for element in elements_for(pericope):
        if element.scene is None:
            continue
        engaged = coverage_state.get(element.key) == CoverageStatus.ENGAGED.value
        by_scene[element.scene] = by_scene.get(element.scene, True) and engaged
    for scene in sorted(by_scene):
        if not by_scene[scene]:
            return f"S{scene}"
    return None


def opened_scene_ids(coverage_state: dict[str, Any], pericope: str) -> list[str]:
    """Scenes the Voice has already opened — at least one element surfaced or engaged."""
    opened: dict[int, bool] = {}
    for element in elements_for(pericope):
        if element.scene is None:
            continue
        touched = coverage_state.get(element.key) in (
            CoverageStatus.SURFACED.value,
            CoverageStatus.ENGAGED.value,
        )
        opened[element.scene] = opened.get(element.scene, False) or touched
    return [f"S{scene}" for scene in sorted(opened) if opened[scene]]


def _observation_id(tail: str) -> str:
    return f"voice:{uuid.uuid4()}:{tail}"


async def run_comprehension_turn(
    db: AsyncSession,
    session: IRSession,
    *,
    speech: HeardSpeech,
    opening: bool,
    guide_prompt: str,
    validator_prompt: str,
    settings: Settings,
) -> ComprehensionTurn:
    """One comprehension turn: what was heard, what it settles, and what the room says back.

    Only the session's very first line is told in two movements. A file-less POST on a session
    that has already spoken is a re-open, and repeating the panorama there would say the whole
    passage twice and pull the necklace apart again.
    """
    pericope = session.pericope
    book = load_map(pericope).book
    checkpoints = list(checkpoints_for(pericope, book))
    scene_ids = scene_ids_for(pericope)
    messages: list[dict[str, Any]] = list(session.messages or [])
    last_guide = next(
        (m.get("text", "") for m in reversed(messages) if m.get("role") == "guide"), ""
    )
    state = comprehension_of(session)
    prior_probe = state.active_probe

    transcript = speech.text
    uncertain = speech.uncertain
    mother_tongue = speech.mother_tongue
    empty = not transcript.strip()
    reliable = not uncertain and not mother_tongue

    recovery_choice_pending = (
        state.stt_recovery is not None and state.stt_recovery.stage == "recovery_choice_pending"
    )
    freeze = process_choice_freezes_bridge_mode(prior_probe, recovery_choice_pending)
    choice_speech = "" if (mother_tongue or uncertain or freeze) else transcript
    current_mode = BridgeMode(session.bridge_mode)
    if current_mode is BridgeMode.CALIBRATION_PENDING:
        bridge_mode = resolve_one_shot_calibration(choice_speech).mode
    else:
        bridge_mode = resolve_bridge_mode_for_turn(current_mode, choice_speech).mode

    recovery_scope: list[str] = []
    if prior_probe is not None and not is_process_only(prior_probe):
        recovery_scope = [
            checkpoint_id
            for checkpoint_id in prior_probe.checkpoint_ids
            if any(c.id == checkpoint_id and c.critical for c in checkpoints)
        ][:1]
    stt_plan = plan_stt_recovery(
        prior=state.stt_recovery,
        probe_id=prior_probe.id if prior_probe and recovery_scope else None,
        checkpoint_ids=recovery_scope,
        method=prior_probe.method if prior_probe and recovery_scope else None,
        transcript_uncertain=uncertain or empty,
    )
    recovery_choice = (
        "unclear"
        if (uncertain or mother_tongue)
        else resolve_stt_recovery_choice(state.stt_recovery, transcript)
    )
    carry_decision = (
        "unclear"
        if (uncertain or mother_tongue)
        else resolve_carry_to_refine_decision(prior_probe, last_guide, transcript)
    )
    consent_decision = resolve_rehearsal_consent(
        probe=prior_probe,
        previous_guide_utterance=last_guide,
        team_utterance=transcript,
        reliable_bridge_speech=reliable,
    )

    assessment = TurnAssessment(observations=[])
    if (
        prior_probe is not None
        and not is_process_only(prior_probe)
        and current_mode is not BridgeMode.CALIBRATION_PENDING
        and transcript.strip()
        and not mother_tongue
        and last_guide.strip()
    ):
        allowed = [c for c in checkpoints if c.id in set(prior_probe.checkpoint_ids)]
        assessment = await assess_turn(
            assessor_prompt=await get_prompt_text(db, IRPromptKey.COMPREHENSION_ASSESSOR),
            observation_id_prefix=_observation_id("assess"),
            probe_id=prior_probe.id,
            method=prior_probe.method,
            checkpoints=allowed,
            meaning_map=load_map(pericope).body,
            previous_guide_question=last_guide,
            team_utterance=transcript,
            mode=(
                bridge_mode
                if bridge_mode is not BridgeMode.CALIBRATION_PENDING
                else BridgeMode.ADAPTIVE
            ),
            speech_recognition_uncertain=uncertain,
            settings=settings,
        )

    new_attempts, no_report_observation = resolve_no_usable_report(
        probe=prior_probe,
        prior_attempts=state.no_report_attempts,
        transcript=transcript,
        reliable_bridge_speech=reliable,
        assessor_found_no_evidence=assessment.assessment_completed and not assessment.observations,
        observation_id=_observation_id("no-report"),
    )

    practice_by_audio = confident_non_bridge_audio_completes_scoped_practice(
        prior_probe, mother_tongue
    )
    practice_confirmed = (
        prior_probe is not None
        and prior_probe.purpose is ProbePurpose.MOTHER_TONGUE_PRACTICE
        and (
            practice_by_audio
            or (reliable and confirms_completed_mother_tongue_practice(last_guide, transcript))
        )
    )
    practiced_now = (
        practiced_scenes_authorized_by_probe(
            prior_probe, practice_confirmed or assessment.mother_tongue_practice_reported
        )
        if prior_probe is not None
        else []
    )

    process_observations: list[EvidenceObservation] = []
    if no_report_observation is not None:
        process_observations.append(no_report_observation)
    pending_recovery_unit = (
        state.stt_recovery.checkpoint_ids[0]
        if state.stt_recovery is not None
        and state.stt_recovery.stage == "recovery_choice_pending"
        and state.stt_recovery.checkpoint_ids
        else None
    )
    recovery_process_resolved = bool(
        pending_recovery_unit
        and (
            recovery_choice != "unclear"
            or (
                prior_probe is not None
                and prior_probe.purpose is ProbePurpose.CARRY_TO_REFINE_CHOICE
                and carry_decision != "unclear"
            )
        )
    )
    if recovery_process_resolved and pending_recovery_unit and state.stt_recovery is not None:
        process_observations.append(
            EvidenceObservation(
                id=_observation_id("stt"),
                unit_id=pending_recovery_unit,
                probe_id=state.stt_recovery.probe_id,
                method=state.stt_recovery.method,
                result=EvidenceResult.STT_UNCERTAIN,
                note="Speech recognition remained uncertain after the single permitted retry.",
            )
        )
    if carry_decision == "carry" and prior_probe is not None and prior_probe.checkpoint_ids:
        recovery = state.stt_recovery
        recovery_bound = (
            recovery_process_resolved
            and pending_recovery_unit == prior_probe.checkpoint_ids[0]
            and recovery is not None
        )
        process_observations.append(
            EvidenceObservation(
                id=_observation_id("carry"),
                unit_id=prior_probe.checkpoint_ids[0],
                probe_id=recovery.probe_id if recovery_bound and recovery else prior_probe.id,
                method=recovery.method if recovery_bound and recovery else prior_probe.method,
                result=EvidenceResult.CARRY_TO_REFINE,
                note=(
                    "The team explicitly chose to leave this STT-limited point open for "
                    "community review in Refine."
                    if recovery_bound
                    else "The team explicitly chose to carry this exact open point into Refine."
                ),
            )
        )
    elif (
        recovery_choice == "carry_to_refine"
        and state.stt_recovery is not None
        and state.stt_recovery.stage == "recovery_choice_pending"
        and state.stt_recovery.checkpoint_ids
    ):
        process_observations.append(
            EvidenceObservation(
                id=_observation_id("carry"),
                unit_id=state.stt_recovery.checkpoint_ids[0],
                probe_id=state.stt_recovery.probe_id,
                method=state.stt_recovery.method,
                result=EvidenceResult.CARRY_TO_REFINE,
                note=(
                    "The team explicitly chose to leave this exact point open for "
                    "community review in Refine."
                ),
            )
        )

    observations = [*assessment.observations, *process_observations]
    events = (
        events_for_observations(
            state.ledger,
            observations,
            conflict_resolution_checkpoint_ids=(
                list(prior_probe.checkpoint_ids)
                if prior_probe is not None and prior_probe.purpose is ProbePurpose.CLARIFY_CONFLICT
                else []
            ),
        )
        if (prior_probe is not None or process_observations)
        else []
    )
    projected_ledger = [*state.ledger, *events]
    projected_practice = list(dict.fromkeys([*state.practiced_scene_ids, *practiced_now]))
    scene_pointer = current_scene_id(session.coverage_state or {}, pericope)

    comprehension_status = render_comprehension_status(
        checkpoints=checkpoints,
        scene_ids=scene_ids,
        ledger=projected_ledger,
        practiced_scene_ids=projected_practice,
        current_scene=scene_pointer,
    )

    recovery_needs_clarification = (
        state.stt_recovery is not None
        and state.stt_recovery.stage == "recovery_choice_pending"
        and recovery_choice == "unclear"
        and carry_decision == "unclear"
        and reliable
        and not empty
    )
    recovery_clarification_checkpoint: Checkpoint | None = None
    if (
        recovery_needs_clarification
        and state.stt_recovery is not None
        and state.stt_recovery.checkpoint_ids
    ):
        recovery_clarification_checkpoint = next(
            (c for c in checkpoints if c.id == state.stt_recovery.checkpoint_ids[0] and c.critical),
            None,
        )

    coverage_complete = floor_met(session.coverage_state or {}, pericope)
    semantic_ready = bridge_mode is not BridgeMode.CALIBRATION_PENDING and (
        evaluate_session_comprehension(
            checkpoints=checkpoints,
            scene_ids=scene_ids,
            ledger=projected_ledger,
            practiced_scene_ids=projected_practice,
        ).evaluation.outcome.value
        != "needs_more_work"
    )
    eligible = coverage_complete and semantic_ready
    resume_requested = (
        state.recording_handoff_paused
        and reliable
        and explicitly_requests_recording_handoff(transcript)
    )
    adaptive_attempt_this_turn = (
        current_mode is BridgeMode.ADAPTIVE
        and prior_probe is not None
        and prior_probe.purpose is ProbePurpose.FREE_RETELL
        and reliable
        and bool(transcript.strip())
    )

    if opening or bridge_mode is BridgeMode.CALIBRATION_PENDING or consent_decision == "accepted":
        planned_probe: ActiveProbe | None = None
    elif recovery_clarification_checkpoint is not None and state.stt_recovery is not None:
        planned_probe = ActiveProbe(
            id=str(uuid.uuid4()),
            checkpoint_ids=[recovery_clarification_checkpoint.id],
            method=state.stt_recovery.method,
            purpose=ProbePurpose.CARRY_TO_REFINE_CHOICE,
        )
    else:
        focused: FocusedRecovery | None = None
        if (
            recovery_choice == "smaller_question"
            or (
                carry_decision == "try_again"
                and prior_probe is not None
                and prior_probe.purpose is ProbePurpose.CARRY_TO_REFINE_CHOICE
            )
        ) and (
            state.stt_recovery is not None
            and state.stt_recovery.stage == "recovery_choice_pending"
            and state.stt_recovery.checkpoint_ids
        ):
            focused = FocusedRecovery(
                checkpoint_id=state.stt_recovery.checkpoint_ids[0],
                previous_method=state.stt_recovery.method,
            )
        planned_probe = plan_next_probe(
            ProbePlanInput(
                id=str(uuid.uuid4()),
                mode=bridge_mode,
                checkpoints=checkpoints,
                ledger=projected_ledger,
                scene_ids=scene_ids,
                current_scene=scene_pointer,
                practiced_scene_ids=projected_practice,
                opened_scene_ids=opened_scene_ids(session.coverage_state or {}, pericope),
                returning_to_full_retell=(
                    bridge_mode is BridgeMode.FULL_RETELL
                    and current_mode is not BridgeMode.FULL_RETELL
                ),
                skip_carry_offer_for_checkpoint_ids=(
                    [prior_probe.checkpoint_ids[0]]
                    if carry_decision == "try_again"
                    and prior_probe is not None
                    and prior_probe.checkpoint_ids
                    else []
                ),
                focused_recovery=focused,
                adaptive_free_retell_attempt_completed=(
                    bridge_mode is BridgeMode.ADAPTIVE
                    and (state.adaptive_free_retell_attempted or adaptive_attempt_this_turn)
                ),
                no_usable_report_attempts=[*state.no_report_attempts, *new_attempts],
            )
        )

    next_probe = planned_probe
    if not opening and should_offer_recording_consent(
        eligible=eligible,
        paused=state.recording_handoff_paused,
        paused_turns=state.recording_handoff_paused_turns,
        explicit_resume_requested=resume_requested,
        prior_decision=consent_decision,
        reliable_bridge_speech=reliable,
    ):
        next_probe = ActiveProbe(
            id=str(uuid.uuid4()),
            checkpoint_ids=[],
            method=EvidenceMethod.MICRO_TELLBACK,
            purpose=ProbePurpose.RECORDING_HANDOFF_CONSENT,
        )

    app_owned_line: str | None = None
    if not opening and eligible and consent_decision == "accepted":
        app_owned_line = REHEARSAL_READINESS_CUE
    elif (
        prior_probe is not None
        and prior_probe.purpose is ProbePurpose.RECORDING_HANDOFF_CONSENT
        and consent_decision == "declined"
    ):
        app_owned_line = REHEARSAL_CONSENT_DECLINED_LINE
    elif next_probe is not None and next_probe.purpose is ProbePurpose.RECORDING_HANDOFF_CONSENT:
        app_owned_line = REHEARSAL_CONSENT_QUESTION
    elif next_probe is not None and next_probe.purpose is ProbePurpose.MOTHER_TONGUE_PRACTICE:
        app_owned_line = MOTHER_TONGUE_PRACTICE_PROMPT

    contract = render_active_probe_contract(
        next_probe,
        checkpoints,
        coverage_complete=coverage_complete,
        semantic_ready=semantic_ready,
        handoff_paused=state.recording_handoff_paused and not resume_requested,
    )
    app_context = "\n\n".join(
        [bridge_mode_status_line(bridge_mode), comprehension_status, contract]
    )
    validator_context = "\n\n".join(
        [bridge_mode_validator_context(bridge_mode), comprehension_status, contract]
    )

    if mother_tongue:
        line, fixed = choose(FailSafe.OFF_BRIDGE_LANGUAGE, turn=len(messages))
        outcome = TurnOutcome(
            speech=line, transcript=transcript, used_fail_safe=True, fixed_line=fixed
        )
    elif not opening and (empty or uncertain):
        if stt_plan.action == "reduce_burden":
            outcome = TurnOutcome(
                speech=STT_RECOVERY_REDUCE_BURDEN_LINE,
                transcript=transcript,
                used_fail_safe=True,
            )
        else:
            line, fixed = choose(FailSafe.INAUDIBLE, turn=len(messages))
            outcome = TurnOutcome(
                speech=line, transcript=transcript, used_fail_safe=True, fixed_line=fixed
            )
    elif app_owned_line is not None:
        outcome = TurnOutcome(
            speech=app_owned_line,
            transcript=transcript,
            peer_cue=detects_peer_cue(app_owned_line),
        )
    else:
        outcome = await run_turn(
            transcript=transcript,
            coverage_state=session.coverage_state or {},
            messages=messages,
            guide_prompt=guide_prompt,
            validator_prompt=validator_prompt,
            pericope_num=pericope,
            book=book,
            opening=opening,
            already_met=session.after_panorama,
            settings=settings,
            app_context=app_context,
            validator_context=validator_context,
            budget=OPENING_BUDGET if opening else TURN_BUDGET,
            ask_for_movements=opening and not messages,
        )

    final_probe = select_probe_after_oral_turn(
        outcome="fail_safe" if outcome.used_fail_safe else "pass",
        prior_probe=prior_probe,
        next_probe=next_probe,
        target_practice_completed=practice_by_audio,
        transcript_uncertain=uncertain,
        transcript_was_mother_tongue=mother_tongue,
        transcript_empty=empty,
        preserve_semantic_probe_for_retry=stt_plan.preserve_semantic_probe,
    )

    new_state = ComprehensionState(
        ledger=projected_ledger,
        active_probe=final_probe,
        practiced_scene_ids=projected_practice,
        adaptive_free_retell_attempted=(
            state.adaptive_free_retell_attempted or adaptive_attempt_this_turn
        ),
        no_report_attempts=[*state.no_report_attempts, *new_attempts],
        stt_recovery=state.stt_recovery if recovery_needs_clarification else stt_plan.next_state,
        recording_consent_given=(
            state.recording_consent_given or (eligible and consent_decision == "accepted")
        ),
        recording_handoff_paused=(
            True
            if consent_decision == "declined"
            else False
            if consent_decision == "accepted" or resume_requested
            else state.recording_handoff_paused
        ),
        recording_handoff_paused_turns=(
            0
            if consent_decision in ("accepted", "declined") or resume_requested
            else state.recording_handoff_paused_turns + 1
            if state.recording_handoff_paused and reliable
            else state.recording_handoff_paused_turns
        ),
    )
    return ComprehensionTurn(outcome=outcome, bridge_mode=bridge_mode.value, state=new_state)
