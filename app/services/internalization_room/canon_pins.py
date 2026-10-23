"""The canon pins live sessions hold, which a prune of the kept canons must keep (ADR 0088).

Every team's, not the reader's: a prune told only some teams' pins removes the others' canon.
"""

from __future__ import annotations

from typing import cast

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRSession
from app.services.internalization_room.live import live


async def live_canon_pins(db: AsyncSession) -> list[str]:
    held = cast(
        Select[tuple[str]],
        select(IRSession.canon_pin)
        .where(live(), IRSession.canon_pin.is_not(None))
        .distinct()
        .order_by(IRSession.canon_pin),
    )
    return list(await db.scalars(held))
