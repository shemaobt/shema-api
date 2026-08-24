"""Recovery without penalizing the team: no-report rotation, STT retry, practice, consent."""

from app.services.internalization_room.comprehension.evidence import (
    EvidenceMethod,
    EvidenceResult,
)
from app.services.internalization_room.comprehension.no_report import resolve_no_usable_report
from app.services.internalization_room.comprehension.practice import (
    MOTHER_TONGUE_PRACTICE_PROMPT,
    confident_non_bridge_audio_completes_scoped_practice,
    confirms_completed_mother_tongue_practice,
)
from app.services.internalization_room.comprehension.probe import ActiveProbe, ProbePurpose
from app.services.internalization_room.comprehension.probe_plan import NoUsableReportAttempt
from app.services.internalization_room.comprehension.stt_recovery import (
    SttRecoveryState,
    plan_stt_recovery,
    resolve_stt_recovery_choice,
)
from app.services.internalization_room.rehearsal_readiness import (
    REHEARSAL_CONSENT_QUESTION,
    resolve_rehearsal_consent,
    resumes_recording_handoff,
    should_offer_recording_consent,
)


def _semantic_probe(probe_id: str = "p1", method=EvidenceMethod.MICRO_TELLBACK) -> ActiveProbe:
    return ActiveProbe(
        id=probe_id,
        checkpoint_ids=["u1"],
        method=method,
        purpose=ProbePurpose.INITIAL_CHECK,
    )


def test_the_first_nao_sei_records_only_a_process_attempt() -> None:
    attempts, observation = resolve_no_usable_report(
        probe=_semantic_probe(),
        prior_attempts=[],
        transcript="não sei",
        reliable_bridge_speech=True,
        assessor_found_no_evidence=False,
        observation_id="obs-1",
    )
    assert len(attempts) == 1
    assert observation is None


def test_a_second_attempt_with_a_different_method_opens_the_bridge_limit() -> None:
    prior = [
        NoUsableReportAttempt(
            probe_id="p0", checkpoint_ids=["u1"], method=EvidenceMethod.MICRO_TELLBACK
        )
    ]
    attempts, observation = resolve_no_usable_report(
        probe=_semantic_probe("p1", method=EvidenceMethod.PEER_CONFIRMATION),
        prior_attempts=prior,
        transcript="não sei",
        reliable_bridge_speech=True,
        assessor_found_no_evidence=False,
        observation_id="obs-2",
    )
    assert len(attempts) == 1
    assert observation is not None
    assert observation.result is EvidenceResult.UNCLEAR_DUE_BRIDGE
    assert "not lack of understanding" in (observation.note or "")


def test_the_same_method_twice_never_opens_the_limit() -> None:
    prior = [
        NoUsableReportAttempt(
            probe_id="p0", checkpoint_ids=["u1"], method=EvidenceMethod.MICRO_TELLBACK
        )
    ]
    _, observation = resolve_no_usable_report(
        probe=_semantic_probe("p1"),
        prior_attempts=prior,
        transcript="não sei",
        reliable_bridge_speech=True,
        assessor_found_no_evidence=False,
        observation_id="obs-3",
    )
    assert observation is None


def test_unreliable_speech_produces_no_report_bookkeeping() -> None:
    attempts, observation = resolve_no_usable_report(
        probe=_semantic_probe(),
        prior_attempts=[],
        transcript="não sei",
        reliable_bridge_speech=False,
        assessor_found_no_evidence=True,
        observation_id="obs-4",
    )
    assert attempts == [] and observation is None


def test_the_first_uncertainty_retries_the_same_probe() -> None:
    decision = plan_stt_recovery(
        prior=None,
        probe_id="p1",
        checkpoint_ids=["u1"],
        method=EvidenceMethod.MICRO_TELLBACK,
        transcript_uncertain=True,
    )
    assert decision.action == "retry_same_probe"
    assert decision.preserve_semantic_probe
    assert decision.next_state is not None and decision.next_state.stage == "retry_requested"


def test_the_second_uncertainty_reduces_the_burden() -> None:
    prior = SttRecoveryState(
        probe_id="p1",
        checkpoint_ids=["u1"],
        method=EvidenceMethod.MICRO_TELLBACK,
        stage="retry_requested",
    )
    decision = plan_stt_recovery(
        prior=prior,
        probe_id="p1",
        checkpoint_ids=["u1"],
        method=EvidenceMethod.MICRO_TELLBACK,
        transcript_uncertain=True,
    )
    assert decision.action == "reduce_burden"
    assert not decision.preserve_semantic_probe
    assert (
        decision.next_state is not None and decision.next_state.stage == "recovery_choice_pending"
    )


def test_a_clear_transcript_clears_the_recovery() -> None:
    decision = plan_stt_recovery(
        prior=None,
        probe_id="p1",
        checkpoint_ids=["u1"],
        method=EvidenceMethod.MICRO_TELLBACK,
        transcript_uncertain=False,
    )
    assert decision.action == "none" and decision.next_state is None


_PENDING = SttRecoveryState(
    probe_id="p1",
    checkpoint_ids=["u1"],
    method=EvidenceMethod.MICRO_TELLBACK,
    stage="recovery_choice_pending",
)


def test_the_two_option_recovery_refuses_a_polar_answer() -> None:
    assert resolve_stt_recovery_choice(_PENDING, "sim") == "unclear"


def test_the_recovery_accepts_an_explicit_smaller_question() -> None:
    assert resolve_stt_recovery_choice(_PENDING, "uma pergunta curta") == "smaller_question"


def test_the_recovery_accepts_an_explicit_carry() -> None:
    assert resolve_stt_recovery_choice(_PENDING, "pode deixar para o Refine") == "carry_to_refine"


def test_naming_both_branches_stays_unclear() -> None:
    assert resolve_stt_recovery_choice(_PENDING, "pergunta curta ou refine, tanto faz") == "unclear"


def test_pronto_after_the_exact_practice_prompt_confirms() -> None:
    assert confirms_completed_mother_tongue_practice(MOTHER_TONGUE_PRACTICE_PROMPT, "pronto")


def test_a_bare_sim_confirms_only_a_direct_practice_question() -> None:
    assert not confirms_completed_mother_tongue_practice("O que aconteceu depois?", "sim")
    assert confirms_completed_mother_tongue_practice(
        "Vocês já ensaiaram esta cena na língua de vocês?", "sim"
    )


def test_a_denied_practice_never_confirms() -> None:
    assert not confirms_completed_mother_tongue_practice(
        MOTHER_TONGUE_PRACTICE_PROMPT, "não terminamos de ensaiar na nossa língua"
    )


def test_a_future_plan_never_confirms() -> None:
    assert not confirms_completed_mother_tongue_practice(
        "Vocês já ensaiaram esta cena na língua de vocês?",
        "vamos ensaiar essa cena na língua de vocês depois",
    )


def test_confident_foreign_audio_completes_only_the_practice_probe() -> None:
    practice = ActiveProbe(
        id="x",
        checkpoint_ids=[],
        method=EvidenceMethod.MICRO_TELLBACK,
        purpose=ProbePurpose.MOTHER_TONGUE_PRACTICE,
        practice_scene_ids=["S1"],
    )
    assert confident_non_bridge_audio_completes_scoped_practice(practice, True)
    assert not confident_non_bridge_audio_completes_scoped_practice(_semantic_probe(), True)
    assert not confident_non_bridge_audio_completes_scoped_practice(practice, False)


_CONSENT_PROBE = ActiveProbe(
    id="consent",
    checkpoint_ids=[],
    method=EvidenceMethod.MICRO_TELLBACK,
    purpose=ProbePurpose.RECORDING_HANDOFF_CONSENT,
)


def test_consent_needs_the_exact_question_and_probe() -> None:
    assert (
        resolve_rehearsal_consent(
            probe=_CONSENT_PROBE,
            previous_guide_utterance=REHEARSAL_CONSENT_QUESTION,
            team_utterance="sim",
            reliable_bridge_speech=True,
        )
        == "accepted"
    )
    assert (
        resolve_rehearsal_consent(
            probe=_CONSENT_PROBE,
            previous_guide_utterance="Querem gravar em breve?",
            team_utterance="sim",
            reliable_bridge_speech=True,
        )
        == "unclear"
    )
    assert (
        resolve_rehearsal_consent(
            probe=_semantic_probe(),
            previous_guide_utterance=REHEARSAL_CONSENT_QUESTION,
            team_utterance="sim",
            reliable_bridge_speech=True,
        )
        == "unclear"
    )


def test_declining_consent_is_recognized() -> None:
    assert (
        resolve_rehearsal_consent(
            probe=_CONSENT_PROBE,
            previous_guide_utterance=REHEARSAL_CONSENT_QUESTION,
            team_utterance="ainda não",
            reliable_bridge_speech=True,
        )
        == "declined"
    )


def test_uncertain_speech_never_consents() -> None:
    assert (
        resolve_rehearsal_consent(
            probe=_CONSENT_PROBE,
            previous_guide_utterance=REHEARSAL_CONSENT_QUESTION,
            team_utterance="sim",
            reliable_bridge_speech=False,
        )
        == "unclear"
    )


def test_a_paused_handoff_waits_for_the_turn_that_resumes_it() -> None:
    assert not should_offer_recording_consent(
        eligible=True,
        paused=True,
        resume_requested=False,
        consent_already_given=False,
        prior_decision="unclear",
        reliable_bridge_speech=True,
    )
    assert should_offer_recording_consent(
        eligible=True,
        paused=True,
        resume_requested=True,
        consent_already_given=False,
        prior_decision="unclear",
        reliable_bridge_speech=True,
    )


def test_an_ordinary_bridge_language_turn_resumes_a_paused_handoff() -> None:
    """The narrow phrasings stopped being the only key; they did not stop working."""
    assert resumes_recording_handoff(
        "acho que agora a gente já entendeu essa parte", reliable_bridge_speech=True
    )
    assert resumes_recording_handoff("queremos gravar agora", reliable_bridge_speech=True)


def test_speech_the_room_could_not_use_never_resumes_a_paused_handoff() -> None:
    """The team spends whole turns in its own language while rehearsing, and a bad take
    comes back as nothing at all — neither is the team asking to be asked again."""
    assert not resumes_recording_handoff(
        "koeti yoko vitukeovo enepone", reliable_bridge_speech=False
    )
    assert not resumes_recording_handoff("", reliable_bridge_speech=True)
    assert not resumes_recording_handoff("   ", reliable_bridge_speech=True)
