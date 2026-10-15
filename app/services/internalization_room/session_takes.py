from __future__ import annotations

import asyncio

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRSession
from app.models.internalization_room import MotherTongueTake, MotherTongueTakesResponse
from app.services.internalization_room.takes import current_parts, listen_url, takes_of
from app.utils.stored_time import as_utc


async def mother_tongue_takes_of(db: AsyncSession, session: IRSession) -> MotherTongueTakesResponse:
    """The recordings of the session in the mother tongue, one per part, in reading order."""
    rows: list[MotherTongueTake] = []
    position = 0
    parts = current_parts(await takes_of(db, session.id))
    links = await asyncio.gather(*(listen_url(take) for take in parts))
    for take, link in zip(parts, links, strict=True):
        if take.ordinal is not None:
            position += 1
        rows.append(
            MotherTongueTake(
                take_id=take.id,
                part=None if take.ordinal is None else position,
                size_kb=(take.size_bytes + 512) // 1024,
                fingerprint=take.sha256[:12],
                recorded_at=as_utc(take.created_at).isoformat(),
                play_url=link,
            )
        )
    return MotherTongueTakesResponse(session_id=session.id, takes=rows)
