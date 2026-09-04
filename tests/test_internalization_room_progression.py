"""ENG-450 — where a team stands in the book, resolved rather than assumed.

Until this slice the server answered `DEFAULT_PERICOPE = "P01"` to every team, every time.
Fourteen passages of Ruth exist and no team had ever left the first, because there was no
mechanism that could move one.

Three of these carry the slice.

**`test_a_floor_met_across_two_sessions_closes_the_passage`** is the only case that can tell
a real implementation from one reading `ir_sessions.coverage_state`. Every session opens at
`initial_state`, so a passage worked over two evenings has no single session row that knows
it is finished. A resolution reading the session tracker passes every other case here and
fails this one.

**`test_a_gap_earlier_in_the_book_outranks_a_later_passage_already_closed`** is what makes
this *canonical* order and not "the furthest passage touched". A team that skipped ahead is
sent back to what it left open.

**`test_a_bead_the_canon_does_not_serve_cannot_close_a_passage`** pins the direction of the
bias. Whether a passage is finished is `floor_met`'s to say and nothing here counts beads —
a count would let a canon that moved close a passage by arithmetic, which is the one error
that cannot be noticed afterwards: the team is simply gone from a passage they never worked.

The stuck-team case at the end is the failure mode the issue asks to be designed against.
It asserts that the condition is *detectable*, which is all this slice owes; being *told*
is ENG-482.
"""

from __future__ import annotations

import itertools

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.internalization_room import sessions as room
from app.services.internalization_room.canon.book_material import unwalkable
from app.services.internalization_room.canon.elements import element_keys
from app.services.internalization_room.canon.parse_map import ROOM_BOOK, load_book
from app.services.internalization_room.coverage import CoverageStatus
from app.services.internalization_room.progression import (
    PericopePosition,
    active_passage,
    active_passages,
    resolve,
    standing,
    team_standing,
)
from tests.baker import make_language, make_project

_codes = itertools.count()

PARTIALLY_ENGAGED = CoverageStatus.PARTIALLY_ENGAGED.value
SURFACED = CoverageStatus.SURFACED.value
ENGAGED = CoverageStatus.ENGAGED.value

#: The book as this deploy serves it, read from the canon rather than written here: a test
#: naming fourteen would keep passing on the day a fifteenth is vendored.
CANON = [meaning_map.pericope_num for meaning_map in load_book(ROOM_BOOK)]
FIRST, SECOND, THIRD = CANON[0], CANON[1], CANON[2]

#: The passages a team can actually be standing on. The rest are vendored but unwalkable, and
#: the resolution steps over them — so the boundary cases below are about the last passage
#: that opens rather than the last one in the folder.
WALKABLE = [
    meaning_map.pericope_num for meaning_map in load_book(ROOM_BOOK) if not unwalkable(meaning_map)
]
LAST = WALKABLE[-1]


def closed(pericope: str) -> dict[str, str]:
    """Every bead of a passage at the floor — the least reading that finishes it."""
    return dict.fromkeys(element_keys(pericope), PARTIALLY_ENGAGED)


def one_bead_short(pericope: str) -> dict[str, str]:
    """The floor met on every bead but one, which is left where the Guide did the talking."""
    reached = closed(pericope)
    reached[element_keys(pericope)[-1]] = SURFACED
    return reached


def the_whole_book() -> dict[str, dict[str, str]]:
    return {pericope: closed(pericope) for pericope in CANON}


# --------------------------------------------------------------- the resolution, as a function


def test_a_team_with_no_history_stands_on_the_first_passage_of_the_book() -> None:
    """The first acceptance criterion, and it is not the constant it replaces.

    P01 is what the canon's first entry happens to be called. This is resolution arriving
    there because nothing is finished, which is why the expectation is read off the book.
    """
    assert resolve({}) == FIRST


def test_a_finished_passage_moves_the_team_to_the_next_one() -> None:
    assert resolve({FIRST: closed(FIRST)}) == SECOND


def test_a_passage_one_bead_short_of_the_floor_does_not_move_the_team() -> None:
    """`done` is the progression mechanism, so the floor is the whole gate.

    One bead left at `surfaced` — the Guide raised it and the team never took it up — and
    the passage stays open.
    """
    assert resolve({FIRST: one_bead_short(FIRST)}) == FIRST


def test_the_strong_reading_is_not_required_to_move_on() -> None:
    """`partially_engaged` meets the floor, which is what ENG-441 landed for.

    Written as its own case because the fixtures above are all built at the floor: if the
    resolution demanded `engaged` they would fail as a group and read as one broken helper.
    """
    every_bead_fully_worked = {FIRST: dict.fromkeys(element_keys(FIRST), ENGAGED)}

    assert resolve(every_bead_fully_worked) == SECOND
    assert resolve({FIRST: closed(FIRST)}) == SECOND


def test_a_gap_earlier_in_the_book_outranks_a_later_passage_already_closed() -> None:
    """Canonical order, not "the furthest passage touched".

    A team that reached P03 with P02 left open is standing on P02. Nothing in the product
    lets them skip, but the data can hold it — a session can be opened naming a passage —
    and the resolution has to answer the book's order rather than their history's.
    """
    reached = {FIRST: closed(FIRST), THIRD: closed(THIRD)}

    assert resolve(reached) == SECOND


def test_a_bead_the_canon_does_not_serve_cannot_close_a_passage() -> None:
    """Biased against completing hollow, which is `floor_met`'s own rule kept whole.

    A passage whose beads were renamed in the canon leaves the team's events pointing at
    keys nobody serves any more. Counting them would close the passage and move the team
    off work they never did — and no one would ever see it happen.
    """
    keys = element_keys(FIRST)
    as_many_beads_but_not_the_right_ones = dict.fromkeys(keys[:-1], PARTIALLY_ENGAGED)
    as_many_beads_but_not_the_right_ones["being:NOT-IN-THE-CANON"] = PARTIALLY_ENGAGED

    assert resolve({FIRST: as_many_beads_but_not_the_right_ones}) == FIRST


def test_a_team_that_closed_every_passage_stands_on_none() -> None:
    """The end of the book is a defined state and not a wrap-around."""
    assert resolve(the_whole_book()) is None


def test_a_team_that_closed_everything_it_can_walk_is_at_the_end_of_the_book() -> None:
    """The end a team can actually reach, which is earlier than the last vendored passage.

    Ruth's last eight carry no preservation layer, so no session can open on them and their
    floor can never be met. The resolution walked them anyway and answered the first of them
    forever: the team closed the sixth passage and was sent, on every touch after that, to a
    seventh that refuses to open. `None` here is what makes the end-of-book branch reachable
    at all.
    """
    assert resolve({pericope: closed(pericope) for pericope in WALKABLE}) is None


def test_the_last_passage_still_being_worked_is_where_the_team_is() -> None:
    """The boundary beside the case above, so `None` cannot come from an off-by-one."""
    reached = {pericope: closed(pericope) for pericope in CANON[:-1]}
    reached[LAST] = one_bead_short(LAST)

    assert resolve(reached) == LAST


# -------------------------------------------------------------- the fourteen, already resolved


def test_the_standing_names_every_passage_of_the_book_in_the_canons_order() -> None:
    positions = standing({})

    assert [entry.pericope for entry in positions] == CANON
    assert positions[0].reference and positions[0].title


def test_the_standing_marks_one_current_and_the_rest_closed_or_future() -> None:
    """`closed · current · future` resolved here, so no screen decides where a team stands."""
    positions = {entry.pericope: entry.position for entry in standing({FIRST: closed(FIRST)})}

    assert positions[FIRST] is PericopePosition.CLOSED
    assert positions[SECOND] is PericopePosition.CURRENT
    assert positions[THIRD] is PericopePosition.FUTURE


def test_a_passage_closed_out_of_order_reads_closed_while_the_team_stands_earlier() -> None:
    """The two facts are different and the standing must not collapse them.

    `closed` is about the passage's floor; `current` is about where the team is. A team on
    P02 with P03 already finished has both, and exactly one `current`.
    """
    positions = {
        entry.pericope: entry.position
        for entry in standing({FIRST: closed(FIRST), THIRD: closed(THIRD)})
    }

    assert positions[SECOND] is PericopePosition.CURRENT
    assert positions[THIRD] is PericopePosition.CLOSED


def test_a_finished_team_has_no_current_passage() -> None:
    """ENG-469's criterion: a complete team shows its last passage as closed, not current."""
    positions = standing(the_whole_book())

    assert all(entry.position is PericopePosition.CLOSED for entry in positions)


# ------------------------------------------------------------ the resolution, against the table


async def a_team(db: AsyncSession, *, name: str):
    """A project, which is what a team is (D-16), with a language of its own.

    The language code is counted rather than cut from the name: fourteen teams named in a
    series share a prefix, and a collision on that unique column fails the test for a reason
    that has nothing to do with what it asserts.
    """
    language = await make_language(db, name=name, code=f"t{next(_codes):02d}")
    return await make_project(db, language.id, name=name)


async def a_session_that_moved(
    db: AsyncSession, *, project_id: str | None, pericope: str, moved: dict[str, str]
):
    """A session of this team that advanced these beads, through the production path.

    Built with `create_session` and `apply_coverage` rather than by inserting event rows, so
    a fixture cannot agree with a resolution that reads the events differently from how they
    are written.
    """
    session = await room.create_session(db, pericope=pericope, project_id=project_id)
    await room.apply_coverage(db, session.id, moved)
    return session


@pytest.mark.asyncio
async def test_a_team_with_nothing_recorded_resolves_to_the_first_passage(
    db_session: AsyncSession,
) -> None:
    team = await a_team(db_session, name="Sem historia")

    assert await active_passage(db_session, project_id=team.id) == FIRST


@pytest.mark.asyncio
async def test_a_tablet_that_never_said_whose_it_was_resolves_to_the_first_passage(
    db_session: AsyncSession,
) -> None:
    """No project is not an error and must not be one.

    The room's app does not send its device credential yet, so this is the common case in the
    field today rather than the exception. A session that belongs to nobody has no history to
    read, which is the same answer as a team that has not started.
    """
    assert await active_passage(db_session, project_id=None) == FIRST


@pytest.mark.asyncio
async def test_a_floor_met_across_two_sessions_closes_the_passage(
    db_session: AsyncSession,
) -> None:
    """The case that separates the team's necklace from one session's tracker.

    `create_session` opens every session at `initial_state`, so a passage worked over two
    evenings has no session row that knows it is finished. Only the events do.
    """
    team = await a_team(db_session, name="Duas noites")
    keys = element_keys(FIRST)
    half, rest = keys[: len(keys) // 2], keys[len(keys) // 2 :]

    await a_session_that_moved(
        db_session,
        project_id=team.id,
        pericope=FIRST,
        moved=dict.fromkeys(half, PARTIALLY_ENGAGED),
    )
    await a_session_that_moved(
        db_session,
        project_id=team.id,
        pericope=FIRST,
        moved=dict.fromkeys(rest, PARTIALLY_ENGAGED),
    )

    assert await active_passage(db_session, project_id=team.id) == SECOND


@pytest.mark.asyncio
async def test_two_teams_at_different_points_progress_independently(
    db_session: AsyncSession,
) -> None:
    """The acceptance criterion the old constant could not even be wrong about."""
    ahead = await a_team(db_session, name="Adiante")
    behind = await a_team(db_session, name="Atras")

    await a_session_that_moved(db_session, project_id=ahead.id, pericope=FIRST, moved=closed(FIRST))
    await a_session_that_moved(
        db_session, project_id=behind.id, pericope=FIRST, moved=one_bead_short(FIRST)
    )

    resolved = await active_passages(db_session, project_ids=[ahead.id, behind.id])

    assert resolved == {ahead.id: SECOND, behind.id: FIRST}


@pytest.mark.asyncio
async def test_another_teams_work_does_not_move_this_team(db_session: AsyncSession) -> None:
    """Element keys belong to the canon, not to a team: `being:B3` is Naomi for everyone."""
    mine = await a_team(db_session, name="Minha")
    theirs = await a_team(db_session, name="Deles")

    await a_session_that_moved(
        db_session, project_id=theirs.id, pericope=FIRST, moved=closed(FIRST)
    )

    assert await active_passage(db_session, project_id=mine.id) == FIRST


@pytest.mark.asyncio
async def test_a_session_belonging_to_no_team_moves_nobody(db_session: AsyncSession) -> None:
    """Work with no project is nobody's rather than everybody's."""
    team = await a_team(db_session, name="Ninguem")

    await a_session_that_moved(db_session, project_id=None, pericope=FIRST, moved=closed(FIRST))

    assert await active_passage(db_session, project_id=team.id) == FIRST


@pytest.mark.asyncio
async def test_the_whole_roll_is_resolved_without_a_round_trip_per_team(
    db_session: AsyncSession, test_engine
) -> None:
    """Fourteen teams is the Desk's own screen, and it opens first, every time.

    The resolution is derived rather than stored, so the cost of deriving it is the cost of
    the screen. One statement for the roll, not one per team.
    """
    from sqlalchemy import event

    teams = [await a_team(db_session, name=f"Equipe {index:02d}") for index in range(14)]
    for team in teams:
        await a_session_that_moved(
            db_session, project_id=team.id, pericope=FIRST, moved=closed(FIRST)
        )

    read: list[str] = []

    @event.listens_for(test_engine.sync_engine, "before_cursor_execute")
    def _record(conn, cursor, statement, parameters, context, executemany):
        read.append(" ".join(statement.split()))

    try:
        resolved = await active_passages(db_session, project_ids=[team.id for team in teams])
    finally:
        event.remove(test_engine.sync_engine, "before_cursor_execute", _record)

    assert set(resolved.values()) == {SECOND}
    assert len(read) == 1, f"a resolucao custou {len(read)} statements para 14 equipes: {read}"


@pytest.mark.asyncio
async def test_the_standing_of_a_real_team_comes_from_its_own_events(
    db_session: AsyncSession,
) -> None:
    team = await a_team(db_session, name="De pe")
    await a_session_that_moved(db_session, project_id=team.id, pericope=FIRST, moved=closed(FIRST))

    positions = {
        entry.pericope: entry.position for entry in await team_standing(db_session, team.id)
    }

    assert positions[FIRST] is PericopePosition.CLOSED
    assert positions[SECOND] is PericopePosition.CURRENT


# ------------------------------------------------ the failure mode the issue names, made visible


@pytest.mark.asyncio
async def test_a_passage_that_never_closes_holds_the_team_and_says_which_bead(
    db_session: AsyncSession,
) -> None:
    """Classification fails silently, and an element that never classifies is a wall.

    Ruth 1's five preservation rules are the candidates the issue names, because a team
    engages them by *noticing a silence*. If one never lands, the passage never closes, the
    team never advances, and nobody is told. There is no facilitator override — unsticking
    belongs to the team — so what this slice owes is that the condition be **detectable**:
    the team holds its passage, and the bead that is holding them is nameable from the
    events. Turning "detectable" into "someone is told" is ENG-482.
    """
    from app.services.internalization_room.coverage_events import furthest_by_passage

    team = await a_team(db_session, name="Emperrada")
    stuck = element_keys(FIRST)[-1]
    worked = {key: PARTIALLY_ENGAGED for key in element_keys(FIRST) if key != stuck}

    await a_session_that_moved(db_session, project_id=team.id, pericope=FIRST, moved=worked)

    assert await active_passage(db_session, project_id=team.id) == FIRST

    reached = await furthest_by_passage(db_session, project_ids=[team.id])
    below_the_floor = [key for key in element_keys(FIRST) if key not in reached[team.id][FIRST]]

    assert below_the_floor == [stuck]


@pytest.mark.asyncio
async def test_a_later_session_merely_mentioning_a_bead_does_not_take_the_team_backwards(
    db_session: AsyncSession,
) -> None:
    """The reading is the furthest the team ever took a bead, not the last thing said about it.

    Every session opens at `initial_state`, so a bead the team engaged on Tuesday earns a fresh
    `surfaced` event the moment Wednesday's Guide mentions it — against Wednesday's own tracker
    it really did move. At team level it moved nowhere. Ordering by recency instead would read
    that bead back down below the floor, un-close a passage the team had finished, and send
    them back to work it again — with nothing anywhere recording that they had already done it.

    Written as its own case because no other scenario here produces it: all the others close a
    passage and stop, so the two orderings agree and the wrong one goes unnoticed.
    """
    team = await a_team(db_session, name="Voltou a mencionar")
    await a_session_that_moved(db_session, project_id=team.id, pericope=FIRST, moved=closed(FIRST))

    mentioned_again = element_keys(FIRST)[0]
    await a_session_that_moved(
        db_session,
        project_id=team.id,
        pericope=FIRST,
        moved={mentioned_again: SURFACED},
    )

    assert await active_passage(db_session, project_id=team.id) == SECOND
