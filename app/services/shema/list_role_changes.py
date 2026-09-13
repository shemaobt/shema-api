"""The org chart's audit trail, newest first, inside the caller's region scope.

**This is the one surface that shows the name of somebody who left a seat.** The chart itself
answers *who holds this office now*, and clearing a seat removes that person from it and from
all four consumers that read it by reference; what survives is this trail, which is the record
of an act rather than a listing of a person. That distinction is the issue's *historical
attribution handled deliberately*: the contribution is kept and attributed to the name its
author used at the time, and it is not a directory entry — nothing here is a way to reach
anybody, and the trail carries no contact, no account and no country.

**Region-scoped, unlike the chart.** ``list_regions`` answers the organisation's own directory
of offices and every member reads all seven; a trail of who replaced whom in a region is a
narrower fact, so a regional ``coordinator`` reads their regions and a global one reads all.
The scope is applied in the query rather than by the caller, which is ``docs/shema.md`` §6.1's
*every list query takes it as a parameter* — a filter applied per endpoint is a filter the
next endpoint writes slightly differently.

``ix_shema_role_changes_region_changed`` is ``(region_key, changed_at)``, which is this query
exactly: the predicate on the left, the order on the right.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.shema_enums import ShemaRegionKey
from app.db.models.shema_org_chart import ShemaRoleChange
from app.models.shema_org_chart import RoleChange
from app.services.shema._scope import RegionScope
from app.utils.stored_time import as_utc

#: How many entries a single read returns. The screen shows a recent history and the table
#: grows forever; an unbounded read of an append-only trail is a query that gets slower every
#: month and is noticed the month it matters.
DEFAULT_LIMIT = 200


async def list_role_changes(
    db: AsyncSession,
    scope: RegionScope,
    *,
    limit: int = DEFAULT_LIMIT,
) -> list[RoleChange]:
    """The most recent changes the caller may see, newest first.

    An empty, non-global scope answers nothing rather than everything — the fail-closed floor
    ``_scope.py`` argues, repeated here because this query does not go through
    ``visible_projects`` and so does not inherit it.
    """
    if not scope.global_ and not scope.regions:
        return []

    stmt = select(ShemaRoleChange)
    if not scope.global_:
        stmt = stmt.where(
            ShemaRoleChange.region_key.in_([ShemaRegionKey(key) for key in sorted(scope.regions)])
        )
    stmt = stmt.order_by(ShemaRoleChange.changed_at.desc(), ShemaRoleChange.id.desc()).limit(limit)

    return [
        RoleChange.model_validate(
            {
                "regionKey": row.region_key.value,
                "role": row.role.value,
                "from": row.from_name,
                "to": row.to_name,
                "changedBy": row.changed_by,
                "changedAt": as_utc(row.changed_at).date(),
            }
        )
        for row in (await db.execute(stmt)).scalars()
    ]
