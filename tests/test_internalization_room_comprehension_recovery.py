"""Recovery without penalizing the team: no-report rotation, STT retry, practice, consent."""

from app.services.internalization_room.comprehension.evidence import (
    EvidenceMethod,
    EvidenceResult,
)
from app.services.internalization_room.comprehension.no_report import resolve_no_usable_report
from app.services.internalization_room.comprehension.practice import (
    bridge_language_retelling_completes_practice,
    confident_non_bridge_audio_completes_scoped_practice,
    confirms_completed_mother_tongue_practice,
    mother_tongue_practice_prompt,
    scenes_practiced_by_the_telling_the_guide_invited,
)
from app.services.internalization_room.comprehension.probe import ActiveProbe, ProbePurpose
from app.services.internalization_room.comprehension.probe_plan import NoUsableReportAttempt
from app.services.internalization_room.comprehension.stt_recovery import (
    SttRecoveryState,
    plan_stt_recovery,
    resolve_stt_recovery_choice,
)
from app.services.internalization_room.rehearsal_readiness import (
    RECORDING_HANDOFF_REOFFER_AFTER_TURNS,
    rehearsal_consent_question,
    rehearsal_readiness_cue,
    resolve_rehearsal_consent,
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
    assert confirms_completed_mother_tongue_practice(mother_tongue_practice_prompt("pt"), "pronto")


def test_a_bare_sim_confirms_only_a_direct_practice_question() -> None:
    assert not confirms_completed_mother_tongue_practice("O que aconteceu depois?", "sim")
    assert confirms_completed_mother_tongue_practice(
        "Vocês já ensaiaram esta cena na língua de vocês?", "sim"
    )


def test_a_denied_practice_never_confirms() -> None:
    assert not confirms_completed_mother_tongue_practice(
        mother_tongue_practice_prompt("pt"), "não terminamos de ensaiar na nossa língua"
    )


def test_a_future_plan_never_confirms() -> None:
    assert not confirms_completed_mother_tongue_practice(
        "Vocês já ensaiaram esta cena na língua de vocês?",
        "vamos ensaiar essa cena na língua de vocês depois",
    )


def test_a_plain_report_of_finished_practice_confirms() -> None:
    assert confirms_completed_mother_tongue_practice(
        mother_tongue_practice_prompt("pt"), "já ensaiamos"
    )


def test_the_completion_word_confirms_inside_a_longer_utterance() -> None:
    assert confirms_completed_mother_tongue_practice(
        mother_tongue_practice_prompt("pt"), "pronto, terminamos"
    )
    assert confirms_completed_mother_tongue_practice(
        mother_tongue_practice_prompt("pt"),
        "a gente leu, depois ensaiou junto, pronto, pode seguir",
    )


def test_asking_about_practice_never_confirms() -> None:
    assert not confirms_completed_mother_tongue_practice(
        mother_tongue_practice_prompt("pt"), "já ensaiamos?"
    )
    assert not confirms_completed_mother_tongue_practice(
        mother_tongue_practice_prompt("pt"), "a gente tem que ensaiar agora?"
    )


def test_a_postponed_practice_never_confirms() -> None:
    assert not confirms_completed_mother_tongue_practice(
        mother_tongue_practice_prompt("pt"), "acho que a gente pode ensaiar depois"
    )
    assert not confirms_completed_mother_tongue_practice(
        mother_tongue_practice_prompt("pt"), "ainda não"
    )


def test_a_negated_practice_never_confirms() -> None:
    assert not confirms_completed_mother_tongue_practice(
        mother_tongue_practice_prompt("pt"), "ainda não ensaiamos"
    )
    assert not confirms_completed_mother_tongue_practice(
        mother_tongue_practice_prompt("pt"), "não, pronto não"
    )
    assert not confirms_completed_mother_tongue_practice(
        mother_tongue_practice_prompt("pt"), "não, pronto"
    )
    assert not confirms_completed_mother_tongue_practice(
        mother_tongue_practice_prompt("pt"), "sim, mas ainda não"
    )
    assert not confirms_completed_mother_tongue_practice(
        mother_tongue_practice_prompt("pt"), "pronto, mas ainda não"
    )


def test_wanting_another_round_does_not_undo_a_finished_practice() -> None:
    assert confirms_completed_mother_tongue_practice(
        mother_tongue_practice_prompt("pt"), "já ensaiamos, mas queremos de novo"
    )


def test_nothing_confirms_a_practice_the_room_never_invited() -> None:
    assert not confirms_completed_mother_tongue_practice("O que aconteceu depois?", "pronto")
    assert not confirms_completed_mother_tongue_practice("O que aconteceu depois?", "já ensaiamos")


def test_a_spanish_room_confirms_a_finished_practice_but_never_a_denied_one() -> None:
    """A Spanish room could not answer its practice probe at all: no matcher carried a
    Spanish word, so the room's own prompt was never read as an invitation."""
    assert confirms_completed_mother_tongue_practice(mother_tongue_practice_prompt("es"), "listo")
    assert not confirms_completed_mother_tongue_practice(
        mother_tongue_practice_prompt("es"), "no, todavía no ensayamos"
    )
    assert not confirms_completed_mother_tongue_practice(
        mother_tongue_practice_prompt("es"), "ya no ensayamos"
    )
    assert not confirms_completed_mother_tongue_practice(
        mother_tongue_practice_prompt("es"), "ya vamos a ensayar esta escena"
    )


def test_the_closing_word_is_heard_at_the_end_of_a_clause_too() -> None:
    """The room heard its own word only when it stood alone.

    Session b553b480, in English: the team answered the fixed invitation with "I already
    said, it's done." and the room said the same invitation again, word for word. The
    token matcher was anchored to a whole segment, so the word arriving where people
    ordinarily put it — at the end of a short clause, after a copula — was not the word at
    all. What refuses stays refusing: the negation, the plan, and the question are each
    turned away by a different guard, and none of them depends on this anchoring.

    The denials are asked in all three languages because the opening is one shared regex
    with a branch per language: an edit to the pt/es branch alone would reopen this in
    pt/es while every English case stayed green. `ya no está listo` is refused here by the
    opening having to touch the word, not by the negation list — no Spanish `no` reaches
    it (ENG-731) — so it is exactly the case a widened opening would lose."""
    english = mother_tongue_practice_prompt("en")

    assert confirms_completed_mother_tongue_practice(english, "I already said, it's done.")
    assert confirms_completed_mother_tongue_practice(english, "it's done")
    assert confirms_completed_mother_tongue_practice(english, "it is done")
    assert confirms_completed_mother_tongue_practice(
        mother_tongue_practice_prompt("pt"), "já está pronto"
    )
    assert confirms_completed_mother_tongue_practice(
        mother_tongue_practice_prompt("es"), "ya está listo"
    )

    assert not confirms_completed_mother_tongue_practice(english, "it's not done")
    assert not confirms_completed_mother_tongue_practice(english, "it will be done")
    assert not confirms_completed_mother_tongue_practice(english, "is it done?")
    assert not confirms_completed_mother_tongue_practice(
        mother_tongue_practice_prompt("pt"), "já não está pronto"
    )
    assert not confirms_completed_mother_tongue_practice(
        mother_tongue_practice_prompt("es"), "ya no está listo"
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
            previous_guide_utterance=rehearsal_consent_question("pt"),
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
            previous_guide_utterance=rehearsal_consent_question("pt"),
            team_utterance="sim",
            reliable_bridge_speech=True,
        )
        == "unclear"
    )


def test_declining_consent_is_recognized() -> None:
    assert (
        resolve_rehearsal_consent(
            probe=_CONSENT_PROBE,
            previous_guide_utterance=rehearsal_consent_question("pt"),
            team_utterance="ainda não",
            reliable_bridge_speech=True,
        )
        == "declined"
    )


def test_uncertain_speech_never_consents() -> None:
    assert (
        resolve_rehearsal_consent(
            probe=_CONSENT_PROBE,
            previous_guide_utterance=rehearsal_consent_question("pt"),
            team_utterance="sim",
            reliable_bridge_speech=False,
        )
        == "unclear"
    )


def test_a_paused_handoff_is_not_reoffered_before_the_cooldown_elapses() -> None:
    assert not should_offer_recording_consent(
        eligible=True,
        paused=True,
        paused_turns=0,
        explicit_resume_requested=False,
        prior_decision="unclear",
        reliable_bridge_speech=True,
    )
    assert should_offer_recording_consent(
        eligible=True,
        paused=True,
        paused_turns=0,
        explicit_resume_requested=True,
        prior_decision="unclear",
        reliable_bridge_speech=True,
    )


def test_a_paused_handoff_is_reoffered_once_the_cooldown_elapses() -> None:
    """The team answered the app's own yes/no question with one of the two words it
    offered; the pause is a deferral, so the question comes back on its own."""
    assert not should_offer_recording_consent(
        eligible=True,
        paused=True,
        paused_turns=RECORDING_HANDOFF_REOFFER_AFTER_TURNS - 1,
        explicit_resume_requested=False,
        prior_decision="unclear",
        reliable_bridge_speech=True,
    )
    assert should_offer_recording_consent(
        eligible=True,
        paused=True,
        paused_turns=RECORDING_HANDOFF_REOFFER_AFTER_TURNS,
        explicit_resume_requested=False,
        prior_decision="unclear",
        reliable_bridge_speech=True,
    )


def test_an_elapsed_cooldown_never_outranks_the_other_gates() -> None:
    """Waiting is not readiness: the passage still has to be finished, the answer still
    has to be heard, and the turn that just declined still declines."""
    assert not should_offer_recording_consent(
        eligible=False,
        paused=True,
        paused_turns=RECORDING_HANDOFF_REOFFER_AFTER_TURNS,
        explicit_resume_requested=False,
        prior_decision="unclear",
        reliable_bridge_speech=True,
    )
    assert not should_offer_recording_consent(
        eligible=True,
        paused=True,
        paused_turns=RECORDING_HANDOFF_REOFFER_AFTER_TURNS,
        explicit_resume_requested=False,
        prior_decision="unclear",
        reliable_bridge_speech=False,
    )
    assert not should_offer_recording_consent(
        eligible=True,
        paused=True,
        paused_turns=RECORDING_HANDOFF_REOFFER_AFTER_TURNS,
        explicit_resume_requested=False,
        prior_decision="declined",
        reliable_bridge_speech=True,
    )


_INVITATION = (
    "A famine comes, and a family leaves Bethlehem for the fields of Moab. "
    "Rehearse this scene together in your own language; when you have finished, "
    "come back and tell me in English what you understood."
)


def test_the_room_hearing_itself_never_finishes_the_practice() -> None:
    """A microphone that picks up the app's own voice must not close the rehearsal.

    The telling the invitation asks for is the team's. The invitation itself, and the head
    or tail of it that a speaker can feed back into the microphone, are the room hearing
    itself — the one thing that is certainly not a rehearsal that happened.

    The head and the tail, and not the middle: a team whose telling repeats a phrase the
    Guide just used is telling, and refusing it would be the refusal this ticket exists to
    remove. The last case fixes that choice, so a widening to plain containment fails
    here instead of quietly costing real retellings."""
    assert not bridge_language_retelling_completes_practice(_INVITATION, _INVITATION, True)
    assert not bridge_language_retelling_completes_practice(
        _INVITATION, "come back and tell me in English what you understood", True
    )
    assert not bridge_language_retelling_completes_practice(
        _INVITATION, "A famine comes, and a family leaves Bethlehem for the fields of Moab.", True
    )
    assert bridge_language_retelling_completes_practice(
        _INVITATION, "A famine came and a family left Bethlehem to live in Moab", True
    )
    assert bridge_language_retelling_completes_practice(
        _INVITATION, "a family leaves Bethlehem for the fields of Moab", True
    )


def test_the_rooms_own_consent_question_never_marks_a_scene_practiced() -> None:
    """The recording-consent question reads exactly like an invitation to rehearse.

    "…record the first rehearsal in your own language?" carries the practice stem and the
    mother-tongue phrase in all three languages, so a team answering it with a whole
    sentence looked like a team reporting a rehearsal — of whatever scene the pointer
    happened to be on, which nobody had invited in that exchange.

    Reading the probe is not enough: accepting the recording clears the planned probe, so
    the readiness cue that follows is an app-owned invitation with no probe behind it at
    all. What settles it is the line — the room's own recording speech never counts, while
    the fixed practice prompt, which is a real invitation, still does."""
    consent = ActiveProbe(
        id="c",
        checkpoint_ids=[],
        method=EvidenceMethod.MICRO_TELLBACK,
        purpose=ProbePurpose.RECORDING_HANDOFF_CONSENT,
    )
    assert (
        scenes_practiced_by_the_telling_the_guide_invited(
            consent,
            rehearsal_consent_question("en"),
            "Yes, let us go ahead and record it now",
            True,
            "S3",
        )
        == []
    )
    for language in ("en", "pt", "es"):
        for line in (rehearsal_consent_question(language), rehearsal_readiness_cue(language)):
            assert (
                scenes_practiced_by_the_telling_the_guide_invited(
                    None, line, "Yes, let us go ahead and record it now", True, "S3"
                )
                == []
            )
    assert scenes_practiced_by_the_telling_the_guide_invited(
        None, _INVITATION, "A famine came and a family left Bethlehem to live in Moab", True, "S1"
    ) == ["S1"]
    assert scenes_practiced_by_the_telling_the_guide_invited(
        None,
        mother_tongue_practice_prompt("en"),
        "A famine came and a family left Bethlehem to live in Moab",
        True,
        "S1",
    ) == ["S1"]


def test_an_announced_plan_is_not_the_telling_the_invitation_asked_for() -> None:
    """The likeliest reply to an invitation is the team saying it is about to obey.

    A plan is the one thing the other completion path had always refused, and the telling
    path was written without it: fluent, substantial, no question, no hedge, no denial, no
    echo — and no rehearsal yet. The scene would enter the practised list on a rehearsal
    that had not started."""
    invitation_pt = mother_tongue_practice_prompt("pt")
    invitation_es = mother_tongue_practice_prompt("es")

    assert not bridge_language_retelling_completes_practice(
        invitation_pt, "vamos ensaiar essa cena agora", True
    )
    assert not bridge_language_retelling_completes_practice(
        _INVITATION, "we are going to rehearse it now", True
    )
    assert not bridge_language_retelling_completes_practice(
        invitation_es, "ya vamos a ensayar esta escena", True
    )
    assert bridge_language_retelling_completes_practice(
        _INVITATION, "A famine came and a family left Bethlehem to live in Moab", True
    )
