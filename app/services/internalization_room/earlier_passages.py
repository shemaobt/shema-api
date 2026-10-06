"""This team's status on every earlier passage of the book, read when a session is created.

Her open reads it before the session exists (`app/api/session/route.ts`), so the voice's very
first words already know which earlier passages the team approved, started or never worked,
and the session keeps that stamp for its whole life: a passage approved later does not
rewrite it. **Approved** is a live release of the passage; **started** is a live session of
it the team entered, in any language (`entered`); **not worked** is neither.

The first passage of a book has no earlier passage, and a Panorama is the book's and not one
of its passages, so neither carries a stamp. Neither does a caller with no team: there is
nothing to read, and "not worked" for every passage would be a claim nobody made.

Two statements for the whole book, never one per passage: the releases and the entered
sessions, each over the earlier passages at once. Live rows only, so a Zerar takes a
passage's release and sessions out of the reading together (ADR 0047).
"""

from __future__ import annotations

from itertools import takewhile

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.room_enums import EarlierPassageStatus
from app.db.models.internalization_room import IRRelease, IRSession
from app.services.internalization_room.canon.parse_map import load_book, load_map
from app.services.internalization_room.coverage import is_panorama
from app.services.internalization_room.entered import entered
from app.services.internalization_room.live import live


async def earlier_passages(
    db: AsyncSession, *, project_id: str | None, pericope: str
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


__all__ = ["earlier_passages"]
