"""A rehearsal is credited to the scene the Guide's invitation named (ADR 0036).

Between the invitation and the team's report the team keeps talking, beads close in later
scenes, and the Scene pointer moves on. The report used to be credited to wherever the
pointer stood when it arrived, so a team that rehearsed scene 1 was marked as having
rehearsed scene 3, and was asked again for the scene it had just told.
"""

import json
import sys
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRSession
from app.services.internalization_room.canon.elements import elements_for
from app.services.internalization_room.comprehension.practice import (
    guide_invited_mother_tongue_practice,
)
from app.services.internalization_room.comprehension.probe import ActiveProbe, ProbePurpose
from app.services.internalization_room.hearing import HeardSpeech
from app.services.internalization_room.live_turn import run_comprehension_turn
from app.services.internalization_room.sessions import (
    append_exchange,
    comprehension_of,
    create_session,
    save_comprehension,
)
from tests.test_ir_a_whole_passage_runs_without_a_provider import (
    INVITATION as RUTH_INVITATION,
)
from tests.turn_harness import GUIDE, VALIDATOR, P, settings

INVITATION = "Agora ensaiem esta cena juntos na língua de vocês; quando terminarem, digam: pronto."
QUESTION = "Vocês já ensaiaram esta cena na língua de vocês?"
CONVERSATION = "Contem mais sobre o que aconteceu com essas pessoas."


class ScriptedGuide:
    """A Guide that says the lines the case wrote, one per turn, and a Validator that passes."""

    def __init__(self) -> None:
        self.lines: list[str] = []

    async def __call__(self, *, system_prompt: str, user_content: str, **kwargs: Any) -> str:
        if "corrected_response" in system_prompt:
            return json.dumps({"verdict": "pass", "issues": []})
        return self.lines.pop(0)


@pytest.fixture
def guide(monkeypatch: pytest.MonkeyPatch) -> ScriptedGuide:
    scripted = ScriptedGuide()
    module = sys.modules["app.services.internalization_room.run_turn"]
    monkeypatch.setattr(module, "call_agent", scripted)
    return scripted


async def _opened(db_session: AsyncSession, language: str = "pt") -> IRSession:
    session = await create_session(db_session, language=language, pericope=P)
    return await append_exchange(db_session, session, team_utterance="", guide_response="abertura")


async def _turn(
    db_session: AsyncSession, session: IRSession, guide: ScriptedGuide, team: str, line: str
) -> None:
    guide.lines.append(line)
    turn = await run_comprehension_turn(
        db_session,
        session,
        speech=HeardSpeech(text=team),
        opening=False,
        guide_prompt=GUIDE,
        validator_prompt=VALIDATOR,
        settings=settings(),
    )
    await save_comprehension(db_session, session, turn.state)
    await append_exchange(
        db_session, session, team_utterance=team, guide_response=turn.outcome.speech
    )


async def _close_the_beads_of(db_session: AsyncSession, session: IRSession, *scenes: int) -> None:
    session.coverage_state = {
        **(session.coverage_state or {}),
        **{e.key: "engaged" for e in elements_for(P) if e.scene in scenes},
    }
    await db_session.commit()


def _practiced(session: IRSession) -> list[str]:
    return comprehension_of(session).practiced_scene_ids


async def test_a_report_after_the_pointer_moved_on_credits_the_scene_invited(
    db_session: AsyncSession, guide: ScriptedGuide
) -> None:
    session = await _opened(db_session)
    await _turn(db_session, session, guide, "podemos começar", CONVERSATION)
    await _turn(db_session, session, guide, "uma mulher volta para o seu povo", INVITATION)

    await _close_the_beads_of(db_session, session, 1, 2)
    await _turn(db_session, session, guide, "pronto, terminamos", CONVERSATION)

    assert _practiced(session) == ["S1"], (
        "o ensaio da cena 1 era creditado à cena 3, onde o ponteiro estava quando o time "
        "avisou que tinha terminado"
    )


async def test_an_invitation_after_beads_closed_ahead_credits_the_first_scene_owed(
    db_session: AsyncSession, guide: ScriptedGuide
) -> None:
    session = await _opened(db_session)
    await _turn(db_session, session, guide, "podemos começar", CONVERSATION)
    await _close_the_beads_of(db_session, session, 1, 2)

    await _turn(db_session, session, guide, "Rute e Noemi em Moabe", INVITATION)
    await _turn(db_session, session, guide, "pronto", CONVERSATION)

    assert _practiced(session) == ["S1"], (
        "o convite era gravado na cena do ponteiro, a 3, com a cena 1 ainda sem ensaio"
    )


async def test_two_invitations_in_a_row_each_credit_their_own_scene(
    db_session: AsyncSession, guide: ScriptedGuide
) -> None:
    session = await _opened(db_session)
    await _turn(db_session, session, guide, "podemos começar", CONVERSATION)
    await _turn(db_session, session, guide, "uma mulher volta para o seu povo", INVITATION)
    await _turn(db_session, session, guide, "pronto", CONVERSATION)
    assert _practiced(session) == ["S1"]

    await _close_the_beads_of(db_session, session, 1)
    await _turn(db_session, session, guide, "Rute diz que vai junto", INVITATION)
    await _turn(db_session, session, guide, "pronto", CONVERSATION)

    assert _practiced(session) == ["S1", "S2"]


async def test_a_question_between_the_invitation_and_the_report_keeps_the_scene_invited(
    db_session: AsyncSession, guide: ScriptedGuide
) -> None:
    session = await _opened(db_session)
    await _turn(db_session, session, guide, "podemos começar", CONVERSATION)
    await _turn(db_session, session, guide, "uma mulher volta para o seu povo", INVITATION)

    await _close_the_beads_of(db_session, session, 1, 2)
    await _turn(db_session, session, guide, "voltamos", QUESTION)
    await _turn(db_session, session, guide, "sim", CONVERSATION)

    assert _practiced(session) == ["S1"], (
        "a pergunta 'vocês já ensaiaram?' não é convite; o ensaio continua sendo o da cena 1"
    )


async def test_a_report_no_invitation_asked_for_marks_nothing(
    db_session: AsyncSession, guide: ScriptedGuide
) -> None:
    session = await _opened(db_session)
    await _turn(db_session, session, guide, "podemos começar", QUESTION)
    await _turn(db_session, session, guide, "sim", CONVERSATION)

    assert _practiced(session) == [], (
        "sem convite nenhum na sessão, um 'sim' à pergunta marcava a cena do ponteiro"
    )


async def test_a_report_under_a_probe_of_another_purpose_marks_nothing(
    db_session: AsyncSession, guide: ScriptedGuide
) -> None:
    session = await _opened(db_session)
    await _turn(db_session, session, guide, "podemos começar", CONVERSATION)
    await _turn(db_session, session, guide, "uma mulher volta para o seu povo", INVITATION)
    probe = ActiveProbe(id="consent-1", purpose=ProbePurpose.RECORDING_HANDOFF_CONSENT)
    await save_comprehension(
        db_session, session, comprehension_of(session).model_copy(update={"active_probe": probe})
    )

    await _turn(db_session, session, guide, "pronto", CONVERSATION)

    assert _practiced(session) == []


async def test_a_session_saved_before_invitations_were_recorded_still_runs(
    db_session: AsyncSession, guide: ScriptedGuide
) -> None:
    session = await _opened(db_session)
    session.comprehension = {"ledger": [], "active_probe": None, "practiced_scene_ids": []}
    await db_session.commit()

    await _turn(db_session, session, guide, "podemos começar", CONVERSATION)
    await _turn(db_session, session, guide, "uma mulher volta para o seu povo", INVITATION)
    await _turn(db_session, session, guide, "pronto", CONVERSATION)

    assert _practiced(session) == ["S1"]


async def test_a_question_whether_the_team_rehearsed_is_not_an_invitation(
    db_session: AsyncSession, guide: ScriptedGuide
) -> None:
    session = await _opened(db_session, language="en")
    await _turn(db_session, session, guide, "we can start", "Tell me more about these people.")
    await _turn(
        db_session, session, guide, "a woman goes back", "Did you rehearse it in your own language?"
    )
    await _turn(db_session, session, guide, "yes", "Tell me more about these people.")

    assert _practiced(session) == [], (
        "a pergunta 'did you rehearse?' era lida como convite e o 'yes' marcava a cena 1"
    )


async def test_a_question_after_a_credit_does_not_invite_the_next_scene(
    db_session: AsyncSession, guide: ScriptedGuide
) -> None:
    session = await _opened(db_session)
    await _turn(db_session, session, guide, "podemos começar", CONVERSATION)
    await _turn(db_session, session, guide, "uma mulher volta para o seu povo", INVITATION)
    await _turn(
        db_session,
        session,
        guide,
        "pronto",
        "Conseguiram ensaiar esta cena na língua de vocês?",
    )
    await _turn(db_session, session, guide, "sim", CONVERSATION)

    assert _practiced(session) == ["S1"], (
        "a pergunta 'conseguiram ensaiar?' gravava a cena 2 e o 'sim' a marcava sem ensaio"
    )


@pytest.mark.parametrize(
    "line",
    [
        RUTH_INVITATION,
        INVITATION,
        "Rehearse this scene together in your own language; when you have finished, "
        "just say: done.",
        "Agora ensaiem esta cena juntos na língua de vocês; quando terminarem, "
        "venham me contar em português o que vocês entenderam.",
        "Ensayen juntos esta escena en su lengua; cuando terminen, digan listo.",
        "Could you all rehearse this together in your own language and tell me what you got?",
    ],
)
def test_an_invitation_that_says_when_to_come_back_is_still_an_invitation(line: str) -> None:
    assert guide_invited_mother_tongue_practice(line)


@pytest.mark.parametrize(
    "line",
    [
        "Did you rehearse it in your own language?",
        "Were you able to rehearse it in your own language?",
        "Conseguiram ensaiar esta cena na língua de vocês?",
        "Vocês tentaram ensaiar na língua de vocês?",
        "¿Pudieron ensayar esta escena en su lengua?",
        "¿Lograron ensayar en su lengua?",
    ],
)
def test_a_question_whether_the_rehearsal_happened_is_not_an_invitation(line: str) -> None:
    assert not guide_invited_mother_tongue_practice(line)
