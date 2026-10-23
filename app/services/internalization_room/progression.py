"""Where a team stands in the served books, resolved from its own history.

The team walks the book on its own, in canonical order, without a facilitator convening
anything (D-03). Choosing the passage is therefore the server's, and until this module
existed the server answered `DEFAULT_PERICOPE = "P01"` — every team, every time. Fourteen
passages of Ruth are vendored and no team had ever left the first, because nothing could
move one.

**Derived, and what it is derived from moved.** A team's position is still a function of the
book's order and of what the team did, and there is still no pointer anybody writes: nothing
stores "this team is on P02". What it reads is no longer only the coverage events — it is the
sessions that are done and the rehearsals kept in them, and both of those are records of things
that happened rather than a computation that can be re-run to another answer.

**The team's own recording is the mechanism.** A passage is closed when the team has a
session on it that both reached the end of the conversation — `sessions.session_is_done`,
which is the session's `done` status, or `needs_person` with its end stamped, the row ADR
0044 leaves where the old code wrote a halt over `done` — and holds the rehearsal they
recorded there. Nothing here reads the coverage floor on its own, and nothing here counts
beads.

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
conversation's tracker, and what outlives the conversations is which of them are done. A passage
worked over two evenings closes on the evening the team finished it, whichever session that
was; one worked over two evenings and never finished stays open.

**A team stands in one book, its Current book** (ADR 0094). It is the book of the team's
latest live session, a Panorama included, in the order the Desk reads a team's sessions, while
that book still has a passage left; otherwise it is the first of Ruth, Esther and Jonah that
has one. Only the Current book has a current passage, and every reader of where a team stands
reads that book. A team is complete only when every served book is closed. Passage ids are
qualified by book (E01, J01, P01), so the closed fact needs no key of its own.

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

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRSession, IRSessionStatus, IRTake, IRTakeKind
from app.models.internalization_room import (
    BookStanding,
    PassageRelease,
    PericopePosition,
    PericopeStanding,
)
from app.services.internalization_room.canon.book_material import unwalkable
from app.services.internalization_room.canon.parse_map import (
    ROOM_BOOK,
    load_book,
    served_books,
    served_maps,
)
from app.services.internalization_room.coverage import PANORAMA_PREFIX
from app.services.internalization_room.entered import latest_entered_first
from app.services.internalization_room.live import live

#: The passages a team has a finished session on. A passage they never opened, and one they
#: worked without finishing, are both simply absent — there is no third answer to give.
Finished = set[str]


@dataclass(frozen=True)
class TeamWhereabouts:
    """Where one team stands: its Current book, its passage there, what it closed, and which
    served books it closed every passage of."""

    book: str
    passage: str | None
    finished: Finished
    closed_books: frozenset[str]

    @property
    def complete(self) -> bool:
        return self.closed_books >= set(served_books())


def resolve(finished: Collection[str], *, book: str) -> str | None:
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


def standing(
    finished: Collection[str],
    *,
    book: str,
    here: str | None,
    releases: Mapping[str, PassageRelease],
    approved: Collection[str],
    findings: Mapping[str, int],
) -> list[PericopeStanding]:
    """Every passage of one served book with its position already resolved — closed, current,
    or future.

    Resolved here rather than left to be derived from the active passage, because a screen
    working it out from `active_passage` and a state would be a second place deciding where a
    team stands, and the two would disagree on exactly the cases that matter.

    `here` is the team's passage in its Current book, so a book the team is not in has no
    `current`: a team is in one place, and there is still exactly one `current` across them.

    `closed` and `current` are different facts and are not collapsed: `closed` is a session
    the team finished on the passage, `current` is where the team is. A team on P02 with P03
    already finished has both.

    Closed reads the same fact the resolution reads, and it has to: a passage the resolution
    still offers and this panel calls closed is one screen telling a facilitator the team is
    past work the room is about to hand them again.

    Approved is a different fact again: a passage whose draft stands under its latest live
    release (ADR 0081), so a re-opened draft is not approved while its release stays listed. A
    finished session without one approves nothing, so `closed` and `approved` are both served
    and never derived from each other.
    """
    return [
        PericopeStanding(
            pericope=meaning_map.pericope_num,
            reference=meaning_map.reference,
            title=meaning_map.title,
            position=_position(meaning_map.pericope_num, finished, here),
            release=releases.get(meaning_map.pericope_num),
            open_findings=findings.get(meaning_map.pericope_num, 0),
            approved=meaning_map.pericope_num in approved,
        )
        for meaning_map in load_book(book)
    ]


def book_standings(
    whereabouts: TeamWhereabouts, *, approved: Collection[str]
) -> list[BookStanding]:
    """Each served book's count, in the order GET /books serves them: «N de 14», «N de 18»,
    «N de 5». Complete means closed, the fact the resolution reads, never approved."""
    return [
        BookStanding(
            book=book,
            passage_total=len(load_book(book)),
            approved_total=sum(
                1 for meaning_map in load_book(book) if meaning_map.pericope_num in approved
            ),
            complete=book in whereabouts.closed_books,
        )
        for book in served_books()
    ]


def _position(pericope: str, finished: Collection[str], here: str | None) -> PericopePosition:
    if pericope == here:
        return PericopePosition.CURRENT
    if pericope in finished:
        return PericopePosition.CLOSED
    return PericopePosition.FUTURE


async def active_passage(
    db: AsyncSession, *, project_id: str | None, book: str | None = None
) -> str | None:
    """Where one team stands, in `book` or, when none is named, in its Current book.

    `project_id` is nullable because the runner's doors open sessions that belong to no team.
    Work with no team belongs to nobody rather than to everybody, so there is no history to
    read and the honest answer is the one a team that has not started gets.
    """
    if project_id is None:
        return resolve(set(), book=book or ROOM_BOOK)
    if book is None:
        return (await where_teams_stand(db, project_ids=[project_id]))[project_id].passage
    finished = await finished_passages(db, project_ids=[project_id])
    return resolve(finished.get(project_id, set()), book=book)


async def where_teams_stand(
    db: AsyncSession, *, project_ids: Sequence[str]
) -> dict[str, TeamWhereabouts]:
    """The whole roll resolved in two statements, because the roll is a screen.

    The work queue opens first and opens every time, and a facilitator with fourteen teams
    would otherwise pay fourteen round trips for a position that is derived rather than
    stored. Deriving it is the cost of that screen, so it is paid once: what each team closed,
    and the books of its live sessions.
    """
    finished = await finished_passages(db, project_ids=project_ids)
    latest = await _latest_books(db, project_ids=project_ids)
    whereabouts = {}
    for project_id in project_ids:
        closed = finished.get(project_id, set())
        closed_books = frozenset(
            book for book in served_books() if resolve(closed, book=book) is None
        )
        book = _current_book(closed_books, latest.get(project_id))
        whereabouts[project_id] = TeamWhereabouts(
            book=book,
            passage=resolve(closed, book=book),
            finished=closed,
            closed_books=closed_books,
        )
    return whereabouts


def _current_book(closed_books: frozenset[str], latest: str | None) -> str:
    if latest is not None and latest not in closed_books:
        return latest
    walking_order = [ROOM_BOOK, *(book for book in served_books() if book != ROOM_BOOK)]
    for book in walking_order:
        if book not in closed_books:
            return book
    return latest or ROOM_BOOK


async def _latest_books(db: AsyncSession, *, project_ids: Sequence[str]) -> dict[str, str]:
    """The book of each team's latest live session, read in the Desk's order.

    A session whose pericope no served book holds is passed over for the next one: the book is
    looked up, never loaded, so a passage the canon no longer serves cannot raise on the queue.
    The ids are passed in hand, for the reason `finished_passages` gives.
    """
    if not project_ids:
        return {}
    books = {meaning_map.pericope_num: meaning_map.book for meaning_map in served_maps()}
    books |= {PANORAMA_PREFIX + book: book for book in served_books()}
    result = await db.execute(
        select(IRSession.project_id, IRSession.pericope)
        .where(IRSession.project_id.in_(project_ids), live())
        .order_by(IRSession.project_id, *latest_entered_first())
    )
    latest: dict[str, str] = {}
    for project_id, pericope in result.all():
        if project_id not in latest and pericope in books:
            latest[project_id] = books[pericope]
    return latest


async def finished_passages(db: AsyncSession, *, project_ids: Sequence[str]) -> dict[str, Finished]:
    """Which passages each of these teams has finished a session on. One statement.

    Two facts and both are required, because they are different facts. A ``done`` status is
    ``session_is_done`` having become true — the coverage floor, written once in
    ``apply_coverage`` — and that gate is what the room reads to let a team
    *into* the rehearsal. It is not what finishes a passage: a team can reach it and stop, and
    the ledger informs, it never ends the conversation (`DOCTRINE.md` §4). What ends it is the
    rehearsal itself arriving — a kept ``ensaio`` take on that same session. "O fecho ('gravem
    o ensaio') é decisão do Guia", Marcia, answer 8.

    **The status decides "done"**: nothing overwrites a ``done`` session. A halt on a closed
    passage is refused (`mark_needs_person`, ADR 0044) and a landing turn never moves a
    session out of ``done``, so a team that finished a passage keeps it finished. The one
    exception is a row the old code wrote ``needs_person`` over ``done``, which ADR 0044
    leaves alone with its ``ended_at`` set until the next lift restores ``done``: it still
    counts, or the passage would reopen for a team that never returns.

    A retro take is a stretch told back to the room and is not the rehearsal, so the kind is
    part of the question.

    The ids are passed in hand and never as a subquery, for the reason `furthest_by_passage`
    records at length: the planner reaches the index with the ids and sequentially scans
    without them, so the cost becomes the size of the installation rather than the size of
    the answer. An empty roll is answered without asking the database anything.

    A team with no finished passage is absent rather than present and empty, which is what
    the caller reads as "nothing closed yet".

    An archived session finishes nothing: a Zerar'd closed passage is the team's again.
    """
    if not project_ids:
        return {}
    result = await db.execute(
        select(IRSession.project_id, IRSession.pericope)
        .join(IRTake, IRTake.session_id == IRSession.id)
        .where(
            IRSession.project_id.in_(project_ids),
            or_(
                IRSession.status == IRSessionStatus.DONE,
                and_(
                    IRSession.status == IRSessionStatus.NEEDS_PERSON,
                    IRSession.ended_at.is_not(None),
                ),
            ),
            live(),
            IRTake.kind == IRTakeKind.ENSAIO,
        )
        .distinct()
    )
    closed: dict[str, Finished] = {}
    for project_id, pericope in result.all():
        closed.setdefault(project_id, set()).add(pericope)
    return closed
