"""ENG-445 — the history behind the necklace.

`ir_sessions.coverage_state` says where a session ended up; nothing said how it got there,
which session moved a bead, or what the necklace looked like while an earlier session was
still running. `ir_coverage_events` is that history.

The state stays the fast read. These tests never ask the events for the current state of a
running session — they ask them for what a past session left behind, and for who touched an
element last, which is what the Desk's element list and session cards need.
"""

from collections.abc import Sequence

from app.services.internalization_room.coverage_events import (
    last_session_to_touch,
    necklace_of,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRCoverageEvent
from app.services.internalization_room import sessions as service
from app.services.internalization_room.canon.elements import element_keys
from app.services.internalization_room.coverage import CoverageStatus

P = "P03"
SURFACED = CoverageStatus.SURFACED.value
ENGAGED = CoverageStatus.ENGAGED.value
NOT_ENCOUNTERED = CoverageStatus.NOT_ENCOUNTERED.value


async def _events(db: AsyncSession, session_id: str) -> Sequence[IRCoverageEvent]:
    result = await db.execute(
        select(IRCoverageEvent)
        .where(IRCoverageEvent.session_id == session_id)
        .order_by(IRCoverageEvent.at, IRCoverageEvent.id)
    )
    return result.scalars().all()


async def _steps(db: AsyncSession, session_id: str) -> list[tuple[str, str]]:
    return [(event.element_key, event.status) for event in await _events(db, session_id)]


async def test_a_transition_writes_one_event(db_session: AsyncSession) -> None:
    """Behaviour 1 — every transition, exactly one event."""
    session = await service.create_session(db_session, pericope=P)
    keys = element_keys(P)

    await service.apply_coverage(db_session, session.id, {keys[0]: SURFACED})

    assert await _steps(db_session, session.id) == [(keys[0], SURFACED)]


async def test_two_transitions_write_two_events(db_session: AsyncSession) -> None:
    """Behaviour 1 — the same bead moving twice leaves both steps behind."""
    session = await service.create_session(db_session, pericope=P)
    keys = element_keys(P)

    await service.apply_coverage(db_session, session.id, {keys[0]: SURFACED})
    await service.apply_coverage(db_session, session.id, {keys[0]: ENGAGED})

    assert await _steps(db_session, session.id) == [
        (keys[0], SURFACED),
        (keys[0], ENGAGED),
    ]


async def test_two_beads_moving_in_one_merge_are_two_events(db_session: AsyncSession) -> None:
    """Behaviour 1 — one event per element that moved, not one per merge."""
    session = await service.create_session(db_session, pericope=P)
    keys = element_keys(P)

    await service.apply_coverage(db_session, session.id, {keys[0]: SURFACED, keys[1]: ENGAGED})

    assert sorted(await _steps(db_session, session.id)) == sorted(
        [(keys[0], SURFACED), (keys[1], ENGAGED)]
    )


async def test_a_merge_that_changes_nothing_writes_no_event(db_session: AsyncSession) -> None:
    """Behaviour 2 — volume is bounded by transitions, not by turns.

    The classifier runs after every turn and mostly reports what is already stored. If the
    event were written before the comparison, a session of forty turns would leave forty
    rows per bead and the table would be a turn log wearing a coverage name.
    """
    session = await service.create_session(db_session, pericope=P)
    keys = element_keys(P)
    await service.apply_coverage(db_session, session.id, {keys[0]: ENGAGED})

    await service.apply_coverage(db_session, session.id, {keys[0]: ENGAGED})
    await service.apply_coverage(db_session, session.id, {keys[0]: ENGAGED})

    assert await _steps(db_session, session.id) == [(keys[0], ENGAGED)]


async def test_a_session_that_moved_nothing_has_no_events(db_session: AsyncSession) -> None:
    """Behaviour 2 — a merge that reports the untouched spine writes nothing at all."""
    session = await service.create_session(db_session, pericope=P)

    await service.apply_coverage(
        db_session, session.id, dict.fromkeys(element_keys(P), NOT_ENCOUNTERED)
    )

    assert await _steps(db_session, session.id) == []


async def test_a_lower_status_is_not_recorded(db_session: AsyncSession) -> None:
    """Behaviour 3 — coverage does not walk backwards, and neither does its history.

    A stale classifier reading arriving late is ordinary. `coverage_state` already refuses
    it; an event written anyway would make the history disagree with the state it explains.
    """
    session = await service.create_session(db_session, pericope=P)
    keys = element_keys(P)
    await service.apply_coverage(db_session, session.id, {keys[0]: ENGAGED})

    await service.apply_coverage(db_session, session.id, {keys[0]: SURFACED})

    assert await _steps(db_session, session.id) == [(keys[0], ENGAGED)]
    assert session.coverage_state[keys[0]] == ENGAGED


async def test_the_necklace_of_a_past_session_comes_back_whole(db_session: AsyncSession) -> None:
    """Behaviour 4 — three sessions on different beads, and the second one still reads true.

    The sessions touch different elements on purpose: a reconstruction that quietly folded
    the whole table would hand back the third session's beads on the second session's card.
    """
    keys = element_keys(P)
    first = await service.create_session(db_session, pericope=P)
    await service.apply_coverage(db_session, first.id, {keys[0]: ENGAGED})

    second = await service.create_session(db_session, pericope=P)
    await service.apply_coverage(db_session, second.id, {keys[1]: SURFACED})
    await service.apply_coverage(db_session, second.id, {keys[1]: ENGAGED})
    await service.apply_coverage(db_session, second.id, {keys[2]: SURFACED})
    at_the_end_of_the_second = dict(second.coverage_state)

    third = await service.create_session(db_session, pericope=P)
    await service.apply_coverage(db_session, third.id, {keys[3]: ENGAGED})

    reconstructed = await necklace_of(db_session, second)

    assert set(reconstructed) == set(keys), "the portrait has to carry the whole spine"
    assert reconstructed == at_the_end_of_the_second
    assert reconstructed[keys[0]] == NOT_ENCOUNTERED, "the first session's bead leaked in"
    assert reconstructed[keys[3]] == NOT_ENCOUNTERED, "a later session's bead leaked in"


async def test_the_two_sources_agree_on_the_most_recent_session(db_session: AsyncSession) -> None:
    """Behaviour 4 — the events and `coverage_state` say the same thing, or one is wrong."""
    keys = element_keys(P)
    session = await service.create_session(db_session, pericope=P)
    await service.apply_coverage(db_session, session.id, {keys[0]: SURFACED, keys[1]: ENGAGED})
    await service.apply_coverage(db_session, session.id, {keys[0]: ENGAGED})

    assert await necklace_of(db_session, session) == session.coverage_state


async def test_the_last_session_to_touch_an_element(db_session: AsyncSession) -> None:
    """Behaviour 5 — the element list asks who moved this bead, and gets one answer."""
    keys = element_keys(P)
    earlier = await service.create_session(db_session, pericope=P, project_id="project-a")
    await service.apply_coverage(db_session, earlier.id, {keys[0]: SURFACED})

    later = await service.create_session(db_session, pericope=P, project_id="project-a")
    await service.apply_coverage(db_session, later.id, {keys[0]: ENGAGED})

    touched_by = await last_session_to_touch(
        db_session, project_id="project-a", pericope=P, element_key=keys[0]
    )

    assert touched_by == later.id


async def test_another_project_working_the_same_passage_is_not_the_answer(
    db_session: AsyncSession,
) -> None:
    """Behaviour 5 — element keys come from the canon, so two teams on Ruth share them.

    `being:B3` is Naomi in every project that works this passage. Answering "who touched
    this bead" without saying whose bead would hand one team the other team's session.
    """
    keys = element_keys(P)
    ours = await service.create_session(db_session, pericope=P, project_id="project-a")
    await service.apply_coverage(db_session, ours.id, {keys[0]: ENGAGED})

    theirs = await service.create_session(db_session, pericope=P, project_id="project-b")
    await service.apply_coverage(db_session, theirs.id, {keys[0]: ENGAGED})

    assert (
        await last_session_to_touch(
            db_session, project_id="project-a", pericope=P, element_key=keys[0]
        )
        == ours.id
    )


async def test_an_untouched_element_has_touched_by_nobody(db_session: AsyncSession) -> None:
    """Behaviour 5 — a bead nobody has worked yet answers with nothing, not with a guess."""
    keys = element_keys(P)
    session = await service.create_session(db_session, pericope=P, project_id="project-a")
    await service.apply_coverage(db_session, session.id, {keys[0]: ENGAGED})

    assert (
        await last_session_to_touch(
            db_session, project_id="project-a", pericope=P, element_key=keys[1]
        )
        is None
    )
