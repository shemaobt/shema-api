"""ENG-450 — where a team stands in the book, resolved rather than assumed.

Until this slice the server answered `DEFAULT_PERICOPE = "P01"` to every team, every time.
Fourteen passages of Ruth exist and no team had ever left the first, because there was no
mechanism that could move one.

Three of these carry the slice.

**`test_a_floor_met_across_two_evenings_does_not_close_the_passage`** is the case ENG-803
turned around. It used to assert the opposite: a floor met across two sessions closed the
passage and moved the team on. The ledger informs, it never ends the conversation
(`DOCTRINE.md` §4) — a team that met the floor and closed the tablet in the middle of the
third scene had not finished anything, and a number carried them off it.

**`test_a_gap_earlier_in_the_book_outranks_a_later_passage_already_closed`** is what makes
this *canonical* order and not "the furthest passage touched". A team that skipped ahead is
sent back to what it left open.

**`test_a_session_the_team_finished_closes_the_passage`** is the other half, and the two are
only meaningful together: a rule that never closes anything passes the first one alone.

The stuck-team case at the end is the failure mode the issue asks to be designed against.
It asserts that the condition is *detectable*, which is all this slice owes; being *told*
is ENG-482.
"""

from __future__ import annotations

import itertools

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.room_enums import HaltKind
from app.db.models.internalization_room import IRSessionStatus, IRTakeKind
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
from tests.baker import (
    fully_supported_comprehension,
    having_finished_the_passage,
    keep_a_take,
    make_language,
    make_project,
)

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


def at_the_floor(pericope: str) -> dict[str, str]:
    """Every bead of a passage at the floor — which no longer finishes anything."""
    return dict.fromkeys(element_keys(pericope), PARTIALLY_ENGAGED)


def one_bead_short(pericope: str) -> dict[str, str]:
    """The floor met on every bead but one, which is left where the Guide did the talking."""
    reached = at_the_floor(pericope)
    reached[element_keys(pericope)[-1]] = SURFACED
    return reached


# --------------------------------------------------------------- the resolution, as a function


def test_a_team_with_no_history_stands_on_the_first_passage_of_the_book() -> None:
    """The first acceptance criterion, and it is not the constant it replaces.

    P01 is what the canon's first entry happens to be called. This is resolution arriving
    there because nothing is finished, which is why the expectation is read off the book.
    """
    assert resolve(set()) == FIRST


def test_a_finished_passage_moves_the_team_to_the_next_one() -> None:
    assert resolve({FIRST}) == SECOND


def test_a_gap_earlier_in_the_book_outranks_a_later_passage_already_closed() -> None:
    """Canonical order, not "the furthest passage touched".

    A team that reached P03 with P02 left open is standing on P02. Nothing in the product
    lets them skip, but the data can hold it — a session can be opened naming a passage —
    and the resolution has to answer the book's order rather than their history's.
    """
    assert resolve({FIRST, THIRD}) == SECOND


def test_a_team_that_closed_every_passage_stands_on_none() -> None:
    """The end of the book is a defined state and not a wrap-around."""
    assert resolve(set(CANON)) is None


def test_a_team_that_closed_everything_it_can_walk_is_at_the_end_of_the_book() -> None:
    """The end a team can actually reach, which is earlier than the last vendored passage.

    The passages past the canon's edge carry no preservation layer, so no session can open
    on them and their floor can never be met. The resolution walked them anyway and answered
    the first of them forever: the team closed the last passage that opens and was sent, on
    every touch after that, to one that refuses to open. `None` here is what makes the
    end-of-book branch reachable at all.
    """
    assert resolve(set(WALKABLE)) is None


def test_the_last_passage_still_being_worked_is_where_the_team_is() -> None:
    """The boundary beside the case above, so `None` cannot come from an off-by-one."""
    assert resolve(set(CANON[:-1]) - {LAST}) == LAST


def test_a_team_that_closed_ruth_2_8_16_is_sent_on_and_not_to_the_end_of_the_book() -> None:
    """The end of the book moved because the canon moved, and no line of the resolution did.

    The seventh passage's withholdings were written on 31 August and the vendored copy
    predated them, so `unwalkable` refused it and the step-over swallowed it: a team that
    finished the field was answered `None` and heard, from every touch after that, that the
    book had nothing left in it. Both passages are named here by the reference the canon
    files them under, so this reads the same the day a fifteenth is vendored.
    """
    filed_under = {
        meaning_map.reference: meaning_map.pericope_num for meaning_map in load_book(ROOM_BOOK)
    }
    field, gleaning = filed_under["Ruth 2:8-16"], filed_under["Ruth 2:17-23"]

    assert resolve(set(CANON[: CANON.index(field) + 1])) == gleaning, (
        "quem fechou 2:8-16 ouvia que o livro tinha acabado, com sete passagens ainda na pasta"
    )


# -------------------------------------------------------------- the fourteen, already resolved


def test_the_standing_names_every_passage_of_the_book_in_the_canons_order() -> None:
    positions = standing(set())

    assert [entry.pericope for entry in positions] == CANON
    assert positions[0].reference and positions[0].title


def test_the_standing_marks_one_current_and_the_rest_closed_or_future() -> None:
    """`closed · current · future` resolved here, so no screen decides where a team stands."""
    positions = {entry.pericope: entry.position for entry in standing({FIRST})}

    assert positions[FIRST] is PericopePosition.CLOSED
    assert positions[SECOND] is PericopePosition.CURRENT
    assert positions[THIRD] is PericopePosition.FUTURE


def test_a_passage_closed_out_of_order_reads_closed_while_the_team_stands_earlier() -> None:
    """The two facts are different and the standing must not collapse them.

    `closed` is a session the team finished; `current` is where the team is. A team on P02
    with P03 already finished has both, and exactly one `current`.
    """
    positions = {entry.pericope: entry.position for entry in standing({FIRST, THIRD})}

    assert positions[SECOND] is PericopePosition.CURRENT
    assert positions[THIRD] is PericopePosition.CLOSED


def test_a_finished_team_has_no_current_passage() -> None:
    """ENG-469's criterion: a complete team shows its last passage as closed, not current."""
    positions = standing(set(CANON))

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


async def a_session_the_team_finished(db: AsyncSession, *, project_id: str | None, pericope: str):
    """A conversation this team took to its end — their own recording of the passage.

    Through the room's own two steps rather than by writing `done` on a row, so a fixture
    cannot agree with a resolution that reads a finished session differently from how one is
    actually finished.
    """
    session = await room.create_session(db, pericope=pericope, project_id=project_id)
    return await having_finished_the_passage(db, session)


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
async def test_a_floor_met_across_two_evenings_does_not_close_the_passage(
    db_session: AsyncSession,
) -> None:
    """The case ENG-803 turned around: this used to send the team on to the second passage.

    Two evenings of work that between them touched every bead is a floor met and nothing
    else. The team never reached the end of a conversation on it — no send-off, no
    recording — so the passage is still theirs, and a number must not carry them off it.
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

    assert await active_passage(db_session, project_id=team.id) == FIRST


@pytest.mark.asyncio
async def test_a_session_the_team_finished_closes_the_passage(
    db_session: AsyncSession,
) -> None:
    """The other half, and the two are only meaningful together.

    A rule that closes nothing passes the case above on its own and holds every team on the
    first passage of the book forever.
    """
    team = await a_team(db_session, name="Gravou")

    await a_session_the_team_finished(db_session, project_id=team.id, pericope=FIRST)

    assert await active_passage(db_session, project_id=team.id) == SECOND


@pytest.mark.asyncio
async def test_a_session_that_reached_the_rehearsal_and_never_recorded_leaves_the_passage_open(
    db_session: AsyncSession,
) -> None:
    """`done` and `closed` are two facts, and this is the case that separates them.

    `session_is_done` is the signal the room reads to send a team to the recording — the
    floor, the evidence, the practice, the consent. Reaching it is not having recorded, and
    the passage stays the team's until they do. A rule reading the session's own `done` would
    close the passage on the invitation.
    """
    team = await a_team(db_session, name="Chegou ao ensaio e parou")
    session = await room.create_session(db_session, pericope=FIRST, project_id=team.id)
    await room.save_comprehension(db_session, session, fully_supported_comprehension(FIRST))

    settled = await room.apply_coverage(db_session, session.id, at_the_floor(FIRST))

    assert settled.status is IRSessionStatus.DONE, "a sessao nem chegou a liberar o ensaio"
    assert await active_passage(db_session, project_id=team.id) == FIRST


@pytest.mark.asyncio
async def test_a_halt_after_the_rehearsal_does_not_hand_the_passage_back(
    db_session: AsyncSession,
) -> None:
    """A passage the team finished cannot be re-opened by the room stopping.

    `mark_needs_person` writes the status with no guard on what it was, and a landing turn
    puts a halted session back to `in_progress` and never to `done`. The halt is reachable
    from here: the back-translation route refuses a session with no rehearsal take, so every
    retell warning it raises lands on a session that has already recorded. A team that
    finished Ruth 1:1-5 and then struggled to tell one stretch back would be handed the
    passage again, with their recording sitting in the bucket.

    Which is why the mark read is `ended_at` and not the status: the close is stamped there
    at the same instant and no halt writes over it.
    """
    team = await a_team(db_session, name="Gravou e depois a sala parou")
    session = await a_session_the_team_finished(db_session, project_id=team.id, pericope=FIRST)

    await room.mark_needs_person(db_session, session, kind=HaltKind.BLOCKING)

    assert await active_passage(db_session, project_id=team.id) == SECOND


@pytest.mark.asyncio
async def test_a_recording_on_a_session_the_room_never_sent_to_rehearse_closes_nothing(
    db_session: AsyncSession,
) -> None:
    """The other half of the same rule, and the reason both are asked for.

    The route that keeps a take asks nothing about the conversation it belongs to, so a
    recording can reach a session the room never judged worked. Closing on the recording
    alone would carry the team off a passage whose beads nobody worked — the floor exists
    to stop exactly that, and it is still the gate on the invitation to record.
    """
    team = await a_team(db_session, name="Gravou sem ter trabalhado")
    session = await room.create_session(db_session, pericope=FIRST, project_id=team.id)

    await keep_a_take(db_session, session)

    assert session.status is IRSessionStatus.IN_PROGRESS, "a sessao ja estava fechada"
    assert await active_passage(db_session, project_id=team.id) == FIRST


@pytest.mark.asyncio
async def test_a_stretch_told_back_is_not_the_rehearsal_and_closes_nothing(
    db_session: AsyncSession,
) -> None:
    """A retro is the team explaining one stretch to the room. The passage is still theirs."""
    team = await a_team(db_session, name="Contou de volta")
    session = await room.create_session(db_session, pericope=FIRST, project_id=team.id)
    await room.save_comprehension(db_session, session, fully_supported_comprehension(FIRST))
    settled = await room.apply_coverage(db_session, session.id, at_the_floor(FIRST))

    await keep_a_take(db_session, settled, kind=IRTakeKind.RETRO)

    assert await active_passage(db_session, project_id=team.id) == FIRST


@pytest.mark.asyncio
async def test_two_teams_at_different_points_progress_independently(
    db_session: AsyncSession,
) -> None:
    """The acceptance criterion the old constant could not even be wrong about.

    The team behind is at the floor on every bead of the passage, which is as far as a
    conversation goes without ending: the two teams differ by a recording and nothing else.
    """
    ahead = await a_team(db_session, name="Adiante")
    behind = await a_team(db_session, name="Atras")

    await a_session_the_team_finished(db_session, project_id=ahead.id, pericope=FIRST)
    await a_session_that_moved(
        db_session, project_id=behind.id, pericope=FIRST, moved=at_the_floor(FIRST)
    )

    resolved = await active_passages(db_session, project_ids=[ahead.id, behind.id])

    assert resolved == {ahead.id: SECOND, behind.id: FIRST}


@pytest.mark.asyncio
async def test_another_teams_work_does_not_move_this_team(db_session: AsyncSession) -> None:
    """A finished session belongs to the team that held it, and moves nobody else."""
    mine = await a_team(db_session, name="Minha")
    theirs = await a_team(db_session, name="Deles")

    await a_session_the_team_finished(db_session, project_id=theirs.id, pericope=FIRST)

    assert await active_passage(db_session, project_id=mine.id) == FIRST


@pytest.mark.asyncio
async def test_a_session_belonging_to_no_team_moves_nobody(db_session: AsyncSession) -> None:
    """Work with no project is nobody's rather than everybody's."""
    team = await a_team(db_session, name="Ninguem")

    await a_session_the_team_finished(db_session, project_id=None, pericope=FIRST)

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
        await a_session_the_team_finished(db_session, project_id=team.id, pericope=FIRST)

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
async def test_the_standing_of_a_real_team_comes_from_its_own_finished_sessions(
    db_session: AsyncSession,
) -> None:
    team = await a_team(db_session, name="De pe")
    await a_session_the_team_finished(db_session, project_id=team.id, pericope=FIRST)

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
async def test_a_later_conversation_on_a_finished_passage_does_not_reopen_it(
    db_session: AsyncSession,
) -> None:
    """A team can be given a finished passage by name, and it stays finished.

    The wheel keeps a finished passage enterable, so a team going back into one is ordinary
    rather than an anomaly. What must not happen is that going back in makes it the team's
    next passage again and holds them there — nothing in the second conversation un-does the
    recording the first one ended with.

    Written as its own case because every other scenario here finishes a passage and stops,
    so a rule that closed on the *latest* session would agree with this one everywhere else.
    """
    team = await a_team(db_session, name="Voltou a entrar")
    await a_session_the_team_finished(db_session, project_id=team.id, pericope=FIRST)

    await a_session_that_moved(
        db_session,
        project_id=team.id,
        pericope=FIRST,
        moved={element_keys(FIRST)[0]: SURFACED},
    )

    assert await active_passage(db_session, project_id=team.id) == SECOND
