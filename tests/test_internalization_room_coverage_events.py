"""ENG-445 — the history behind the necklace.

`ir_sessions.coverage_state` says where a session ended up; nothing said how it got there,
which session moved a bead, or what the necklace looked like while an earlier session was
still running. `ir_coverage_events` is that history.

The state stays the fast read. These tests never ask the events for the current state of a
running session — they ask them for what a past session left behind, and for where a team's
whole necklace stands, which is what the Desk's element list and session cards need.

Two reads were written here and both were replaced by `necklace_with_touches` in ENG-449,
which answers a team's whole necklace in one statement. `last_session_to_touch` asked the
same question one bead at a time. `necklace_of` asked a genuinely different one — where a
single session's own spine stood — and nothing ever came to ask it: the Desk's session card
needs the team's accumulated necklace as of that session, which is not the same portrait.

What `necklace_of` was the only reader of is behaviour 4's promise, that the events and
`coverage_state` cannot disagree. That is now asserted against the events themselves. A
helper rebuilding the state inside this file would be a second implementation of the thing
under test, and the two would agree with each other while both drifted from `apply_coverage`.
"""

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models.internalization_room import IRCoverageEvent
from app.services.internalization_room import sessions as service
from app.services.internalization_room.canon.elements import element_keys
from app.services.internalization_room.coverage import CoverageStatus, furthest
from app.services.internalization_room.coverage_events import (
    necklace_with_touches,
    necklaces_of,
    record_transitions,
)

P = "P03"
TEAM = "the-team"
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


async def test_a_sessions_events_are_only_its_own(db_session: AsyncSession) -> None:
    """Behaviour 4 — three sessions on different beads, and the second one still reads true.

    The sessions touch different elements on purpose: a history that quietly folded the whole
    table together would hand back the third session's beads under the second session's id.
    """
    keys = element_keys(P)
    first = await service.create_session(db_session, pericope=P)
    await service.apply_coverage(db_session, first.id, {keys[0]: ENGAGED})

    second = await service.create_session(db_session, pericope=P)
    await service.apply_coverage(db_session, second.id, {keys[1]: SURFACED})
    await service.apply_coverage(db_session, second.id, {keys[1]: ENGAGED})
    await service.apply_coverage(db_session, second.id, {keys[2]: SURFACED})

    third = await service.create_session(db_session, pericope=P)
    await service.apply_coverage(db_session, third.id, {keys[3]: ENGAGED})

    assert await _steps(db_session, second.id) == [
        (keys[1], SURFACED),
        (keys[1], ENGAGED),
        (keys[2], SURFACED),
    ]


async def test_the_two_sources_agree_on_the_most_recent_session(db_session: AsyncSession) -> None:
    """Behaviour 4 — the events and `coverage_state` say the same thing, or one is wrong.

    This is what the table exists to promise, so it is asserted against the events themselves
    rather than through a reconstruction: a helper that rebuilds the state would be this
    file's own second implementation of the thing under test, and the two would agree with
    each other while both drifted from `apply_coverage`.
    """
    keys = element_keys(P)
    session = await service.create_session(db_session, pericope=P)
    await service.apply_coverage(db_session, session.id, {keys[0]: SURFACED, keys[1]: ENGAGED})
    await service.apply_coverage(db_session, session.id, {keys[0]: ENGAGED})

    worked = {
        key: status for key, status in session.coverage_state.items() if status != NOT_ENCOUNTERED
    }
    furthest_per_bead: dict[str, str] = {}
    for key, status in await _steps(db_session, session.id):
        furthest_per_bead[key] = status

    assert worked == {keys[0]: ENGAGED, keys[1]: ENGAGED}
    assert furthest_per_bead == worked


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

    ours_only = await necklace_with_touches(db_session, project_id="project-a", pericope=P)

    assert ours_only[keys[0]].session_id == ours.id
    assert theirs.id != ours.id


async def test_an_untouched_element_has_touched_by_nobody(db_session: AsyncSession) -> None:
    """Behaviour 5 — a bead nobody has worked yet is absent, rather than guessed at.

    The reconstruction lays what came back over the untouched spine, so a bead with no events
    has to be missing from the answer rather than present with an invented status.
    """
    keys = element_keys(P)
    session = await service.create_session(db_session, pericope=P, project_id="project-a")
    await service.apply_coverage(db_session, session.id, {keys[0]: ENGAGED})

    walked = await necklace_with_touches(db_session, project_id="project-a", pericope=P)

    assert keys[0] in walked
    assert keys[1] not in walked


async def test_two_settles_that_read_the_same_state_do_not_lose_a_merge(
    db_session: AsyncSession, test_engine
) -> None:
    """Two turns overlapping is ordinary, and the second one must not be thrown away.

    The classifier for turn seven is still on its round trip when turn eight lands, and
    each settle opens its own transaction. Both read the same tracker, so both write the
    same step for the bead they agree on — and the later one also carries a bead only it
    heard.

    `furthest` exists to absorb exactly this. If the database refused the repeated step as
    a duplicate it would take that whole second transaction down with it, and the bead only
    the second settle heard would be gone: the merge would fail at the one moment it was
    written for.
    """
    session = await service.create_session(db_session, pericope=P)
    session_id = session.id
    keys = element_keys(P)
    read_by_both = dict(session.coverage_state)

    seventh = furthest(read_by_both, {keys[0]: SURFACED}, pericope_num=P)
    eighth = furthest(read_by_both, {keys[0]: SURFACED, keys[1]: ENGAGED}, pericope_num=P)

    settling = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with settling() as seventh_turn, settling() as eighth_turn:
        record_transitions(seventh_turn, session, before=read_by_both, after=seventh)
        await seventh_turn.commit()
        record_transitions(eighth_turn, session, before=read_by_both, after=eighth)
        await eighth_turn.commit()

    await db_session.rollback()
    assert (keys[1], ENGAGED) in await _steps(db_session, session_id), (
        "the bead only the later settle heard was lost with its transaction"
    )


async def test_a_card_shows_the_necklace_as_it_stood_when_that_conversation_ended(
    db_session: AsyncSession,
) -> None:
    """ENG-451 — RF-06 asks for the portrait *at that moment*, which accumulates.

    A card showing only what its own conversation moved would sit under a panel showing
    everything the team has done and disagree with it, which is the one thing the issue says
    must not happen. `necklace_of` above answers the other question and says so.
    """
    keys = element_keys(P)
    first = await service.create_session(db_session, pericope=P, project_id=TEAM)
    await service.apply_coverage(db_session, first.id, {keys[0]: ENGAGED})

    second = await service.create_session(db_session, pericope=P, project_id=TEAM)
    await service.apply_coverage(db_session, second.id, {keys[1]: ENGAGED})

    rebuilt = await necklaces_of(db_session, [second, first])

    assert rebuilt[first.id][keys[0]] == ENGAGED
    assert rebuilt[first.id][keys[1]] == NOT_ENCOUNTERED, "a later conversation leaked backwards"
    assert rebuilt[second.id][keys[0]] == ENGAGED, (
        "Tuesday's bead vanished from Wednesday's card; the portrait is a diff, not a state"
    )
    assert rebuilt[second.id][keys[1]] == ENGAGED


async def test_two_conversations_on_one_bead_stay_on_their_own_cards(
    db_session: AsyncSession,
) -> None:
    """The common case, not the rare one — and the case a grouping without the session leaks.

    The first version of this test had the two conversations touching different beads, which
    left exactly one row per group: dropping the session from the grouping still answered
    correctly and the mutation survived. Two conversations moving the *same* bead is what a
    team actually does, and it is what makes the grouping observable.
    """
    keys = element_keys(P)
    first = await service.create_session(db_session, pericope=P, project_id=TEAM)
    await service.apply_coverage(db_session, first.id, {keys[0]: SURFACED})

    second = await service.create_session(db_session, pericope=P, project_id=TEAM)
    await service.apply_coverage(db_session, second.id, {keys[0]: ENGAGED})

    rebuilt = await necklaces_of(db_session, [second, first])

    assert rebuilt[first.id][keys[0]] == SURFACED, (
        "the later conversation's step reached the earlier conversation's card"
    )
    assert rebuilt[second.id][keys[0]] == ENGAGED


async def test_a_bead_already_engaged_is_not_walked_back_by_a_later_mention(
    db_session: AsyncSession,
) -> None:
    """Furthest rank, never most recent — the rule the facilitator's panel already uses.

    Every session opens at `initial_state`, so a bead the team engaged on Tuesday earns a
    fresh `surfaced` step the moment Wednesday's Guide mentions it: against Wednesday's own
    tracker it really did move, and at team level it moved nowhere. Reading the latest step
    instead would show the bead going backwards on the newer card.
    """
    keys = element_keys(P)
    tuesday = await service.create_session(db_session, pericope=P, project_id=TEAM)
    await service.apply_coverage(db_session, tuesday.id, {keys[0]: ENGAGED})

    wednesday = await service.create_session(db_session, pericope=P, project_id=TEAM)
    await service.apply_coverage(db_session, wednesday.id, {keys[0]: SURFACED})

    rebuilt = await necklaces_of(db_session, [wednesday, tuesday])

    assert rebuilt[wednesday.id][keys[0]] == ENGAGED


async def test_one_passage_does_not_accumulate_into_another(db_session: AsyncSession) -> None:
    """A team walks the book, and the passages share beads — which is what makes this bite.

    The first version put a P05 conversation with no steps of its own beside a P03 one and
    asked for nothing to have crossed. It passed with the grouping mutated away, because a
    conversation with no steps has no instant of its own and sorted first by accident of the
    database's one-second clock. Naomi is `being:B3` in both passages, so the honest version
    engages a **shared** key over here and gives the P05 conversation a step of its own, so
    it is genuinely the later of the two.
    """
    other = "P05"
    shared = "being:B3"
    only_there = "being:B13"
    assert shared in element_keys(P) and shared in element_keys(other)
    assert only_there not in element_keys(P)

    here = await service.create_session(db_session, pericope=P, project_id=TEAM)
    await service.apply_coverage(db_session, here.id, {shared: ENGAGED})

    there = await service.create_session(db_session, pericope=other, project_id=TEAM)
    await service.apply_coverage(db_session, there.id, {only_there: SURFACED})

    rebuilt = await necklaces_of(db_session, [there, here])

    assert rebuilt[there.id][shared] == NOT_ENCOUNTERED, (
        "the other passage's bead crossed over; an element key is the canon's, not a team's"
    )
    assert rebuilt[there.id][only_there] == SURFACED
    assert rebuilt[here.id][shared] == ENGAGED


async def test_rebuilding_no_sessions_asks_the_database_nothing(db_session: AsyncSession) -> None:
    """A team that has never met is the ordinary case, not an edge one."""
    assert await necklaces_of(db_session, []) == {}


async def test_a_panorama_session_has_no_spine_to_rebuild(db_session: AsyncSession) -> None:
    """`OV-Ruth` addresses the book rather than a passage, so there are no beads.

    It is answered empty rather than refused: a panorama is a conversation the team really
    held, and dropping it from their history would hide it. The Desk draws an empty portrait
    as a conversation that reached nothing, which is what happened.
    """
    panorama = await service.create_session(db_session, pericope="OV", project_id=TEAM)

    assert await necklaces_of(db_session, [panorama]) == {panorama.id: {}}
