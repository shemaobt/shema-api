"""Asking for a person is a pause, not a door that only closes.

`NEEDS_PERSON` had exactly one writer and no reader that ever undid it. The app offers a
long press so a facilitator can start the room again; the next state poll, thirty seconds
later, read the still-latched status and halted the room again — for the rest of the
session, every thirty seconds, while the person stood there.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.room_enums import HaltKind
from app.db.models.internalization_room import IRSessionStatus
from app.services.internalization_room import sessions as service


@pytest.fixture()
async def halted(db_session: AsyncSession):
    session = await service.create_session(db_session, pericope="P01")
    await service.mark_needs_person(db_session, session, kind=HaltKind.BLOCKING)
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


async def test_re_recording_does_not_hand_the_team_a_fresh_retell_budget(
    db_session: AsyncSession,
) -> None:
    """The counter exists so a loop cannot be a loop, and the team could reset it.

    Re-recording is a room-key route the team drives by voice — the very tap a stuck team
    makes when the finding will not go away.
    """
    session = await service.create_session(db_session, pericope="P01")
    state = service.back_translation_of(session)
    state.scope = "P01"
    state.retells = 2
    await service.save_back_translation(db_session, session, state)

    fresh = await service.begin_back_translation_again(db_session, session)

    assert fresh.retells == 2, "toda outra propriedade voltava ao padrão, e o orçamento junto"


async def test_the_session_says_where_the_telling_back_stopped(
    db_session: AsyncSession,
) -> None:
    """Everything a tablet needs to pick a retro back up was already stored, unreachable.

    The app keeps `session_id` in memory only, so any restart lost the whole telling-back
    and the team had to record the rehearsal again.
    """
    from app.api.internalization_room.sessions import _progress
    from app.services.internalization_room.back_translation import BackTranslationState
    from app.services.internalization_room.segments import capture_segment

    session = await service.create_session(db_session, pericope="P01")
    await service.save_back_translation(
        db_session, session, BackTranslationState(scope="P01", retells=1)
    )
    for position, (text, pass_number, starts, ends) in enumerate(
        [("um", 1, 0, 9000), ("dois", 2, 9000, 21000)], start=1
    ):
        await capture_segment(
            db_session,
            session,
            take_id="ensaio-1",
            starts_ms=starts,
            ends_ms=ends,
            bridge_take_id=f"retro-{position}",
            transcript=text,
            pass_number=pass_number,
        )

    told = await _progress(db_session, session)

    assert [one.pass_number for one in told.segments] == [1, 2]
    assert [[one.starts_ms, one.ends_ms] for one in told.segments] == [[0, 9000], [9000, 21000]]
    assert [one.take_id for one in told.segments] == ["ensaio-1", "ensaio-1"], (
        "cada trecho nomeia o arquivo de onde saiu, e não só onde parou de tocar"
    )
    assert told.scope == "P01"
    assert told.retells == 1
