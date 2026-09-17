"""The aggregate reads, scoped by the same value the list is.

The issue's negative-test line names aggregate counts beside direct-id access and paging,
and the reason they belong together is that a count is the cheapest leak in the module: a
number does not look like data, so a query written for a badge is the one nobody thinks to
scope. A caller who is told *Asia: 14* has learned fourteen facts about a region they
cannot open.

**Both functions here build a** ``select(func.count())`` **of their own and compose**
``within_scope`` **into it by hand**, which makes this the one file in the module that does
not start from ``visible_projects`` — and it is the aggregation that forces it. A global
scope's predicate is a literal ``true()`` naming no column, so
``visible_projects(scope).with_only_columns(func.count())`` re-derives an empty ``FROM`` and
compiles to ``SELECT count(*) WHERE true``: a global caller answered *1* whatever the table
holds. Wrapping the entity select in a subquery is correct and reads a derived table of
seventy-odd columns to produce a number. So the predicate sits beside the aggregation here
rather than underneath it, and what keeps a later aggregate from being written without it is
not the shape of the statement but the glob in ``tests/test_shema/test_scope.py`` — a file in
this package that names ``ShemaProject`` and neither scope helper fails the build.

The per-region breakdown **names only regions inside the scope** — returning every key with a
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
