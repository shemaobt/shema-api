"""Checkpoint derivation."""

from app.services.internalization_room.comprehension.checkpoints import checkpoints_for

P = "P03"


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
