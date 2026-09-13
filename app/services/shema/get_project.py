"""The record read, addressed by id — and the one place the visibility answer is felt.

A project outside the caller's scope is refused exactly as a project that does not exist
is refused: ``NotFoundError``, the same message, the same 404. ``app/services/shema/_scope.py``
carries the argument; what lands here is its consequence, which is that this function has
**no branch** a reader could later "improve" into a 403. The row simply is not in the
statement, so the two cases arrive at the same line.

The refusal is logged — with the caller, the operation and the caller's own regions, and
without any column of the row being protected. That is the DoD's last line, and it is what
makes an indistinguishable response investigable.

**The branch below fires on any miss**, so a mistyped id reaches the same line an
out-of-region one does. That is the choice above seen from the logging side rather than a
gap in it: this function cannot tell the two apart without the unscoped query the 404 exists
to avoid. What it can do is not claim to, which is why the message classifies the outcome
rather than announcing a refused authorization — see ``refuse_out_of_scope``.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.auth import User
from app.db.models.shema import ShemaProject
from app.services.shema._scope import RegionScope, refuse_out_of_scope, visible_projects


async def get_project(
    db: AsyncSession,
    scope: RegionScope,
    project_id: str,
    *,
    user: User,
    operation: str = "get_project",
) -> ShemaProject:
    """One project inside ``scope``, or ``NotFoundError``.

    ``user`` is here for the log line and for nothing else — the decision was already made
    when ``scope`` was computed, and taking the account again would be a second place to
    get the rule wrong. ``operation`` lets a caller name the surface that asked (the record
    read, an export, a write's pre-check) so one refusal in a log can be told from another.
    """
    stmt = visible_projects(scope).where(ShemaProject.id == project_id)
    project = (await db.execute(stmt)).scalar_one_or_none()
    if project is None:
        raise refuse_out_of_scope(scope, user=user, operation=operation, project_id=project_id)
    return project
