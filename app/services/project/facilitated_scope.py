"""Which teams a facilitator reaches, as a restriction a query can carry.

Written once and shared because it is the same sentence in two places, and the day the two
drift is the day one route shows what the other hides. ``list_facilitator_teams`` restricts
five subqueries with it; the room's inbox restricts a page and a count with it.

``None`` for a platform admin rather than a select of every project id: their scope is "no
restriction at all", and spelling it as a subquery listing the installation would put that
list inside every clause for nothing.
"""

from collections.abc import Sequence

from sqlalchemy import ColumnElement, Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from app.core.enums import ProjectRole
from app.db.models.auth import User
from app.db.models.project import ProjectUserAccess
from app.services.project.list_facilitated_project_ids import list_facilitated_project_ids

#: One sentence for a team that is not yours and for a team that does not exist. A caller
#: who could tell them apart could map an installation by asking about ids, and closing that
#: at one door and leaving it open at another closes nothing.
TEAM_NOT_FOUND = "Team not found"


def facilitated_projects(user: User) -> Select | None:
    """The project ids the caller reaches, or ``None`` when that is every one of them."""
    if user.is_platform_admin:
        return None

    return select(ProjectUserAccess.project_id).where(
        ProjectUserAccess.user_id == user.id,
        ProjectUserAccess.role == ProjectRole.FACILITATOR,
    )


def within(column: InstrumentedAttribute[str | None], scope: Select | None) -> ColumnElement[bool]:
    """Confine one clause to the caller's teams.

    Falls back to "has a project at all" for a platform admin, which is what an unrestricted
    scope means here. A null project belongs to no team either way, and ``IN`` already
    excludes it — the explicit test is what keeps the admin's case honest rather than
    accidental.
    """
    if scope is None:
        return column.is_not(None)

    return column.in_(scope)


async def facilitated_project_ids(db: AsyncSession, user: User) -> list[str] | None:
    """The same scope with the ids in hand, or ``None`` when the caller reaches everything.

    **The second form exists because the first one cannot be planned.** A restriction
    written as ``project_id IN (SELECT …)`` is opaque to the planner: on a seeded Postgres
    of 70,000 questions across 200 teams, asking for one facilitator's fourteen produced a
    hash join over a **sequential scan of the whole table** — 70,000 rows read and 1,439
    buffers touched to answer fifty. The same query with the fourteen ids spelled out is a
    bitmap index scan on ``ix_ir_questions_project_id``: 4,900 rows, 128 buffers, eleven
    times less. An ``EXISTS`` rewrite plans identically to the subquery and does not help.

    So the shape is chosen by where the restriction sits. Inside the grouped subqueries of
    ``list_facilitator_teams`` the select form is what belongs; as the main filter of a
    ``SELECT … ORDER BY … LIMIT``, where the planner has to decide whether an index is worth
    using, the ids have to be visible. The extra read is one index lookup on a table with one
    row per team a person facilitates.

    Sorted so that two calls with the same scope render the same statement.
    """
    if user.is_platform_admin:
        return None

    return sorted(await list_facilitated_project_ids(db, user))


def confined_to(
    column: InstrumentedAttribute[str | None], ids: Sequence[str] | None
) -> ColumnElement[bool]:
    """``within`` for a scope already in hand. ``None`` still means "any team at all"."""
    if ids is None:
        return column.is_not(None)

    return column.in_(ids)
