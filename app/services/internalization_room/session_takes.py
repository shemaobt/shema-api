from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRSession
from app.models.internalization_room import MotherTongueTake, MotherTongueTakesResponse
from app.services.internalization_room.takes import current_parts, takes_of


async def mother_tongue_takes_of(db: AsyncSession, session: IRSession) -> MotherTongueTakesResponse:
    """The recordings of the session in the mother tongue, one per part, in reading order."""
    parts = current_parts(await takes_of(db, session.id))
    return MotherTongueTakesResponse(
        session_id=session.id,
        takes=[
            MotherTongueTake(take_id=take.id, part=position)
            for position, take in enumerate(parts, start=1)
        ],
    )
