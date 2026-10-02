"""The scoped collection read, and the shape every later list query copies.

FE-44 §9.1 freezes ``GET /api/shema/projects`` as *the whole collection the caller's role
and region allow* — no pagination, no filter parameters, no facet counts, because sixteen
facet groups and four presets are computed client-side in one pass under a rule whose whole
value is that one function produces both the sidebar's numbers and the list. So the
endpoint BE-05 builds takes no ``limit``.

**This function takes one anyway, and that is the point of it being here.** The issue asks
that a caller not be able to page past their scope, and the way to be sure is to have the
paging and the scope in one statement with the predicate underneath the window rather than
beside it. ``limit``/``offset`` exist so the property can be exercised rather than
asserted, and so the day §9.1's own note fires — past roughly 2,000 projects, when the
server takes the filter *and* the counts together — the window is already inside the scope
instead of being added on top of it by whoever is holding the pen that week.

The order is the **id**, an opaque UUID since OBT-552, and that is a privacy decision
(OBT-563, Daniel, 2/out/2026). It used to be ``language_name``, the real name, and every caller
that hands the rows on in their order — the Projetos screen through its stable sorts, the
export through its rows — then placed a sensitive project by the name it withholds. An order
that says nothing is the one this read can give to every reader; whoever shows the rows orders
them by the name the reader reads, which only the shape built for that reader knows. A window
still needs *an* order, or a paging test passes for the wrong reason, and the id is total.
``ix_shema_projects_language_name`` no longer serves this read.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.shema import ShemaProject
from app.services.shema._scope import RegionScope, visible_projects


async def list_projects(
    db: AsyncSession,
    scope: RegionScope,
    *,
    limit: int | None = None,
    offset: int | None = None,
) -> list[ShemaProject]:
    """Every project inside ``scope``, ordered by id.

    ``scope`` is positional and has no default. A keyword with a permissive default is how
    a scope stops being applied: the call that omits it still compiles, still passes review
    and returns the whole table. There is no unscoped spelling of this call.
    """
    stmt = visible_projects(scope).order_by(ShemaProject.id)
    if offset is not None:
        stmt = stmt.offset(offset)
    if limit is not None:
        stmt = stmt.limit(limit)
    return list((await db.execute(stmt)).scalars().all())
