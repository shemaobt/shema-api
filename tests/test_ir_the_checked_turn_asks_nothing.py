import pytest

from app.services.internalization_room.back_translation import (
    CLOSING_CHECKED,
    CLOSING_PLAIN,
    Finding,
    FindingKind,
    closing_block,
    findings_block,
    segments_block,
)
from app.services.internalization_room.run_turn import run_verdict_turn
from tests.test_internalization_room_back_translation import (
    SPEAKER,
    VALIDATOR,
    P,
    _settings,
    _told,
    patch_loop,
    patch_speaker,
)

#: Silences an unused-import lint warning: pytest discovers these fixtures by name because
#: they are imported into this module's namespace, not because anything here calls them
#: directly.
_FIXTURES = (patch_loop, patch_speaker)

#: The phrase every kind but this one still closes with. Its absence is half of what "asks
#: nothing" means here.
ANSWERABLE_QUESTION = "answerable question"

#: The other half of the old instruction's vocabulary — the word this closing may not use
#: even if it avoids a literal question mark.
INVITATION = "invitation"

#: The prompt's own promise of a next round, previously a static line under `{{CLOSING}}`
#: on every verdict turn. `CLOSING_CHECKED` has no next round, so this and it may not both
#: reach the Speaker on the same turn — found in code review, same class of defect as the
#: original bug: a signal that promises continuation on the one turn that has none.
CONTINUES_TELLING_BACK = "finish the telling-back again"


async def _checked_turn_for(draft: str, patch_speaker) -> str:
    """The Speaker's system prompt on a turn with no finding that closes `checked`."""
    agent = patch_speaker(draft)
    await run_verdict_turn(
        session_language="Portuguese",
        language_code="pt",
        findings_text=findings_block(None),
        closing=closing_block(None, checked=True),
        scope=P,
        pericope_num=P,
        messages=[],
        speaker_prompt=SPEAKER,
        validator_prompt=VALIDATOR,
        settings=_settings(),
    )
    return str(agent.seen[0])


async def _checked_turn_with_loop(draft: str, patch_loop):
    """Same turn, through the draft-and-gate loop so the Validator's own brief is visible."""
    told = _told()
    agent = patch_loop(draft, told)
    outcome = await run_verdict_turn(
        session_language="Portuguese",
        language_code="pt",
        findings_text=findings_block(None),
        closing=closing_block(None, checked=True),
        scope=P,
        pericope_num=P,
        messages=[],
        telling_back=segments_block(told),
        speaker_prompt=SPEAKER,
        validator_prompt=VALIDATOR,
        settings=_settings(),
    )
    return outcome, agent


@pytest.mark.asyncio
async def test_a_checked_turn_does_not_ask_a_question(patch_speaker) -> None:
    """Case 1. Sem achado e com evidência suficiente, o fechamento não pede pergunta.

    R5: a rota marcava `checked = True` e ainda assim mandava o narrador terminar com
    "exactly one answerable question or invitation" — o `CLOSING_PLAIN` de sempre. Não há
    próximo turno depois de `checked`, então a pergunta não tinha para quem responder.
    """
    spoken_to = await _checked_turn_for("A passagem foi contada e conferida.", patch_speaker)

    assert ANSWERABLE_QUESTION not in spoken_to
    assert INVITATION not in spoken_to
    assert "Do not ask" in spoken_to
    assert CLOSING_PLAIN not in spoken_to
    assert CLOSING_CHECKED in spoken_to
    assert CONTINUES_TELLING_BACK not in spoken_to


@pytest.mark.asyncio
async def test_the_validator_is_shown_the_checked_closing_not_the_plain_one(
    patch_loop,
) -> None:
    """Case 2. O validador vê o mesmo fechamento que o narrador recebeu, não `CLOSING_PLAIN`."""
    _, agent = await _checked_turn_with_loop("A passagem foi contada e conferida.", patch_loop)

    assert CLOSING_CHECKED in agent.briefs[0]
    assert CLOSING_PLAIN not in agent.briefs[0]
    assert ANSWERABLE_QUESTION not in agent.briefs[0]


@pytest.mark.asyncio
async def test_an_obedient_narrator_passes_the_checked_turn(patch_loop) -> None:
    """Case 3, first half. A draft that only affirms told-and-checked is not refused.

    This only proves the loop still runs end to end on this turn shape — none of the
    Validator double's three rules read the closing at all, so this case cannot tell a
    working `CLOSING_CHECKED` from a broken one either. Cases 1 and 2 carry that weight.

    The mirror half of case 3 — a draft that still asks "Como vocês se sentem?" — is not
    written here. `ValidatorReadsOnlyItsOwnPrompt` judges three things read straight out of
    its own prompt: a claim about the telling-back with no evidence for it, a destination
    the brief never named, and a name the team never said. None of its three rules read the
    closing's own instruction not to ask, so it cannot fail a draft on that basis, and a test
    asserting a fail-safe there would not be testing this change — it would be testing
    against a rule the double does not have. Reported as a gap, not filled with a test that
    would look like coverage of it.
    """
    outcome, _ = await _checked_turn_with_loop("A passagem foi contada e conferida.", patch_loop)

    assert outcome.used_fail_safe is False
    assert outcome.speech == "A passagem foi contada e conferida."


def test_insufficient_evidence_keeps_the_plain_closing() -> None:
    """Case 4 (guard). Sem achado mas com evidência insuficiente, o fechamento não muda.

    Há próximo turno — a equipe vai contar mais — então a pergunta continua tendo para quem
    responder. `state.checked` só fica `True` com achado nenhum *e* evidência suficiente; sem
    a segunda metade, o chamador nunca passa `checked=True` para `closing_block`.
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
