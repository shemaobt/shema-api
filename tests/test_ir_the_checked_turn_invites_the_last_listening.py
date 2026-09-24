import pytest

from app.services.internalization_room.back_translation import (
    CLOSING_CHECKED,
    CLOSING_PLAIN,
    Finding,
    FindingKind,
    closing_block,
    findings_block,
)
from app.services.internalization_room.part_names import Addresses
from app.services.internalization_room.run_turn import run_verdict_turn
from tests.turn_harness import (
    CONTINUES_TELLING_BACK,
    INVITATION_WORDS,
    SPEAKER,
    VALIDATOR,
    P,
    settings,
    the_speaker_answers,
)


@pytest.fixture
def patch_speaker(monkeypatch: pytest.MonkeyPatch):
    def _install(draft: str):
        return the_speaker_answers(monkeypatch, draft)

    return _install


#: The Refine-stage boundary, in the Validator's own vocabulary. The closing that invites the
#: approval is the one place where the word would slip in.
FINAL_TRANSLATION = "final translation"

#: What the closing forbade before it invited anything, and still forbids. A closing that
#: gained the invitation and lost these would be the original defect turned around, and the
#: constant as a whole cannot say so: `CLOSING_CHECKED in spoken_to` agrees with any wording.
PROHIBITIONS = (
    "Do not ask them to answer anything out loud",
    "do not ask how the team feels",
    "do not say goodbye",
    "That invitation is the only next step you name — no other gesture and no other screen",
    "Never a checklist, never a speech",
)


async def _checked_turn_for(draft: str, patch_speaker) -> str:
    """The Speaker's system prompt on a turn with no finding that closes `checked`."""
    agent = patch_speaker(draft)
    await run_verdict_turn(
        session_language="Portuguese",
        language_code="pt",
        findings_text=findings_block([], Addresses()),
        closing=closing_block(None, checked=True),
        scope=P,
        pericope_num=P,
        messages=[],
        speaker_prompt=SPEAKER,
        validator_prompt=VALIDATOR,
        settings=settings(),
    )
    return str(agent.seen[0])


async def test_a_checked_turn_invites_the_last_listening_and_the_approval(patch_speaker) -> None:
    """Case 1. Sem achado e com evidência suficiente, o fechamento nomeia o último passo.

    R5: a rota marcava `checked = True` e mandava o narrador parar por ali. Não há próximo
    turno depois de `checked`, mas há um passo: a equipe ouve a própria gravação inteira e
    aprova como rascunho final. O fechamento é o único lugar em que esse convite é pedido.
    """
    spoken_to = await _checked_turn_for("A passagem foi contada e conferida.", patch_speaker)

    for word in INVITATION_WORDS:
        assert word in spoken_to
    for order in PROHIBITIONS:
        assert order in spoken_to
    assert FINAL_TRANSLATION not in spoken_to
    assert CLOSING_PLAIN not in spoken_to
    assert CLOSING_CHECKED in spoken_to
    assert CONTINUES_TELLING_BACK not in spoken_to


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
