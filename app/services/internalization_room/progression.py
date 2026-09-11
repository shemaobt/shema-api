"""Where a team stands in the book, resolved from its own history.

The team walks the book on its own, in canonical order, without a facilitator convening
anything (D-03). Choosing the passage is therefore the server's, and until this module
existed the server answered `DEFAULT_PERICOPE = "P01"` — every team, every time. Fourteen
passages of Ruth are vendored and no team had ever left the first, because nothing could
move one.

**Derived, and what it is derived from moved.** A team's position is still a function of the
book's order and of what the team did, and there is still no pointer anybody writes: nothing
stores "this team is on P02". What it reads is no longer only the coverage events — it is the
sessions that ended and the rehearsals kept in them, and both of those are records of things
that happened rather than a computation that can be re-run to another answer.

**The team's own recording is the mechanism.** A passage is closed when the team has a
session on it that both reached the end of the conversation — `sessions.session_is_done`,
whose instant is stamped on the row as `ir_sessions.ended_at` — and holds the rehearsal they
recorded there. Nothing here reads the coverage floor on its own, and nothing here counts
beads. Why the stamp and not the status they are written together with is on
`finished_passages`.

**Reaching the rehearsal and finishing the passage are two facts, and this module wants the
second.** `session_is_done` is the first: it is the signal the room reads to let a team into
the recording, so it must go on meaning what it means. A team can reach it and stop — and
until the take is kept, the passage is still theirs.

**The floor closed passages and it should never have.** "O classificador só pinta as contas e
não pode travar a sessão: o registro informa, o fecho ('gravem o ensaio') é decisão do Guia"
— Marcia, answer 8, and `DOCTRINE.md` §4 in the same words. A team that met the floor and
closed the tablet in the middle of the third scene was carried off the passage by a number,
with the parts they never worked counted as worked. The floor stays exactly what it was: the
gate on the invitation to record.

**The reading is the team's, not a session's tracker.** `ir_sessions.coverage_state` is one
conversation's tracker, and what outlives the conversations is which of them ended. A passage
worked over two evenings closes on the evening the team finished it, whichever session that
was; one worked over two evenings and never finished stays open.

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

**A re-vendored canon no longer re-opens a passage, and that is a change of kind.** The old
resolution asked `floor_met` against today's spine every time, so renaming a bead un-closed
the passage and sent the team back into it — the bias that
`test_a_bead_the_canon_does_not_serve_cannot_close_a_passage` pinned. Closing on a recording
cannot work that way: the team really did rehearse the passage they were given, and no edit to
the canon undoes that. So a re-vendor that renames a bead leaves the closed passages closed,
and the beads it added are not offered to a team that has already moved past them. Whether
they should be is a question about re-work, which nothing in the product asks for yet.

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

from collections.abc import Collection, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRSession, IRTake, IRTakeKind
from app.models.internalization_room import PericopePosition, PericopeStanding
from app.services.internalization_room.canon.book_material import unwalkable
from app.services.internalization_room.canon.parse_map import ROOM_BOOK, load_book

#: The passages a team has a finished session on. A passage they never opened, and one they
#: worked without finishing, are both simply absent — there is no third answer to give.
Finished = set[str]


def resolve(finished: Collection[str], *, book: str = ROOM_BOOK) -> str | None:
    """The team's next unfinished passage, in the book's order, or `None` at the end of it.

    Canonical order and not "the furthest passage touched": a team that somehow reached P03
    with P02 still open is standing on P02. Nothing in the product lets them skip, but the
    data can hold it — a session may be opened naming a passage — and the answer belongs to
    the book rather than to the order things happened in.

    `None` is the end of the book and is a defined state, not an absence. Every caller has a
    behaviour for it and none of them wraps around to the first passage.

    A passage the room would refuse is stepped over rather than landed on. Its floor can never
    be met — no session can open on it to write a single event — so it was answered on every
    resolution after the one before it closed, and the team was routed for good into a passage
    that could only reply with a refusal. Stepping over is also what keeps this and the wheel
    describing the same book: what a team can be sent to is exactly what it can be offered.
    """
    for meaning_map in load_book(book):
        if unwalkable(meaning_map):
            continue
        if meaning_map.pericope_num not in finished:
            return meaning_map.pericope_num
    return None


def standing(finished: Collection[str], *, book: str = ROOM_BOOK) -> list[PericopeStanding]:
    """All fourteen with their position already resolved — closed, current, or future.

    Resolved here rather than left to be derived from the active passage, because a screen
    working it out from `active_passage` and a state would be a second place deciding where a
    team stands, and the two would disagree on exactly the cases that matter.

    `closed` and `current` are different facts and are not collapsed: `closed` is a session
    the team finished on the passage, `current` is where the team is. A team on P02 with P03
    already finished has both, and there is still exactly one `current`.

    Closed reads the same fact the resolution reads, and it has to: a passage the resolution
    still offers and this panel calls closed is one screen telling a facilitator the team is
    past work the room is about to hand them again.
    """
    here = resolve(finished, book=book)
    return [
        PericopeStanding(
            pericope=meaning_map.pericope_num,
            reference=meaning_map.reference,
            title=meaning_map.title,
            position=_position(meaning_map.pericope_num, finished, here),
        )
        for meaning_map in load_book(book)
    ]


def _position(pericope: str, finished: Collection[str], here: str | None) -> PericopePosition:
    if pericope == here:
        return PericopePosition.CURRENT
    if pericope in finished:
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
        return resolve(set(), book=book)
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
    finished = await finished_passages(db, project_ids=project_ids)
    return {
        project_id: resolve(finished.get(project_id, set()), book=book)
        for project_id in project_ids
    }


async def finished_passages(db: AsyncSession, *, project_ids: Sequence[str]) -> dict[str, Finished]:
    """Which passages each of these teams has finished a session on. One statement.

    Two facts and both are required, because they are different facts. ``ended_at`` is the
    instant ``session_is_done`` became true — the coverage floor and the comprehension gate,
    stamped once in ``apply_coverage`` — and that gate is what the room reads to let a team
    *into* the rehearsal. It is not what finishes a passage: a team can reach it and stop, and
    the ledger informs, it never ends the conversation (`DOCTRINE.md` §4). What ends it is the
    rehearsal itself arriving — a kept ``ensaio`` take on that same session. "O fecho ('gravem
    o ensaio') é decisão do Guia", Marcia, answer 8.

    **The stamp and not the status**, though the two are written together. ``mark_needs_person``
    overwrites the status with no guard on what it was, and the retell warning it raises only
    ever reaches a session that has already recorded — the back-translation route refuses one
    without a take. Read from the status, a team that finished a passage and then struggled to
    tell a stretch back would have it handed to them again, and a landing turn restores
    ``IN_PROGRESS`` and never ``DONE``, so it would stay handed back. ``ended_at`` is written
    at the same instant and no halt writes over it.

    A retro take is a stretch told back to the room and is not the rehearsal, so the kind is
    part of the question.

    The ids are passed in hand and never as a subquery, for the reason `furthest_by_passage`
    records at length: the planner reaches the index with the ids and sequentially scans
    without them, so the cost becomes the size of the installation rather than the size of
    the answer. An empty roll is answered without asking the database anything.

    A team with no finished passage is absent rather than present and empty, which is what
    the caller reads as "nothing closed yet".
    """
    if not project_ids:
        return {}
    result = await db.execute(
        select(IRSession.project_id, IRSession.pericope)
        .join(IRTake, IRTake.session_id == IRSession.id)
        .where(
            IRSession.project_id.in_(project_ids),
            IRSession.ended_at.is_not(None),
            IRTake.kind == IRTakeKind.ENSAIO,
        )
        .distinct()
    )
    closed: dict[str, Finished] = {}
    for project_id, pericope in result.all():
        closed.setdefault(project_id, set()).add(pericope)
    return closed


async def team_standing(
    db: AsyncSession, project_id: str, *, book: str = ROOM_BOOK
) -> list[PericopeStanding]:
    """The fourteen as this team stands on them."""
    finished = await finished_passages(db, project_ids=[project_id])
    return standing(finished.get(project_id, set()), book=book)
