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

The order is ``language_name``, which is the collection's default order on the screen and
the one ``ix_shema_projects_language_name`` serves. A window over an unordered select is a
window over an arbitrary page, which would make a paging test pass for the wrong reason.
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
    """Every project inside ``scope``, ordered by language name.

    ``scope`` is positional and has no default. A keyword with a permissive default is how
    a scope stops being applied: the call that omits it still compiles, still passes review
    and returns the whole table. There is no unscoped spelling of this call.
    """
    stmt = visible_projects(scope).order_by(ShemaProject.language_name, ShemaProject.id)
    if offset is not None:
        stmt = stmt.offset(offset)
    if limit is not None:
        stmt = stmt.limit(limit)
    return list((await db.execute(stmt)).scalars().all())
