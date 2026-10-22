from app.db.models.internalization_room import IRSession
from app.services.internalization_room.canon.kept import deployed_pin
from app.services.internalization_room.coverage import coverage_view

#: A P02 session stored before her spine: the team worked the road in all three scenes and
#: Naomi in the first. Her P02 has 38 beads and no road among them.
STORED_BEFORE = {
    "place:S1:the-road": "engaged",
    "place:S2:the-road": "engaged",
    "place:S3:the-road": "engaged",
    "being:S1:B3": "engaged",
}


def test_a_bead_her_spine_does_not_have_fills_nothing_and_a_new_one_waits() -> None:
    stored = IRSession(pericope="P02", coverage_state=STORED_BEFORE, canon_pin=deployed_pin())

    view = coverage_view(stored)

    assert (view.engaged, view.total, view.beads_filled) == (1, 38, 0), (
        "a estrada que o colar dela não tem enchia três contas, e as contas novas nem "
        "entravam no total, então o tablet mostrava o colar inteiro cheio"
    )
