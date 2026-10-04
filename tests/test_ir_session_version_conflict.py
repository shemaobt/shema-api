"""ENG-643 — a turn landing while another is still in flight must not erase its evidence.

`messages` and `comprehension` are both whole-value JSON, each written from whatever the
writer had read at the top of its own turn. Two turns racing the same session used to have
no way to tell the later commit that an earlier one had already moved the row, so the later
write stood and the earlier turn's evidence was gone with neither writer told.

Two independent ``AsyncSession``s stand in for two turns landing together — each loads its
own copy of the row, the way two concurrent requests would, rather than sharing one
connection's identity map, which would hide the race entirely.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.exceptions import ConflictError
from app.services.internalization_room.comprehension.state import ComprehensionState
from app.services.internalization_room.sessions import (
    append_exchange,
    create_session,
    get_session,
    save_comprehension,
)

P = "P01"


@pytest.fixture()
def rival_factory(test_engine) -> async_sessionmaker[AsyncSession]:
    """A second, independent connection onto the same database as ``db_session``."""
    return async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)


async def test_a_turn_that_lands_second_does_not_erase_the_first_turns_message(
    db_session: AsyncSession, rival_factory: async_sessionmaker[AsyncSession]
) -> None:
    session = await create_session(db_session, pericope=P, language="pt")

    async with rival_factory() as rival_db:
        rival_session = await get_session(rival_db, session.id)

        await append_exchange(db_session, session, team_utterance="oi", guide_response="ola")

        with pytest.raises(ConflictError):
            await append_exchange(
                rival_db, rival_session, team_utterance="alo", guide_response="e ai"
            )

    async with rival_factory() as fresh_db:
        landed = await get_session(fresh_db, session.id)
    assert [message["text"] for message in landed.messages] == ["oi", "ola"], (
        "a mensagem do turno perdedor não pode aparecer, e a do vencedor não pode sumir"
    )


async def test_a_turn_that_lands_second_does_not_erase_the_first_turns_comprehension(
    db_session: AsyncSession, rival_factory: async_sessionmaker[AsyncSession]
) -> None:
    session = await create_session(db_session, pericope=P, language="pt")

    async with rival_factory() as rival_db:
        rival_session = await get_session(rival_db, session.id)

        winner_state = ComprehensionState(practiced_scene_ids=["scene-1"])
        await save_comprehension(db_session, session, winner_state)

        loser_state = ComprehensionState(practiced_scene_ids=["scene-1", "scene-2"])
        with pytest.raises(ConflictError):
            await save_comprehension(rival_db, rival_session, loser_state)

    async with rival_factory() as fresh_db:
        landed = await get_session(fresh_db, session.id)
    assert landed.comprehension["practiced_scene_ids"] == ["scene-1"], (
        "o ledger perdedor não pode substituir o do vencedor"
    )
