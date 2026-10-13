"""This team's status on every earlier passage of the book, read within her budgets.

Her open reads it before the session exists (`app/api/session/route.ts`), so the voice's very
first words already know which earlier passages the team approved, started or never worked; a
session that has none reads it before its next turn (`app/api/turn/route.ts`). Either way the
session keeps the stamp, and her turn route reads it again off the voice's path once it is five
minutes old, so a passage approved later reaches the voice on a later turn, never mid-step.
**Approved** is a live release of the passage; **started** is a live session of it the team
entered, in any language (`entered`); **not worked** is neither.

The first passage of a book has no earlier passage, and a Panorama is the book's and not one
of its passages, so neither carries a stamp. Neither does a caller with no team: there is no
team whose work could be read.

The read has her budgets: 3 s at the open, as her session route gives it, and 1.5 s before a
turn, as her turn route does, and it runs on a session of its own, so a statement cut by the
budget never touches the caller's transaction. A read that misses its budget never leaves the
fact out: every passage it could not read keeps its status from the stamp before, or is
stamped not worked yet when there is none, and is named in the stamp's `unread`, as her reader
does (`src/turn/earlierPassagesRead.ts`, app 18fa7c4). It is the safe reading, the one that
never claims a memory the team does not have: the voice tells such a passage as the story's,
«a história conta que…», and never recalls it as the team's.

`unread` sits beside the statuses as one comma-separated string, so the stamp stays a map of
strings for everything that reads it. Those readers look only at the passages, so a stamp
written before `unread` existed reads as one with nothing unread.

`at` sits beside them too: when the stamp was read, in UTC, as an ISO 8601 string. After a
turn, a stamp is read again off the voice's path once `at` is five minutes old, and a stamp
with no `at` is read again on the next turn. That absence is what re-reads every stamp written
before `at` existed, and every stamp a timeout left: a timeout writes no `at`, because the
passages it names unread are due again at once, as her route reads again a stamp with an
unread passage.

Two statements for the whole book, never one per passage: the releases and the entered
sessions, each over the earlier passages at once. Live rows only, so a Zerar takes a
passage's release and sessions out of the reading together (ADR 0047).
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from itertools import takewhile

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.room_enums import EarlierPassageStatus
from app.db.models.internalization_room import IRRelease, IRSession
from app.services.internalization_room.canon.parse_map import load_book, load_map
from app.services.internalization_room.coverage import is_panorama
from app.services.internalization_room.entered import entered
from app.services.internalization_room.live import live

logger = logging.getLogger(__name__)

OPEN_READ_BOUND_S = 3.0
TURN_READ_BOUND_S = 1.5
READ_AGAIN_AFTER = timedelta(minutes=5)


async def earlier_passages(
    db: AsyncSession,
    *,
    project_id: str | None,
    pericope: str,
    before_a_turn: bool = False,
    prior: Mapping[str, str] | None = None,
) -> dict[str, str] | None:
    if project_id is None or is_panorama(pericope):
        return None
    earlier = [
        meaning_map.pericope_num
        for meaning_map in takewhile(
            lambda meaning_map: meaning_map.pericope_num != pericope,
            load_book(load_map(pericope).book),
        )
    ]
    if not earlier:
        return None
    bound_s = TURN_READ_BOUND_S if before_a_turn else OPEN_READ_BOUND_S
    at = datetime.now(UTC).isoformat()
    try:
        async with asyncio.timeout(bound_s), AsyncSession(db.bind) as reader:
            return {**await read_statuses(reader, project_id=project_id, earlier=earlier), "at": at}
    except TimeoutError:
        unread = ", ".join(earlier)
        logger.warning(
            "[earlier] team %s, %s: %s not read within %s s — kept from the stamp before, "
            "or read as not worked yet",
            project_id,
            pericope,
            unread,
            bound_s,
        )
        kept = prior or {}
        return {
            **{passage: kept.get(passage, EarlierPassageStatus.NOT_WORKED) for passage in earlier},
            "unread": unread,
        }


def earlier_passages_due(stamp: Mapping[str, str] | None) -> bool:
    if stamp is None:
        return False
    at = stamp.get("at")
    return at is None or datetime.now(UTC) - datetime.fromisoformat(at) >= READ_AGAIN_AFTER


async def read_statuses(db: AsyncSession, *, project_id: str, earlier: list[str]) -> dict[str, str]:
    approved = set(
        await db.scalars(
            select(IRRelease.pericope).where(
                IRRelease.project_id == project_id,
                IRRelease.pericope.in_(earlier),
                live(IRRelease),
            )
        )
    )
    started = set(
        await db.scalars(
            select(IRSession.pericope).where(
                IRSession.project_id == project_id,
                IRSession.pericope.in_(earlier),
                live(),
                entered(),
            )
        )
    )
    return {passage: _status(passage, approved, started) for passage in earlier}


def _status(passage: str, approved: set[str], started: set[str]) -> EarlierPassageStatus:
    if passage in approved:
        return EarlierPassageStatus.APPROVED
    if passage in started:
        return EarlierPassageStatus.STARTED
    return EarlierPassageStatus.NOT_WORKED


__all__ = ["earlier_passages", "earlier_passages_due"]
