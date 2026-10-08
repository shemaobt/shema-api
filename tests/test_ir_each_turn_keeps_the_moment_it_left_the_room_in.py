from sqlalchemy.ext.asyncio import AsyncSession

from app.services.internalization_room.sessions import append_exchange, create_session
from app.services.internalization_room.validated_turn import TurnOutcome

P = "P01"
OPENING = "Vamos começar pela Familiarização. Primeiro eu conto a passagem inteira."


async def test_a_reply_that_opens_scene_two_leaves_the_room_in_its_internalization(
    db_session: AsyncSession,
) -> None:
    session = await create_session(db_session, pericope=P)
    session = await append_exchange(db_session, session, team_utterance="", guide_response=OPENING)

    session = await append_exchange(
        db_session,
        session,
        team_utterance="estamos prontos",
        guide_response="Vamos pra Internalização da cena 2. Na segunda cena, Noemi decide voltar.",
    )

    assert session.messages[-1]["moment"] == {
        "before": {"at": "familiarization"},
        "after": {"at": "internalization", "part": 2},
        "by": ["entrance"],
    }, "a resposta abria a cena 2 e a sala continuava na Familiarização"


async def test_a_fixed_line_that_answered_in_the_guides_place_moves_nothing(
    db_session: AsyncSession,
) -> None:
    session = await create_session(db_session, pericope=P)
    session = await append_exchange(db_session, session, team_utterance="", guide_response=OPENING)
    fixed = "Vamos pra Internalização da cena 2."

    session = await append_exchange(
        db_session,
        session,
        team_utterance="estamos prontos",
        guide_response=fixed,
        outcome=TurnOutcome(
            speech=fixed, transcript="estamos prontos", used_fail_safe=True, fixed_line="A1"
        ),
    )

    assert session.messages[-1]["moment"] == {
        "before": {"at": "familiarization"},
        "after": {"at": "familiarization"},
        "by": [],
    }, "uma linha fixa no lugar do Guia mudou o momento da sala"


async def test_a_panorama_turn_keeps_no_moment_because_a_book_has_none(
    db_session: AsyncSession,
) -> None:
    session = await create_session(db_session, pericope="OV-Ruth")

    session = await append_exchange(
        db_session, session, team_utterance="", guide_response="Vamos ouvir o livro de Rute."
    )

    assert "moment" not in session.messages[-1], "o panorama ganhou um momento de passagem"


async def test_a_session_begun_before_the_moment_was_read_goes_on_with_no_moment(
    db_session: AsyncSession,
) -> None:
    session = await create_session(db_session, pericope=P)
    session.messages = [{"role": "guide", "text": OPENING, "at": "2026-10-01T12:00:00+00:00"}]
    await db_session.commit()

    session = await append_exchange(
        db_session,
        session,
        team_utterance="estamos prontos",
        guide_response="Vamos pra Internalização da cena 1.",
    )

    assert "moment" not in session.messages[-1], (
        "uma sessão de antes do momento ganhou um momento a partir do meio da conversa"
    )
