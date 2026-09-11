"""The aggregate reads, scoped by the same value the list is.

The issue's negative-test line names aggregate counts beside direct-id access and paging,
and the reason they belong together is that a count is the cheapest leak in the module: a
number does not look like data, so a query written for a badge is the one nobody thinks to
scope. A caller who is told *Asia: 14* has learned fourteen facts about a region they
cannot open.

Both functions here build on ``visible_projects`` rather than on ``select(func.count())``
of their own, so the predicate sits underneath the aggregation instead of beside it. The
per-region breakdown **names only regions inside the scope** — returning every key with a
zero beside the ones out of reach would answer *there is nothing in Africa* to somebody who
may not know either way, which is the existence answer arriving through the back door.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.shema import ShemaProject
from app.services.shema._scope import RegionScope, within_scope


async def count_projects(db: AsyncSession, scope: RegionScope) -> int:
    """How many projects the caller reaches."""
    stmt = select(func.count()).select_from(ShemaProject).where(within_scope(scope))
    return int((await db.execute(stmt)).scalar_one())


async def count_projects_by_region(db: AsyncSession, scope: RegionScope) -> dict[str, int]:
    """The per-region breakdown, keyed by region key, over the caller's reach only.

    A region inside the scope with no projects is **absent** rather than zero: the caller
    learns nothing from the difference, and a dict built from the rows that exist is one
    fewer place to decide which keys to enumerate.
    """
    stmt = (
        select(ShemaProject.region_key, func.count())
        .where(within_scope(scope))
        .group_by(ShemaProject.region_key)
    )
    return {key.value: int(total) for key, total in (await db.execute(stmt)).all()}
