"""One region's three seats — what the editing screen loads before it saves.

``list_regions`` answers the whole chart for the four consumers that read it by reference;
this answers one region for the one screen that writes it. The frozen half is the same
assembly (``region_of``), so the editor and the readers cannot drift on a name; what this adds
is ``teamAccounts``, which the collection deliberately has no field for — a user id is an
internal identifier and this is the one surface that hands it out.

**The region key is not an existence question.** All seven are a public vocabulary the console
already holds and a seat with no row is a real, renderable state, so an unknown key is the
only refusal here and it is a plain validation failure rather than a 404 about a row.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.shema_enums import ShemaRegionKey
from app.models.shema_org_chart import RegionWithAccounts
from app.services.shema.list_regions import accounts_of, region_of, seats_of


async def get_region_team(db: AsyncSession, region_key: ShemaRegionKey) -> RegionWithAccounts:
    """The region's seats, assigned or not, with the account behind each where there is one."""
    seats = await seats_of(db, region_key)
    region = region_of(region_key, seats)
    return RegionWithAccounts(
        key=region.key,
        labelKey=region.label_key,
        team=region.team,
        teamAccounts=accounts_of(seats),
    )
