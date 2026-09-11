"""The whole org chart: seven regions, three seats each, assigned or not.

**Twenty-one seats always, and they are not rows.** ``shema_region_teams`` ships empty on
purpose — FE-44 §5.3 records that the prototype's names were real people hardcoded in a file
and that the honest wave-1 state is twenty-one unassigned roles. So the grid comes from the
two enums and the stored rows are an **overlay**, which means the chart is complete on a
database nobody has written to and no seeding step stands between a fresh install and a
screen that renders. A seat gains a row the first time somebody is put in it.

**Not scoped by region, and that is the chart being a chart.** ``docs/shema.md`` §6.1's scope
answers *which projects does this caller reach*; this is the organisation's own directory of
offices, and its four consumers include the sidebar panel that shows every region at once.
A regional coordinator reads the whole chart and writes only their own region —
``save_region_team.py`` is where the second half is enforced, and it is the half that matters.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.shema_enums import ShemaRegionKey, ShemaRoleKey
from app.db.models.shema_org_chart import ShemaRegionTeam
from app.models.shema_org_chart import Region, RegionTeam, RegionTeamAccounts, label_key_for

#: The seat order of every shape in this module, and the order FE-44's ``RegionTeam`` writes
#: its three fields in. One tuple, so the chart, the save and the audit cannot disagree about
#: which seat is which.
SEAT_ORDER: tuple[ShemaRoleKey, ...] = (
    ShemaRoleKey.COORDINATOR,
    ShemaRoleKey.OBT_LAB,
    ShemaRoleKey.RESOURCE_CIRCLE,
)

#: The attribute each seat carries in ``RegionTeam`` and ``RegionTeamAccounts``. Public
#: because ``save_region_team.py`` reads the same payload seat by seat, and a second mapping
#: between three enum members and three field names is two places for one fact.
FIELD_FOR_SEAT: dict[ShemaRoleKey, str] = {
    ShemaRoleKey.COORDINATOR: "coordinator",
    ShemaRoleKey.OBT_LAB: "obt_lab",
    ShemaRoleKey.RESOURCE_CIRCLE: "resource_circle",
}


async def seats_of(
    db: AsyncSession, region_key: ShemaRegionKey
) -> dict[ShemaRoleKey, ShemaRegionTeam]:
    """The stored rows of one region, keyed by seat. Absent means unassigned."""
    stmt = select(ShemaRegionTeam).where(ShemaRegionTeam.region_key == region_key)
    return {row.role: row for row in (await db.execute(stmt)).scalars()}


def region_of(region_key: ShemaRegionKey, seats: dict[ShemaRoleKey, ShemaRegionTeam]) -> Region:
    """One region's frozen shape, built over whatever rows exist for it."""
    return Region(
        key=region_key.value,
        labelKey=label_key_for(region_key.value),
        team=RegionTeam(
            **{
                FIELD_FOR_SEAT[seat]: (seats[seat].holder_name if seat in seats else "")
                for seat in SEAT_ORDER
            }
        ),
        teamAccounts=RegionTeamAccounts(
            **{
                FIELD_FOR_SEAT[seat]: (seats[seat].holder_user_id if seat in seats else None)
                for seat in SEAT_ORDER
            }
        ),
    )


async def list_regions(db: AsyncSession) -> list[Region]:
    """Every region in ``RegionKey``'s own order, each with its three seats.

    One query for all twenty-one rows rather than seven; the table's whole size is the
    product's whole org chart, so paging it would be arithmetic about a page of nothing.
    """
    rows = (await db.execute(select(ShemaRegionTeam))).scalars()
    by_region: dict[ShemaRegionKey, dict[ShemaRoleKey, ShemaRegionTeam]] = {}
    for row in rows:
        by_region.setdefault(row.region_key, {})[row.role] = row
    return [region_of(key, by_region.get(key, {})) for key in ShemaRegionKey]
