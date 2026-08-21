"""Asking for a person is a pause, not a door that only closes.

`NEEDS_PERSON` had exactly one writer and no reader that ever undid it. The app offers a
long press so a facilitator can start the room again; the next state poll, thirty seconds
later, read the still-latched status and halted the room again — for the rest of the
session, every thirty seconds, while the person stood there.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRSessionStatus
from app.services.internalization_room import sessions as service


@pytest.fixture()
async def halted(db_session: AsyncSession):
    session = await service.create_session(db_session, pericope="P01")
    await service.mark_needs_person(db_session, session)
    assert session.status is IRSessionStatus.NEEDS_PERSON
    return session


async def test_a_turn_that_lands_is_the_person_coming_back(
    db_session: AsyncSession, halted
) -> None:
    await service.append_exchange(
        db_session, halted, team_utterance="voltamos", guide_response="que bom"
    )

    assert halted.status is IRSessionStatus.IN_PROGRESS


async def test_a_finished_passage_does_not_reopen_itself(db_session: AsyncSession) -> None:
    session = await service.create_session(db_session, pericope="P01")
    session.status = IRSessionStatus.DONE
    await db_session.commit()

    await service.append_exchange(db_session, session, team_utterance="oi", guide_response="ola")

    assert session.status is IRSessionStatus.DONE, (
        "só a pausa se desfaz sozinha; uma passagem conferida não volta a estar em curso"
    )
