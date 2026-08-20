from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.db.models.internalization_room import IRSessionStatus
from app.services.internalization_room.back_translation import BackTranslationState, Chunk
from app.services.internalization_room.canon.elements import element_keys
from app.services.internalization_room.coverage import initial_state, merge
from app.services.internalization_room.session_end import SessionState, end_of
from app.services.internalization_room.sessions import (
    MAX_RETELLS,
    append_exchange,
    apply_coverage,
    back_translation_of,
    begin_back_translation_again,
    create_session,
    get_session,
    mark_needs_person,
    save_back_translation,
)

P = "P03"


@pytest.mark.asyncio
async def test_a_new_session_starts_with_nothing_encountered(db_session: AsyncSession) -> None:
    session = await create_session(db_session, pericope=P)

    assert session.status is IRSessionStatus.IN_PROGRESS
    assert session.messages == []
    assert session.coverage_state == initial_state(P)


@pytest.mark.asyncio
async def test_an_unknown_session_is_not_found(db_session: AsyncSession) -> None:
    with pytest.raises(NotFoundError):
        await get_session(db_session, "nao-existe")


@pytest.mark.asyncio
async def test_the_exchange_is_appended_in_order(db_session: AsyncSession) -> None:
    session = await create_session(db_session, pericope=P)

    session = await append_exchange(
        db_session, session, team_utterance="a fome chegou", guide_response="isso mesmo"
    )

    assert session.messages == [
        {"role": "team", "text": "a fome chegou"},
        {"role": "guide", "text": "isso mesmo"},
    ]


@pytest.mark.asyncio
async def test_the_opening_turn_records_only_the_guide(db_session: AsyncSession) -> None:
    session = await create_session(db_session, pericope=P)

    session = await append_exchange(
        db_session, session, team_utterance="", guide_response="que bom ter vocês aqui"
    )

    assert session.messages == [{"role": "guide", "text": "que bom ter vocês aqui"}]


@pytest.mark.asyncio
async def test_coverage_settles_without_closing_a_partial_session(
    db_session: AsyncSession,
) -> None:
    session = await create_session(db_session, pericope=P)
    partial = merge(initial_state(P), pericope_num=P, engaged=element_keys(P)[:3])

    session = await apply_coverage(db_session, session.id, partial)

    assert session.status is IRSessionStatus.IN_PROGRESS
    assert session.coverage_state[element_keys(P)[0]] == "engaged"


@pytest.mark.asyncio
async def test_meeting_the_floor_closes_the_session(db_session: AsyncSession) -> None:
    session = await create_session(db_session, pericope=P)
    whole = merge(initial_state(P), pericope_num=P, engaged=element_keys(P))

    session = await apply_coverage(db_session, session.id, whole)

    assert session.status is IRSessionStatus.DONE


@pytest.mark.asyncio
async def test_meeting_the_floor_stamps_the_instant_the_session_closed(
    db_session: AsyncSession,
) -> None:
    """ENG-451. Closing is an event, so it is written down rather than inferred later.

    The other way a session ends leaves no stamp on purpose — it is derived from the last
    activity, because the limit that decides it is not agreed with the room app. Which is
    exactly why this one has to be stamped: without it a finished conversation is
    indistinguishable from an abandoned one, and the Desk would call every completed session
    abandoned.
    """
    session = await create_session(db_session, pericope=P)
    whole = merge(initial_state(P), pericope_num=P, engaged=element_keys(P))

    session = await apply_coverage(db_session, session.id, whole)

    assert session.ended_at is not None
    assert end_of(session, at=datetime.now(UTC)).state is SessionState.COMPLETE


@pytest.mark.asyncio
async def test_a_settle_that_does_not_close_the_session_stamps_nothing(
    db_session: AsyncSession,
) -> None:
    session = await create_session(db_session, pericope=P)
    partial = merge(initial_state(P), pericope_num=P, engaged=element_keys(P)[:3])

    session = await apply_coverage(db_session, session.id, partial)

    assert session.ended_at is None


@pytest.mark.asyncio
async def test_a_session_closes_once_and_the_end_does_not_move_afterwards(
    db_session: AsyncSession,
) -> None:
    """A second settle on a closed session must not slide its end forward.

    The classifier keeps running for whatever turns were already in flight when the floor
    was met, and each of those is another write. An end re-stamped on every one of them
    would grow the conversation's length after the team had finished.
    """
    session = await create_session(db_session, pericope=P)
    whole = merge(initial_state(P), pericope_num=P, engaged=element_keys(P))
    session = await apply_coverage(db_session, session.id, whole)
    closed_at = session.ended_at

    session = await apply_coverage(db_session, session.id, whole)

    assert session.ended_at == closed_at


@pytest.mark.asyncio
async def test_a_session_needing_a_person_is_marked(db_session: AsyncSession) -> None:
    session = await create_session(db_session, pericope=P)

    session = await mark_needs_person(db_session, session)

    assert session.status is IRSessionStatus.NEEDS_PERSON


@pytest.mark.asyncio
async def test_a_fresh_recording_throws_the_whole_telling_back_away(
    db_session: AsyncSession,
) -> None:
    session = await create_session(db_session, pericope=P)
    await save_back_translation(
        db_session,
        session,
        BackTranslationState(scope=P, retells=2, chunks=[Chunk(index=1, text="velho")]),
    )

    state = await begin_back_translation_again(db_session, session)

    assert state.chunks == []
    assert state.retells == 2, (
        "o contado de volta é jogado fora; o orçamento de recontagens não é parte dele. "
        "Zerá-lo punha nas mãos da equipe — por um toque em 'gravar de novo' — o contador "
        "que existe para um laço não virar laço"
    )
    assert session.status is IRSessionStatus.IN_PROGRESS


@pytest.mark.asyncio
async def test_the_retells_are_counted_and_run_out(db_session: AsyncSession) -> None:
    session = await create_session(db_session, pericope=P)
    await save_back_translation(
        db_session, session, BackTranslationState(scope=P, retells=MAX_RETELLS - 1)
    )

    state = back_translation_of(session)
    state.retells += 1
    await save_back_translation(db_session, session, state)
    if state.retells >= MAX_RETELLS:
        await mark_needs_person(db_session, session)

    assert session.status is IRSessionStatus.NEEDS_PERSON, (
        "contar o mesmo trecho de novo era um ciclo que ninguém limitava, e o "
        "orçamento que existia estava numa rota que o app nunca chamava"
    )
