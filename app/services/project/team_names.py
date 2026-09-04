"""The names of teams already named by id, for a listing that crosses teams.

Every other facilitator listing is about one team, which the caller asked for by id and can
name themselves. The room's queue is the exception: it is read to decide *which* team to walk
to, and a row that names only an id is a row nobody can act on.

One statement for the whole page rather than a lookup per row — the queue is short today and
a query per card is a shape this codebase has had to take back out once already.
"""

from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.project import Project


async def team_names(db: AsyncSession, ids: Iterable[str]) -> dict[str, str]:
    """Team id to team name, for the ids that exist. Asking for none asks nothing."""
    wanted = set(ids)
    if not wanted:
        return {}
    rows = await db.execute(select(Project.id, Project.name).where(Project.id.in_(sorted(wanted))))
    return dict(rows.tuples().all())
