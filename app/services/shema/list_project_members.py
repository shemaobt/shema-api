"""``GET /api/shema/projects/{id}/members`` — who is on a project's team, and since when (OBT-524).

**Three readers**, which is the issue's sentence — *lê quem tem escopo sobre o projeto, e o membro
sobre os próprios projetos* — plus the Admin, who writes every roster and reads what it writes:
``_scope.roster_projects`` is the one statement that says so. Anybody else is refused exactly as a
project that does not exist is, by ``refuse_out_of_scope``: the roster answers *nothing* about a
project the caller does not reach, and the status code is where that answer would otherwise leak
(``docs/shema.md`` §6.1).

**A coordination surface, and it redacts nothing.** A member of a project in a sensitive country is
still named on that project's roster: the readers are the people who work with them. No export
reads this table until BE-14 decides it.

The names come from ``users``, joined here for the one column a roster needs. That is reading an
account, not a grant: ``save_region_team`` does the same to check a seat's account, and
``docs/shema.md`` §2.4's rule is about the grant tables, which this never touches.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.auth import User
from app.db.models.shema import ShemaProject
from app.db.models.shema_project_member import ShemaProjectMember
from app.models.shema_project_member import ProjectMember
from app.services.shema._roster import project_member
from app.services.shema._scope import RosterReach, refuse_out_of_scope, roster_projects


async def list_project_members(
    db: AsyncSession, reach: RosterReach, project_id: str, *, user: User
) -> list[ProjectMember]:
    """The project's live members, in the order they joined.

    Removed rows stay in the table and out of this list: the roster is who is on the team now,
    and the history is the table's, for whoever investigates.
    """
    reachable = roster_projects(reach, user.id).where(ShemaProject.id == project_id)
    if (await db.execute(reachable)).scalar_one_or_none() is None:
        raise refuse_out_of_scope(
            reach.scope, user=user, operation="list_project_members", project_id=project_id
        )

    rows = await db.execute(
        select(ShemaProjectMember, User)
        .join(User, User.id == ShemaProjectMember.user_id)
        .where(
            ShemaProjectMember.project_id == project_id,
            ShemaProjectMember.removed_at.is_(None),
        )
        .order_by(ShemaProjectMember.added_at, ShemaProjectMember.id)
    )
    return [project_member(member, account) for member, account in rows.tuples()]
