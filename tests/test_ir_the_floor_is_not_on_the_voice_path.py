"""The completion floor is a ledger fact, and the voice path never reads it.

"O classificador só pinta as contas e não pode travar a sessão: o registro informa, o
fecho ('gravem o ensaio') é decisão do Guia" — Marcia, answer 8; `DOCTRINE.md` §4 has it
as the acceptance-bar line "the ledger informs, it never ends the conversation". Raising
the floor back to `engaged` therefore changes nothing the team hears: the same turn, on a
spine that holds the floor and on one that meets it, is answered with the same words, no
fixed line and no fail-safe either way. Where the floor is read — `session_is_done`, which
the turn answers as `done` beside these words, and the release — is not the Guide's voice.
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.internalization_room.canon.elements import element_keys
from app.services.internalization_room.coverage import (
    CoverageStatus,
    floor_met,
    initial_state,
    merge,
)
from app.services.internalization_room.hearing import HeardSpeech
from app.services.internalization_room.live_turn import run_comprehension_turn
from app.services.internalization_room.sessions import (
    append_exchange,
    apply_coverage,
    create_session,
)
from tests.turn_harness import GUIDE, VALIDATOR, P, settings, the_speaker_answers

THE_GUIDES_ANSWER = "Rute disse a Noemi que ia com ela. O que vocês acham que ela sentiu?"


@pytest.fixture
def the_guide_answers(monkeypatch: pytest.MonkeyPatch):
    return the_speaker_answers(monkeypatch, THE_GUIDES_ANSWER)


async def _a_session_whose_spine_is_at(db: AsyncSession, bucket: str):
    session = await create_session(db, language="pt", pericope=P)
    session = await apply_coverage(
        db, session.id, merge(initial_state(P), pericope_num=P, **{bucket: element_keys(P)})
    )
    return await append_exchange(db, session, team_utterance="", guide_response="abertura")


async def _the_same_turn_on(db: AsyncSession, session):
    return await run_comprehension_turn(
        db,
        session,
        speech=HeardSpeech(text="ela foi junto com a sogra, mesmo sem ter mais nada lá"),
        opening=False,
        guide_prompt=GUIDE,
        validator_prompt=VALIDATOR,
        settings=settings(),
    )


async def test_a_floor_not_met_changes_nothing_the_guide_says_back(
    db_session: AsyncSession, the_guide_answers
) -> None:
    echoed = await _a_session_whose_spine_is_at(db_session, CoverageStatus.SURFACED.value)
    worked = await _a_session_whose_spine_is_at(db_session, CoverageStatus.ENGAGED.value)
    assert floor_met(echoed.coverage_state, P) is False
    assert floor_met(worked.coverage_state, P) is True

    on_the_echo = await _the_same_turn_on(db_session, echoed)
    on_the_work = await _the_same_turn_on(db_session, worked)

    assert on_the_echo.outcome.speech == THE_GUIDES_ANSWER, (
        "a sala trocava a fala do Guia por uma linha fixa numa passagem só ecoada"
    )
    assert on_the_echo.outcome == on_the_work.outcome, (
        "o piso decidia o que a equipe ouve — o convite de gravar era condicionado a ele"
    )
    assert on_the_echo.state.active_probe is None
    assert on_the_echo.state.active_probe == on_the_work.state.active_probe
