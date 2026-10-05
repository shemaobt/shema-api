from app.services.internalization_room.back_translation import (
    CLOSING_CHECKED,
    CLOSING_PLAIN,
    Finding,
    FindingKind,
    closing_block,
)
from tests.turn_harness import (
    CONTINUES_TELLING_BACK,
)


def test_a_turn_that_is_not_the_checked_one_keeps_asking() -> None:
    """The pure contract of the plain closing: no finding, not checked, so the turn goes on.

    `closing_block` is asked for a closing by more than the room's own `finish`, and this is
    the answer when a finding-less turn is not the one that strikes the passage off — it
    affirms and invites the team to carry on telling back.
    """
    assert closing_block(None, checked=False) == CLOSING_PLAIN
    assert closing_block(None) == CLOSING_PLAIN
    assert CONTINUES_TELLING_BACK in closing_block(None, checked=False)


def test_a_finding_ignores_the_checked_flag() -> None:
    """Case 5 (guard). Com achado, nada muda — os fechamentos de achado continuam os de hoje.

    Na rota real `state.checked` só é `True` quando não há achado, mas `checked` é
    ignorado sempre que há um: a passagem não pode estar conferida no mesmo turno em que
    o narrador está falando sobre algo que o analista encontrou.
    """
    finding = Finding(kind=FindingKind.ADDITION, note="Orfa", segment_id="segmento-2")

    assert closing_block(finding, checked=True) == closing_block(finding, checked=False)
    assert closing_block(finding, checked=True) != CLOSING_CHECKED
    assert CONTINUES_TELLING_BACK in closing_block(finding, checked=True)
