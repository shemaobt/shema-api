"""The frase each stretch of a session is known by, frozen by its latest version or live."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRRelease, IRSession
from app.services.internalization_room.back_translation import frase_numbers
from app.services.internalization_room.segments import final_segments, told_back


async def stretch_numbers(db: AsyncSession, session: IRSession) -> dict[str, int]:
    """Each stretch standing, by id, with the frase the latest version of this session froze.

    Read out of the stored packet rather than recomputed from the rows, which is the whole point
    of freezing it: every reading renumbers, and a comment filed against frase 3 has to go on
    meaning the stretch it meant. A packet that carries no number at all (the ones minted before
    the number was frozen) answers the live reading instead, and so does a session with no
    version. A stretch with nothing said on it has no number in either.
    """
    stretches = await final_segments(db, session.id)
    latest = await db.scalar(
        select(IRRelease)
        .where(IRRelease.session_id == session.id)
        .order_by(IRRelease.version.desc())
        .limit(1)
    )
    frozen = {
        entry["segment_id"]: entry["frase"]
        for entry in ((latest.packet if latest else {}).get("back_translation") or {}).get(
            "segments", []
        )
        if entry.get("segment_id") and entry.get("frase") is not None
    }
    numbers = frozen or frase_numbers(told_back(stretches))
    return {row.id: numbers[row.id] for row in stretches if row.id in numbers}
