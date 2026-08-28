"""Where a team stands in the book, resolved from its own history.

The team walks the book on its own, in canonical order, without a facilitator convening
anything (D-03). Choosing the passage is therefore the server's, and until this module
existed the server answered `DEFAULT_PERICOPE = "P01"` — every team, every time. Fourteen
passages of Ruth are vendored and no team had ever left the first, because nothing could
move one.

**Derived, never stored.** A team's position is a function of the coverage events it wrote
and the canon's order, and there is no column that could disagree with them. A stored
pointer would become a second opinion the moment a passage is reworked or the canon is
re-vendored, and it would be the opinion the room actually obeys.

**`done` is the mechanism.** A passage is finished when `coverage.floor_met` says so, and
that question is asked there and answered nowhere else here. Nothing in this module counts
beads: a count would let a canon that renamed an element close a passage by arithmetic and
carry a team off work they never did — the one error nobody can notice afterwards, because
what it leaves behind looks exactly like progress.

**The reading is the team's, not a session's.** `ir_sessions.coverage_state` is one
conversation's tracker and every session opens at `initial_state`, so a passage worked over
two evenings has no row that knows it is finished. The events are what outlive the
conversations, which is why the resolution reads those and not the trackers.

## What this does not fix, and saying so is the point

**This module was stationary for its first two releases, and the reason has moved twice.**
`classify_coverage._parse` first read `engaged` and `surfaced` off the top of the model's
reply while the prompt asks for `decisions[]`, so every well-formed reply was dropped and
no event was ever written — nothing resolved past the first passage, with this module in
place exactly as without it. That was ENG-569. Its replacement then bucketed the array into
two lists while the scale had grown to three, so `partially_engaged` alone was discarded:
the narrower failure, and the one that mattered most, because the floor had been lowered to
accept exactly that status. That was ENG-615. Both are fixed, and both lived in that file
rather than in this one.

**A passage that never closes is a wall, and no one is told.** Classification runs on an
LLM off the voice path and fails silently: the tracker is left untouched and the turn moves
on. More turns give more chances, which handles a transient failure and does nothing for an
element that is systematically hard to classify — Ruth 1's five preservation rules being the
natural candidates, since a team engages them by *noticing a silence*. Then the passage never
closes, the team never advances, and nothing raises a hand. There is deliberately no
facilitator override: unsticking belongs to the team, through the app. What is owed here is
that the condition be **detectable**, and it is — the team holds its passage, ages into
`stalled` on the work queue, and `GET /facilitator/teams/{id}/coverage` names the exact beads
still below the floor. Turning that into someone being *told* is ENG-482 (CS-06).
"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.internalization_room import PericopePosition, PericopeStanding
from app.services.internalization_room.canon.parse_map import ROOM_BOOK, load_book
from app.services.internalization_room.coverage import floor_met
from app.services.internalization_room.coverage_events import furthest_by_passage

#: How far a team took every bead of every passage it has touched, keyed by passage. A passage
#: the team never opened is absent rather than present and empty, and `floor_met` is handed the
#: empty reading for it — which it refuses, as it refuses anything unknown.
Reached = dict[str, dict[str, str]]


def resolve(reached: Reached, *, book: str = ROOM_BOOK) -> str | None:
    """The team's next unfinished passage, in the book's order, or `None` at the end of it.

    Canonical order and not "the furthest passage touched": a team that somehow reached P03
    with P02 still open is standing on P02. Nothing in the product lets them skip, but the
    data can hold it — a session may be opened naming a passage — and the answer belongs to
    the book rather than to the order things happened in.

    `None` is the end of the book and is a defined state, not an absence. Every caller has a
    behaviour for it and none of them wraps around to the first passage.
    """
    for meaning_map in load_book(book):
        if not floor_met(reached.get(meaning_map.pericope_num, {}), meaning_map.pericope_num):
            return meaning_map.pericope_num
    return None


def standing(reached: Reached, *, book: str = ROOM_BOOK) -> list[PericopeStanding]:
    """All fourteen with their position already resolved — closed, current, or future.

    Resolved here rather than left to be derived from the active passage, because a screen
    working it out from `active_passage` and a state would be a second place deciding where a
    team stands, and the two would disagree on exactly the cases that matter.

    `closed` and `current` are different facts and are not collapsed: `closed` is the
    passage's floor being met, `current` is where the team is. A team on P02 with P03 already
    finished has both, and there is still exactly one `current`.
    """
    here = resolve(reached, book=book)
    return [
        PericopeStanding(
            pericope=meaning_map.pericope_num,
            reference=meaning_map.reference,
            title=meaning_map.title,
            position=_position(meaning_map.pericope_num, reached, here),
        )
        for meaning_map in load_book(book)
    ]


def _position(pericope: str, reached: Reached, here: str | None) -> PericopePosition:
    if pericope == here:
        return PericopePosition.CURRENT
    if floor_met(reached.get(pericope, {}), pericope):
        return PericopePosition.CLOSED
    return PericopePosition.FUTURE


async def active_passage(
    db: AsyncSession, *, project_id: str | None, book: str = ROOM_BOOK
) -> str | None:
    """Where one team stands. A tablet that never said whose it is stands at the beginning.

    `project_id` is nullable because the room's app does not send its device credential yet
    (ENG-454), so today that is the common case in the field rather than the exception. Work
    with no project belongs to nobody rather than to everybody, so there is no history to read
    and the honest answer is the one a team that has not started gets.
    """
    if project_id is None:
        return resolve({}, book=book)
    resolved = await active_passages(db, project_ids=[project_id], book=book)
    return resolved[project_id]


async def active_passages(
    db: AsyncSession, *, project_ids: Sequence[str], book: str = ROOM_BOOK
) -> dict[str, str | None]:
    """The whole roll resolved in one statement, because the roll is a screen.

    The work queue opens first and opens every time, and a facilitator with fourteen teams
    would otherwise pay fourteen round trips for a position that is derived rather than
    stored. Deriving it is the cost of that screen, so it is paid once.
    """
    reached = await furthest_by_passage(db, project_ids=project_ids)
    return {
        project_id: resolve(reached.get(project_id, {}), book=book) for project_id in project_ids
    }


async def team_standing(
    db: AsyncSession, project_id: str, *, book: str = ROOM_BOOK
) -> list[PericopeStanding]:
    """The fourteen as this team stands on them."""
    reached = await furthest_by_passage(db, project_ids=[project_id])
    return standing(reached.get(project_id, {}), book=book)
