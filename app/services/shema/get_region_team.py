"""One region's three seats — what the editing screen loads before it saves.

``list_regions`` answers the whole chart for the four consumers that read it by reference;
this answers one region for the one screen that writes it. Same shape, so the editor and the
readers cannot drift, and no second assembly of a ``Region``.

**The region key is not an existence question.** All seven are a public vocabulary the console
already holds and a seat with no row is a real, renderable state, so an unknown key is the
only refusal here and it is a plain validation failure rather than a 404 about a row.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.shema_enums import ShemaRegionKey
from app.models.shema_org_chart import Region
from app.services.shema.list_regions import region_of, seats_of


async def get_region_team(db: AsyncSession, region_key: ShemaRegionKey) -> Region:
    """The region's seats, assigned or not, with the account behind each where there is one."""
    return region_of(region_key, await seats_of(db, region_key))
