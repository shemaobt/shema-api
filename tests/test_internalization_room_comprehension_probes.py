"""Checkpoint derivation and what a turn leaves standing for the next answer.

The deterministic planner and the authorization invariants it fed are gone. What a probe
still is — the app having voiced its own consent question and owing the next answer to its
own parser — is the whole of what these tests can still ask about.
"""

from app.core.exceptions import ValidationError
from app.services.internalization_room.comprehension.checkpoints import checkpoints_for
from app.services.internalization_room.comprehension.probe import (
    ActiveProbe,
    ProbePurpose,
    process_choice_freezes_bridge_mode,
    select_probe_after_oral_turn,
)

P = "P03"


def _consent_probe(probe_id: str = "probe-1") -> ActiveProbe:
    return ActiveProbe(id=probe_id, purpose=ProbePurpose.RECORDING_HANDOFF_CONSENT)


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


def test_a_probe_without_an_id_is_refused() -> None:
    """The id is what binds an answer to the question that was actually voiced, and a
    blank one binds it to nothing."""
    try:
        ActiveProbe(id="  ", purpose=ProbePurpose.RECORDING_HANDOFF_CONSENT)
    except ValidationError:
        return
    raise AssertionError("a probe with no id was accepted")


def test_a_pending_process_choice_freezes_the_bridge_mode() -> None:
    """A "sim" that answers the app's own consent question must not also switch the
    bridge-language method on its way past."""
    assert process_choice_freezes_bridge_mode(_consent_probe())
    assert not process_choice_freezes_bridge_mode(None)


def test_a_voiced_turn_installs_the_next_probe() -> None:
    nxt = _consent_probe("next")
    assert (
        select_probe_after_oral_turn(
            outcome="pass",
            prior_probe=None,
            next_probe=nxt,
            transcript_uncertain=False,
            transcript_was_mother_tongue=False,
            transcript_empty=False,
        )
        is nxt
    )


def test_a_fail_safe_never_binds_an_answer_to_an_unvoiced_prompt() -> None:
    assert (
        select_probe_after_oral_turn(
            outcome="fail_safe",
            prior_probe=_consent_probe("prior"),
            next_probe=_consent_probe("next"),
            transcript_uncertain=False,
            transcript_was_mother_tongue=False,
            transcript_empty=False,
        )
        is None
    )


def test_an_unheard_turn_keeps_the_prior_probe_for_the_answer_it_asks_for_again() -> None:
    prior = _consent_probe("prior")
    for kwargs in (
        {"transcript_was_mother_tongue": True, "transcript_empty": False},
        {"transcript_was_mother_tongue": False, "transcript_empty": True},
        {"transcript_uncertain": True, "transcript_empty": False},
    ):
        kept = select_probe_after_oral_turn(
            outcome="fail_safe",
            prior_probe=prior,
            next_probe=None,
            **{
                "transcript_uncertain": False,
                "transcript_was_mother_tongue": False,
                "transcript_empty": False,
                **kwargs,
            },
        )
        assert kept is prior
