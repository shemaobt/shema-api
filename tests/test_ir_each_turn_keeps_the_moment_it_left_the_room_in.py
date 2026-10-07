from sqlalchemy.ext.asyncio import AsyncSession

from app.services.internalization_room.sessions import append_exchange, create_session

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
