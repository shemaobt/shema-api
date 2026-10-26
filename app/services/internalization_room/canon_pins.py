"""The canon pins sessions hold, which a prune of the kept canons must keep (ADRs 0088, 0099).

Every team's, not the reader's: a prune told only some teams' pins removes the others' canon.
An archived session's too: the Desk still reads it by id.
"""

from __future__ import annotations

from typing import cast

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRSession


async def held_canon_pins(db: AsyncSession) -> list[str]:
    held = cast(
        Select[tuple[str]],
        select(IRSession.canon_pin)
        .where(IRSession.canon_pin.is_not(None))
        .distinct()
        .order_by(IRSession.canon_pin),
    )
    return list(await db.scalars(held))
