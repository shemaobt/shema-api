"""ENG-803 — the necklace outlives the conversation that strung it.

A team works Ruth 1:1-5 on Tuesday, closes the tablet in the middle of the third scene, and
comes back on Thursday. `create_session` opened every session at `initial_state`, so the beads
they filled on Tuesday read `not_encountered` on Thursday's tracker, the Guide was handed a
REMAINING block naming the whole passage again, and the room walked the team back through
parts they already had.

The team-level reading these seed from already existed and answered only the facilitator's
route — `necklace_with_touches` folds a team's coverage events across sessions, and says why
in its own docstring.
"""

from __future__ import annotations

import itertools

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.internalization_room import sessions as room
from app.services.internalization_room.canon.elements import element_keys
from app.services.internalization_room.canon.parse_map import ROOM_BOOK, load_book
from app.services.internalization_room.coverage import CoverageStatus, floor_met
from app.services.internalization_room.progression import active_passage
from app.services.internalization_room.prompt_blocks import coverage_status_block
from tests.baker import (
    fully_supported_comprehension,
    keep_a_take,
    make_language,
    make_project,
)

_codes = itertools.count()

NOT_ENCOUNTERED = CoverageStatus.NOT_ENCOUNTERED.value
PARTIALLY_ENGAGED = CoverageStatus.PARTIALLY_ENGAGED.value
ENGAGED = CoverageStatus.ENGAGED.value

#: Ruth 1:1-5 and what follows it, read from the book rather than written here.
FIRST, SECOND = (meaning_map.pericope_num for meaning_map in load_book(ROOM_BOOK)[:2])


async def a_team(db: AsyncSession, *, name: str):
    """A project, which is what a team is (D-16), with a language of its own."""
    language = await make_language(db, name=name, code=f"n{next(_codes):02d}")
    return await make_project(db, language.id, name=name)


@pytest.mark.asyncio
async def test_a_second_session_opens_with_the_beads_the_team_already_filled(
    db_session: AsyncSession,
) -> None:
    """Thursday's necklace is Tuesday's, at the status Tuesday left each bead on."""
    team = await a_team(db_session, name="Terca e quinta")
    keys = element_keys(FIRST)
    tuesday = await room.create_session(db_session, pericope=FIRST, project_id=team.id)
    worked = {keys[0]: ENGAGED, keys[1]: PARTIALLY_ENGAGED}
    await room.apply_coverage(db_session, tuesday.id, worked)

    thursday = await room.create_session(db_session, pericope=FIRST, project_id=team.id)

    assert thursday.coverage_state == {**dict.fromkeys(keys, NOT_ENCOUNTERED), **worked}


@pytest.mark.asyncio
async def test_a_tablet_that_never_said_whose_it_is_still_opens_on_an_empty_necklace(
    db_session: AsyncSession,
) -> None:
    """Work with no project is nobody's rather than everybody's.

    The room app sends its device credential only from ENG-454 onward, so a session with no
    team is the common case in the field rather than the exception — and there is no history
    to read for one. Carrying the unowned beads instead would hand every such tablet the
    accumulated work of every other unowned tablet in the installation.
    """
    keys = element_keys(FIRST)
    somebody_elses = await room.create_session(db_session, pericope=FIRST, project_id=None)
    await room.apply_coverage(db_session, somebody_elses.id, {keys[0]: ENGAGED})

    session = await room.create_session(db_session, pericope=FIRST, project_id=None)

    assert session.coverage_state == dict.fromkeys(keys, NOT_ENCOUNTERED)


@pytest.mark.asyncio
async def test_the_guide_is_handed_only_what_the_team_still_has_left(
    db_session: AsyncSession,
) -> None:
    """The REMAINING block is the whole point of carrying the necklace.

    The Guide is shown this list and nothing else, so a room that opened at `initial_state`
    was told the team had the whole passage still to work and walked them back through parts
    they already had.
    """
    team = await a_team(db_session, name="So falta uma")
    keys = element_keys(FIRST)
    tuesday = await room.create_session(db_session, pericope=FIRST, project_id=team.id)
    await room.apply_coverage(db_session, tuesday.id, dict.fromkeys(keys[:-1], ENGAGED))

    thursday = await room.create_session(db_session, pericope=FIRST, project_id=team.id)

    block = coverage_status_block(thursday.coverage_state, FIRST)
    assert f"[{keys[-1]}]" in block
    assert [key for key in keys[:-1] if f"[{key}]" in block] == []


@pytest.mark.asyncio
async def test_a_team_that_closed_the_tablet_mid_passage_finishes_it_on_the_second_evening(
    db_session: AsyncSession,
) -> None:
    """The ticket end to end, and where its two halves meet.

    Thursday's session is opened without naming a passage, so the resolution answers it: the
    passage is still the team's because nothing finished it on Tuesday. It opens on Tuesday's
    beads, which is what lets one more evening's work reach the floor at all — against a fresh
    tracker the second evening would only ever have half the passage on it.

    Then the two facts, in the order the room meets them. `session_is_done` goes true and the
    app opens the way to the rehearsal — and Ruth 1:1-5 is still the passage the team is
    handed, because reaching the recording is not having recorded. The take lands and only
    then does the passage stop being theirs.
    """
    team = await a_team(db_session, name="Fechou no meio da terceira cena")
    keys = element_keys(FIRST)
    half, rest = keys[: len(keys) // 2], keys[len(keys) // 2 :]

    tuesday = await room.create_session(db_session, pericope=FIRST, project_id=team.id)
    await room.apply_coverage(db_session, tuesday.id, dict.fromkeys(half, PARTIALLY_ENGAGED))

    thursday = await room.create_session(db_session, project_id=team.id)
    assert thursday.pericope == FIRST, "a passagem inacabada deixou de ser a da equipe"

    thursday = await room.save_comprehension(
        db_session, thursday, fully_supported_comprehension(FIRST)
    )
    thursday = await room.apply_coverage(
        db_session, thursday.id, dict.fromkeys(rest, PARTIALLY_ENGAGED)
    )

    assert floor_met(thursday.coverage_state, FIRST), (
        "a segunda noite so tinha metade da passagem no proprio tracker"
    )
    assert room.session_is_done(thursday), "a equipe nao chegaria a entrada do ensaio"
    assert await active_passage(db_session, project_id=team.id) == FIRST, (
        "a passagem fechou na entrada do ensaio, antes de a equipe gravar"
    )

    await keep_a_take(db_session, thursday)

    assert await active_passage(db_session, project_id=team.id) == SECOND
