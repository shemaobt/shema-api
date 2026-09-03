"""Checkpoint derivation, probe authorization invariants, and the deterministic planner."""

import pytest

from app.core.exceptions import ValidationError
from app.services.internalization_room.calibration import BridgeMode
from app.services.internalization_room.comprehension.checkpoints import (
    checkpoints_for,
    scene_ids_for,
)
from app.services.internalization_room.comprehension.evidence import (
    EvidenceMethod,
    EvidenceObservation,
    EvidenceResult,
)
from app.services.internalization_room.comprehension.probe import (
    ActiveProbe,
    ProbePurpose,
    process_choice_freezes_bridge_mode,
    resolve_carry_to_refine_decision,
    select_probe_after_oral_turn,
)
from app.services.internalization_room.comprehension.probe_plan import (
    ProbePlanInput,
    plan_next_probe,
    render_active_probe_contract,
)

P = "P03"


def _plan_input(**overrides):
    base = {
        "id": "probe-1",
        "mode": BridgeMode.GUIDED_MICROCHECKS,
        "checkpoints": list(checkpoints_for(P)),
        "ledger": [],
        "scene_ids": scene_ids_for(P),
        "current_scene": None,
        "practiced_scene_ids": [],
        "opened_scene_ids": scene_ids_for(P),
        "told_scene_ids": scene_ids_for(P),
    }
    base.update(overrides)
    return ProbePlanInput(**base)


def _obs(event_id: str, unit: str, result: EvidenceResult, method=EvidenceMethod.MICRO_TELLBACK):
    return EvidenceObservation(
        id=event_id, unit_id=unit, probe_id=f"p-{event_id}", method=method, result=result
    )


def test_the_semantic_spine_is_bounded_not_exhaustive() -> None:
    checkpoints = checkpoints_for(P)
    propositions = [c for c in checkpoints if c.kind == "proposition"]
    critical_propositions = [c for c in propositions if c.critical]
    assert 0 < len(critical_propositions) < len(propositions)


def test_absences_and_preserved_elements_are_always_critical() -> None:
    for checkpoint in checkpoints_for(P):
        if checkpoint.kind in ("significant_absence", "preserved_element"):
            assert checkpoint.critical


def test_checkpoint_ids_are_unique_and_scoped_to_the_pericope() -> None:
    checkpoints = checkpoints_for(P)
    ids = [c.id for c in checkpoints]
    assert len(set(ids)) == len(ids)
    assert all(f":{P}:" in c.id for c in checkpoints)


def test_a_practice_probe_cannot_authorize_semantic_evidence() -> None:
    with pytest.raises(ValidationError):
        ActiveProbe(
            id="x",
            checkpoint_ids=["u1"],
            method=EvidenceMethod.MICRO_TELLBACK,
            purpose=ProbePurpose.MOTHER_TONGUE_PRACTICE,
            practice_scene_ids=["S1"],
        )


def test_a_guided_probe_authorizes_exactly_one_checkpoint() -> None:
    with pytest.raises(ValidationError):
        ActiveProbe(
            id="x",
            checkpoint_ids=["u1", "u2"],
            method=EvidenceMethod.MICRO_TELLBACK,
            purpose=ProbePurpose.INITIAL_CHECK,
        )


def test_only_a_free_retell_may_span_many_checkpoints() -> None:
    probe = ActiveProbe(
        id="x",
        checkpoint_ids=["u1", "u2"],
        method=EvidenceMethod.FREE_BRIDGE_RETELL,
        purpose=ProbePurpose.FREE_RETELL,
    )
    assert len(probe.checkpoint_ids) == 2
    with pytest.raises(ValidationError):
        ActiveProbe(
            id="x",
            checkpoint_ids=["u1"],
            method=EvidenceMethod.MICRO_TELLBACK,
            purpose=ProbePurpose.FREE_RETELL,
        )


def test_conflict_clarification_needs_a_focused_method() -> None:
    with pytest.raises(ValidationError):
        ActiveProbe(
            id="x",
            checkpoint_ids=["u1"],
            method=EvidenceMethod.FREE_BRIDGE_RETELL,
            purpose=ProbePurpose.CLARIFY_CONFLICT,
        )


def test_a_pending_process_choice_freezes_the_bridge_mode() -> None:
    consent = ActiveProbe(
        id="x",
        checkpoint_ids=[],
        method=EvidenceMethod.MICRO_TELLBACK,
        purpose=ProbePurpose.RECORDING_HANDOFF_CONSENT,
    )
    assert process_choice_freezes_bridge_mode(consent, recovery_choice_pending=False)
    assert process_choice_freezes_bridge_mode(None, recovery_choice_pending=True)
    semantic = ActiveProbe(
        id="y",
        checkpoint_ids=["u1"],
        method=EvidenceMethod.MICRO_TELLBACK,
        purpose=ProbePurpose.INITIAL_CHECK,
    )
    assert not process_choice_freezes_bridge_mode(semantic, recovery_choice_pending=False)


def test_full_retell_mode_opens_with_a_whole_scope_retell() -> None:
    probe = plan_next_probe(_plan_input(mode=BridgeMode.FULL_RETELL))
    assert probe is not None
    assert probe.purpose is ProbePurpose.FREE_RETELL
    assert probe.method is EvidenceMethod.FREE_BRIDGE_RETELL
    assert len(probe.checkpoint_ids) > 1


def test_guided_mode_asks_for_scene_practice_before_any_semantic_question() -> None:
    probe = plan_next_probe(_plan_input())
    assert probe is not None
    assert probe.purpose is ProbePurpose.MOTHER_TONGUE_PRACTICE
    assert probe.practice_scene_ids == [scene_ids_for(P)[0]]
    assert probe.checkpoint_ids == []


def test_practice_is_never_invited_for_a_scene_the_voice_has_not_opened() -> None:
    probe = plan_next_probe(_plan_input(opened_scene_ids=[], told_scene_ids=[]))
    assert probe is not None
    assert probe.purpose is not ProbePurpose.MOTHER_TONGUE_PRACTICE


def test_practice_waits_for_its_own_scene_to_open() -> None:
    later = scene_ids_for(P)[1:]
    probe = plan_next_probe(
        _plan_input(opened_scene_ids=later, told_scene_ids=later, current_scene=scene_ids_for(P)[0])
    )
    assert probe is not None
    assert probe.purpose is not ProbePurpose.MOTHER_TONGUE_PRACTICE or (
        probe.practice_scene_ids and probe.practice_scene_ids[0] in later
    )


def test_guided_mode_probes_one_atomic_checkpoint_after_practice() -> None:
    probe = plan_next_probe(_plan_input(practiced_scene_ids=scene_ids_for(P)))
    assert probe is not None
    assert probe.purpose is ProbePurpose.INITIAL_CHECK
    assert len(probe.checkpoint_ids) == 1


def test_an_open_bridge_limit_gets_the_carry_offer() -> None:
    checkpoints = list(checkpoints_for(P))
    first_critical = next(c for c in checkpoints if c.critical)
    ledger = [_obs("a", first_critical.id, EvidenceResult.UNCLEAR_DUE_BRIDGE)]
    probe = plan_next_probe(_plan_input(ledger=ledger, practiced_scene_ids=scene_ids_for(P)))
    assert probe is not None
    assert probe.purpose is ProbePurpose.CARRY_TO_REFINE_CHOICE
    assert probe.checkpoint_ids == [first_critical.id]


def test_a_disputed_transcript_gets_the_carry_offer_too() -> None:
    checkpoints = list(checkpoints_for(P))
    first_critical = next(c for c in checkpoints if c.critical)
    ledger = [_obs("a", first_critical.id, EvidenceResult.UNCLEAR_DUE_TRANSCRIPT)]
    probe = plan_next_probe(_plan_input(ledger=ledger, practiced_scene_ids=scene_ids_for(P)))
    assert probe is not None
    assert probe.purpose is ProbePurpose.CARRY_TO_REFINE_CHOICE
    assert probe.checkpoint_ids == [first_critical.id]


def test_a_conflict_is_clarified_before_anything_else() -> None:
    checkpoints = list(checkpoints_for(P))
    first_critical = next(c for c in checkpoints if c.critical)
    ledger = [_obs("a", first_critical.id, EvidenceResult.CONFLICT)]
    probe = plan_next_probe(_plan_input(ledger=ledger, practiced_scene_ids=scene_ids_for(P)))
    assert probe is not None
    assert probe.purpose is ProbePurpose.CLARIFY_CONFLICT


def test_prompted_support_triangulates_with_a_different_method() -> None:
    checkpoints = list(checkpoints_for(P))
    target = next(c for c in checkpoints if c.critical and c.kind == "proposition")
    others = [c.id for c in checkpoints if c.critical and c.id != target.id]
    ledger = [_obs("a", target.id, EvidenceResult.SUPPORTED_PROMPTED)] + [
        _obs(f"z{i}", unit, EvidenceResult.CARRY_TO_REFINE) for i, unit in enumerate(others)
    ]
    probe = plan_next_probe(_plan_input(ledger=ledger, practiced_scene_ids=scene_ids_for(P)))
    assert probe is not None
    assert probe.purpose is ProbePurpose.TRIANGULATE
    assert probe.checkpoint_ids == [target.id]
    assert probe.method is not EvidenceMethod.MICRO_TELLBACK


def test_nothing_left_plans_no_probe() -> None:
    checkpoints = list(checkpoints_for(P))
    ledger = [_obs(f"a{i}", c.id, EvidenceResult.DEMONSTRATED) for i, c in enumerate(checkpoints)]
    assert plan_next_probe(_plan_input(ledger=ledger, practiced_scene_ids=scene_ids_for(P))) is None


def test_adaptive_tries_one_natural_scene_then_micro_questions() -> None:
    first = plan_next_probe(
        _plan_input(mode=BridgeMode.ADAPTIVE, practiced_scene_ids=scene_ids_for(P))
    )
    assert first is not None
    assert first.purpose is ProbePurpose.FREE_RETELL
    after_attempt = plan_next_probe(
        _plan_input(
            mode=BridgeMode.ADAPTIVE,
            practiced_scene_ids=scene_ids_for(P),
            adaptive_free_retell_attempt_completed=True,
        )
    )
    assert after_attempt is not None
    assert after_attempt.purpose is ProbePurpose.INITIAL_CHECK
    assert len(after_attempt.checkpoint_ids) == 1


def _semantic_probe() -> ActiveProbe:
    return ActiveProbe(
        id="prior",
        checkpoint_ids=["u1"],
        method=EvidenceMethod.MICRO_TELLBACK,
        purpose=ProbePurpose.INITIAL_CHECK,
    )


def test_a_voiced_turn_installs_the_next_probe() -> None:
    nxt = _semantic_probe()
    assert (
        select_probe_after_oral_turn(
            outcome="pass",
            prior_probe=None,
            next_probe=nxt,
            target_practice_completed=False,
            transcript_uncertain=False,
            transcript_was_mother_tongue=False,
            transcript_empty=False,
            preserve_semantic_probe_for_retry=False,
        )
        is nxt
    )


def test_a_fail_safe_never_binds_evidence_to_an_unvoiced_prompt() -> None:
    prior = _semantic_probe()
    assert (
        select_probe_after_oral_turn(
            outcome="fail_safe",
            prior_probe=prior,
            next_probe=_semantic_probe(),
            target_practice_completed=False,
            transcript_uncertain=False,
            transcript_was_mother_tongue=False,
            transcript_empty=False,
            preserve_semantic_probe_for_retry=False,
        )
        is None
    )


def test_an_empty_or_mother_tongue_turn_keeps_the_prior_probe_for_retry() -> None:
    prior = _semantic_probe()
    for kwargs in (
        {"transcript_was_mother_tongue": True, "transcript_empty": False},
        {"transcript_was_mother_tongue": False, "transcript_empty": True},
    ):
        kept = select_probe_after_oral_turn(
            outcome="fail_safe",
            prior_probe=prior,
            next_probe=None,
            target_practice_completed=False,
            transcript_uncertain=False,
            preserve_semantic_probe_for_retry=False,
            **kwargs,
        )
        assert kept is prior


_CARRY_PROBE = ActiveProbe(
    id="carry",
    checkpoint_ids=["u1"],
    method=EvidenceMethod.MICRO_TELLBACK,
    purpose=ProbePurpose.CARRY_TO_REFINE_CHOICE,
)
_BOUND_QUESTION = (
    "Querem levar este ponto aberto para o Refine, ou tentar uma pergunta menor agora?"
)


def test_carry_requires_the_bound_question() -> None:
    assert (
        resolve_carry_to_refine_decision(_CARRY_PROBE, "O que aconteceu depois?", "sim")
        == "unclear"
    )


def test_an_explicit_carry_is_recognized() -> None:
    assert (
        resolve_carry_to_refine_decision(_CARRY_PROBE, _BOUND_QUESTION, "pode levar para o Refine")
        == "carry"
    )


def test_declining_the_carry_means_try_again() -> None:
    assert (
        resolve_carry_to_refine_decision(_CARRY_PROBE, _BOUND_QUESTION, "ainda não") == "try_again"
    )
    assert (
        resolve_carry_to_refine_decision(
            _CARRY_PROBE, _BOUND_QUESTION, "não, quero tentar outra pergunta menor"
        )
        == "try_again"
    )


def test_a_bare_sim_carries_only_when_the_question_said_so() -> None:
    assert resolve_carry_to_refine_decision(_CARRY_PROBE, _BOUND_QUESTION, "sim") == "unclear"
    explicit = (
        "Se disserem sim, vamos guardar este ponto para o Refine. "
        "Querem levar este ponto aberto para o Refine?"
    )
    assert resolve_carry_to_refine_decision(_CARRY_PROBE, explicit, "sim") == "carry"


def test_the_contract_carries_purpose_method_and_material() -> None:
    checkpoints = list(checkpoints_for(P))
    target = next(c for c in checkpoints if c.critical)
    probe = ActiveProbe(
        id="x",
        checkpoint_ids=[target.id],
        method=EvidenceMethod.MICRO_TELLBACK,
        purpose=ProbePurpose.INITIAL_CHECK,
    )
    contract = render_active_probe_contract(probe, checkpoints)
    assert "PURPOSE: initial_check" in contract
    assert "EVIDENCE METHOD: micro_tellback" in contract
    assert "AUTHORIZED CANONICAL MATERIAL" in contract
    assert "Do not voice internal ids." in contract


def test_no_probe_still_forbids_invented_tests() -> None:
    contract = render_active_probe_contract(None, [])
    assert "Do not invent another semantic test" in contract


def test_a_scene_worked_to_its_last_bead_is_not_invited_to_rehearse_again() -> None:
    """The readiness gate and the planner read the same scene the same way.

    A scene whose every element is engaged counts as practiced for the gate, so a planner
    still reading the reported list alone invites the rehearsal the gate has already
    stopped waiting for — and with a critical checkpoint open the practice branch runs
    before the semantic ones, so that invitation is what the room says."""
    checkpoints = list(checkpoints_for(P))
    open_critical = next(c for c in checkpoints if c.critical)
    ledger = [
        _obs(f"a{i}", c.id, EvidenceResult.DEMONSTRATED)
        for i, c in enumerate(checkpoints)
        if c.id != open_critical.id
    ]
    probe = plan_next_probe(
        _plan_input(
            ledger=ledger,
            practiced_scene_ids=[],
            engaged_scene_ids=scene_ids_for(P),
        )
    )
    assert probe is not None
    assert probe.purpose is not ProbePurpose.MOTHER_TONGUE_PRACTICE


def test_a_finished_practice_never_speaks_over_the_scene_being_invited_now() -> None:
    """Raised in review (little-henok, PR #322), against the fix one commit earlier.

    The note that says a practice is behind the room outlived the turn it was written for.
    `projected_practice` accumulates across the session and `_pick_practice_scene` skips the
    scenes already in it, so the turn that opens scene 2 plans a practice probe for scene 2
    and, with scene 1 finished, rendered both halves of a contradiction in one block: this
    turn ENDS with the invitation, and, a line below, do not invite it again. Both the Guide
    and the Validator read that block, so the invitation at risk was the new scene's — the
    exact failure this branch exists to remove, arriving one scene later.

    A probe that is inviting a rehearsal already names the scene it is inviting. Nothing has
    to be said about the finished ones on that turn.
    """
    probe = ActiveProbe(
        id="x",
        checkpoint_ids=[],
        method=EvidenceMethod.MICRO_TELLBACK,
        purpose=ProbePurpose.MOTHER_TONGUE_PRACTICE,
        practice_scene_ids=[scene_ids_for(P)[1]],
    )

    contract = render_active_probe_contract(
        probe, list(checkpoints_for(P)), practiced_scene_ids=[scene_ids_for(P)[0]]
    )

    assert "ENDS with the invitation" in contract
    assert "do not invite" not in contract
    assert "ask only about the report" not in contract


def test_the_practice_contract_carries_both_halves_of_the_invitation() -> None:
    """One rehearsal, one voice, one contract — and the contract is the Guide's.

    The fixed line asked for a rehearsal closed by a single word; the Guide, invited to
    say the same thing in its own words, asked for a telling-back. Two contracts for one
    piece of work. The invitation is the Guide's now, and the contract it is handed names
    both halves: rehearse in the team's own language, then come back and tell what was
    understood. The closing word is no longer what it asks for."""
    probe = ActiveProbe(
        id="x",
        checkpoint_ids=[],
        method=EvidenceMethod.MICRO_TELLBACK,
        purpose=ProbePurpose.MOTHER_TONGUE_PRACTICE,
        practice_scene_ids=[scene_ids_for(P)[0]],
    )
    contract = render_active_probe_contract(probe, list(checkpoints_for(P))).lower()

    assert "rehearse this scene together in its own language" in contract
    assert "tell you in the session language what it understood" in contract
    assert "pronto" not in contract


def test_a_scene_the_voice_never_opened_is_opened_before_it_is_probed() -> None:
    """The planner reaches an unopened scene and asks about it as if it had been framed.

    Practice waits for the scene to be opened, and nothing else ever opened it: the first
    scene is opened by the passage opening, so the second one arrived with the semantic
    probe as its introduction. The team heard a checkpoint question about material nobody
    had told it.
    """
    first, second = scene_ids_for(P)[0], scene_ids_for(P)[1]
    probe = plan_next_probe(
        _plan_input(
            current_scene=second,
            opened_scene_ids=[first],
            told_scene_ids=[first],
            practiced_scene_ids=[first],
        )
    )
    assert probe is not None
    assert probe.purpose is ProbePurpose.SCENE_OPENING
    assert probe.practice_scene_ids == [second]
    assert probe.checkpoint_ids == []


def test_a_scene_the_guide_only_mentioned_is_still_opened_first() -> None:
    """A bead the Guide raised in passing is `surfaced`, and `opened_scene_ids` counts it.

    Read there, the scene the Guide name-dropped while asking about the previous one kept
    the ENG-740 behaviour exactly: opened on paper, never told, and met by the team as the
    question about it. What the planner has to ask is whether the team took the scene up,
    and that is a bead engaged or partially engaged, not one mentioned.
    """
    first, second = scene_ids_for(P)[0], scene_ids_for(P)[1]
    probe = plan_next_probe(
        _plan_input(
            current_scene=second,
            opened_scene_ids=[first, second],
            told_scene_ids=[first],
            practiced_scene_ids=[first],
        )
    )
    assert probe is not None
    assert probe.purpose is ProbePurpose.SCENE_OPENING
    assert probe.practice_scene_ids == [second]


def test_a_scene_already_opened_is_probed_not_opened_again() -> None:
    probe = plan_next_probe(
        _plan_input(current_scene=scene_ids_for(P)[0], practiced_scene_ids=scene_ids_for(P))
    )
    assert probe is not None
    assert probe.purpose is ProbePurpose.INITIAL_CHECK


def test_the_opening_contract_authorizes_the_canonical_content_it_needs() -> None:
    """The Guide is told to say what happens in the scene, which every other turn forbids.

    An opening that may not state the map is not an opening, and the Validator holds the
    same block: without the permission written into it, the one draft the contract asks
    for is the one the Validator rejects for revealing the answer.
    """
    second = scene_ids_for(P)[1]
    probe = ActiveProbe(
        id="open-1",
        checkpoint_ids=[],
        method=EvidenceMethod.MICRO_TELLBACK,
        purpose=ProbePurpose.SCENE_OPENING,
        practice_scene_ids=[second],
    )
    contract = render_active_probe_contract(
        probe, list(checkpoints_for(P)), practiced_scene_ids=[scene_ids_for(P)[0]]
    )
    assert "scene_opening" in contract
    assert second in contract
    assert "canonical content is allowed" in contract
    assert "rehearse" in contract
    assert "PRACTICE DONE" not in contract
