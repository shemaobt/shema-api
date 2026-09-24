from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.room_enums import HaltKind
from app.db.models.internalization_room import IRSessionStatus
from app.services.internalization_room.canon.elements import element_keys
from app.services.internalization_room.comprehension.checkpoints import (
    checkpoints_for,
    scene_ids_for,
)
from app.services.internalization_room.comprehension.evidence import (
    EvidenceMethod,
    EvidenceObservation,
    EvidenceResult,
)
from app.services.internalization_room.comprehension.state import ComprehensionState
from app.services.internalization_room.coverage import initial_state, merge
from app.services.internalization_room.hard_stretches import note_a_hard_stretch
from app.services.internalization_room.segments import (
    capture_segment,
    final_segments,
)
from app.services.internalization_room.session_end import SessionState, end_of
from app.services.internalization_room.sessions import (
    RETELLS_BEFORE_A_WARNING,
    append_exchange,
    apply_coverage,
    comprehension_of,
    create_session,
    get_session,
    mark_needs_person,
    save_comprehension,
)

P = "P03"


async def test_a_new_session_starts_with_nothing_encountered(db_session: AsyncSession) -> None:
    session = await create_session(db_session, pericope=P)

    assert session.status is IRSessionStatus.IN_PROGRESS
    assert session.messages == []
    assert session.coverage_state == initial_state(P)


async def test_an_unknown_session_is_not_found(db_session: AsyncSession) -> None:
    with pytest.raises(NotFoundError):
        await get_session(db_session, "nao-existe")


async def test_the_exchange_is_appended_in_order(db_session: AsyncSession) -> None:
    session = await create_session(db_session, pericope=P)

    session = await append_exchange(
        db_session, session, team_utterance="a fome chegou", guide_response="isso mesmo"
    )

    assert session.messages == [
        {"role": "team", "text": "a fome chegou"},
        {"role": "guide", "text": "isso mesmo"},
    ]


async def test_the_opening_turn_records_only_the_guide(db_session: AsyncSession) -> None:
    session = await create_session(db_session, pericope=P)

    session = await append_exchange(
        db_session, session, team_utterance="", guide_response="que bom ter vocês aqui"
    )

    assert session.messages == [{"role": "guide", "text": "que bom ter vocês aqui"}]


async def test_coverage_settles_without_closing_a_partial_session(
    db_session: AsyncSession,
) -> None:
    session = await create_session(db_session, pericope=P)
    partial = merge(initial_state(P), pericope_num=P, engaged=element_keys(P)[:3])

    session = await apply_coverage(db_session, session.id, partial)

    assert session.status is IRSessionStatus.IN_PROGRESS
    assert session.coverage_state[element_keys(P)[0]] == "engaged"


async def test_the_coverage_floor_alone_closes_the_session(db_session: AsyncSession) -> None:
    session = await create_session(db_session, pericope=P)
    whole = merge(initial_state(P), pericope_num=P, engaged=element_keys(P))

    session = await apply_coverage(db_session, session.id, whole)

    assert session.status is IRSessionStatus.DONE
    assert session.ended_at is not None


def _fully_supported_comprehension(pericope: str) -> ComprehensionState:
    ledger = [
        EvidenceObservation(
            id=f"ev-{index}",
            unit_id=checkpoint.id,
            probe_id=f"probe-{index}",
            method=EvidenceMethod.MICRO_TELLBACK,
            result=EvidenceResult.DEMONSTRATED,
        )
        for index, checkpoint in enumerate(checkpoints_for(pericope))
    ]
    return ComprehensionState(
        ledger=list(ledger),
        practiced_scene_ids=scene_ids_for(pericope),
    )


async def test_the_floor_with_evidence_and_practice_closes_the_session(
    db_session: AsyncSession,
) -> None:
    session = await create_session(db_session, pericope=P)
    session = await save_comprehension(db_session, session, _fully_supported_comprehension(P))
    whole = merge(initial_state(P), pericope_num=P, engaged=element_keys(P))

    session = await apply_coverage(db_session, session.id, whole)

    assert session.status is IRSessionStatus.DONE


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
    session = await save_comprehension(db_session, session, _fully_supported_comprehension(P))
    whole = merge(initial_state(P), pericope_num=P, engaged=element_keys(P))

    session = await apply_coverage(db_session, session.id, whole)

    assert session.ended_at is not None
    assert end_of(session, at=datetime.now(UTC)).state is SessionState.COMPLETE


async def test_a_settle_that_does_not_close_the_session_stamps_nothing(
    db_session: AsyncSession,
) -> None:
    session = await create_session(db_session, pericope=P)
    partial = merge(initial_state(P), pericope_num=P, engaged=element_keys(P)[:3])

    session = await apply_coverage(db_session, session.id, partial)

    assert session.ended_at is None


async def test_a_session_closes_once_and_the_end_does_not_move_afterwards(
    db_session: AsyncSession,
) -> None:
    """A second settle on a closed session must not slide its end forward.

    The classifier keeps running for whatever turns were already in flight when the floor
    was met, and each of those is another write. An end re-stamped on every one of them
    would grow the conversation's length after the team had finished.
    """
    session = await create_session(db_session, pericope=P)
    session = await save_comprehension(db_session, session, _fully_supported_comprehension(P))
    whole = merge(initial_state(P), pericope_num=P, engaged=element_keys(P))
    session = await apply_coverage(db_session, session.id, whole)
    closed_at = session.ended_at

    session = await apply_coverage(db_session, session.id, whole)

    assert closed_at is not None
    assert session.ended_at == closed_at


async def test_a_session_needing_a_person_is_marked(db_session: AsyncSession) -> None:
    session = await create_session(db_session, pericope=P)

    session = await mark_needs_person(db_session, session, kind=HaltKind.BLOCKING)

    assert session.status is IRSessionStatus.NEEDS_PERSON


async def _tell(db_session: AsyncSession, session, text: str):
    """One stretch told back, so a case can have one without going through the route."""
    told = await final_segments(db_session, session.id)
    return await capture_segment(
        db_session,
        session,
        take_id="ensaio-1",
        starts_ms=len(told) * 9000,
        ends_ms=(len(told) + 1) * 9000,
        bridge_take_id="retro-1",
        transcript=text,
    )


async def test_the_third_telling_of_a_stretch_reaches_the_warning(db_session: AsyncSession) -> None:
    """The count is the stretch's, so the service decides on the stretch and not on the state.

    Written as arithmetic the test did itself, this case asserted nothing about the room: it
    called `mark_needs_person` and then checked that the room was marked.
    """
    session = await create_session(db_session, pericope=P)
    told = await _tell(db_session, session, "o trecho")
    told.tellings = RETELLS_BEFORE_A_WARNING - 1
    await db_session.commit()

    assert await note_a_hard_stretch(db_session, session, told) is False
    assert session.status is not IRSessionStatus.NEEDS_PERSON

    told.tellings = RETELLS_BEFORE_A_WARNING
    await db_session.commit()

    assert await note_a_hard_stretch(db_session, session, told) is True
    assert session.status is IRSessionStatus.NEEDS_PERSON
    assert session.halt_kind == HaltKind.WARNING.value


async def test_a_session_saved_under_a_purpose_this_build_forgot_still_opens(
    db_session: AsyncSession,
) -> None:
    """Seventeen live sessions on this machine hold a probe purpose that is gone.

    A tablet keeps the session id on disk with no expiry and reopens it: the passage it
    was left in comes back by id, and every turn on it reads this state. A typed submodel
    that no longer validates makes that a 500, and the app only forgets a saved id on a
    404 — so the passage would be stuck on that tablet at every opening, with no way out
    through the app.
    """
    session = await create_session(db_session, language="pt", pericope=P)
    session.comprehension = {
        "ledger": [],
        "active_probe": {
            "id": "probe-1",
            "checkpoint_ids": ["proposition:P01:P1"],
            "method": "micro_tellback",
            "purpose": "initial_check",
            "practice_scene_ids": [],
        },
        "practiced_scene_ids": ["S1"],
    }
    await db_session.commit()

    state = comprehension_of(session)

    assert state.active_probe is None
    assert state.practiced_scene_ids == ["S1"]
