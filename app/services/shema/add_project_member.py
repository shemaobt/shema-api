"""``POST /api/shema/projects/{id}/members`` — the Admin puts an account on a project's team.

**Only the Admin writes a roster** (OBT-522; the regional coordination does not, *"por enquanto
não"* — Karina, 25/set). The route is guarded by ``AdminUser``; what this function adds is the
reach that guard implies — every project, through ``RosterReach`` — and the refusals a write owes
before anything is stored:

* a project the Admin cannot find is the same 404 every other miss in the module is;
* an account that does not exist is ``UnknownReferenceError`` (422), checked rather than left to
  the foreign key, whose failure inside a flush would reach the caller as a 500 for their own bad
  id — ``save_region_team``'s reason;
* an account already live on the project is a ``ConflictError`` (409), with a sentence a screen can
  show. The partial unique index stays underneath as the guarantee, for the race and for any caller
  that does not come through here — ``create_fund``'s shape.

Somebody who left and comes back gets a **new** row: the old one keeps its ``removed_at``, and the
history holds both stays.
"""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, UnknownReferenceError
from app.db.models.auth import User
from app.db.models.shema import ShemaProject
from app.db.models.shema_project_member import MEMBER_ROLE, ShemaProjectMember
from app.models.shema_project_member import ProjectMember
from app.services.shema._roster import live_membership, project_member
from app.services.shema._scope import RosterReach, refuse_out_of_scope, roster_projects

logger = logging.getLogger(__name__)


async def add_project_member(
    db: AsyncSession, reach: RosterReach, project_id: str, *, member_id: str, actor: User
) -> ProjectMember:
    """Make ``member_id`` a live member of ``project_id``, and answer the roster's shape of it."""
    reachable = roster_projects(reach, actor.id).where(ShemaProject.id == project_id)
    if (await db.execute(reachable)).scalar_one_or_none() is None:
        raise refuse_out_of_scope(
            reach.scope, user=actor, operation="add_project_member", project_id=project_id
        )

    account = await db.get(User, member_id)
    if account is None:
        raise UnknownReferenceError(f"No user with id '{member_id}'")

    if await live_membership(db, project_id, member_id) is not None:
        raise ConflictError("This account is already a member of this project.")

    member = ShemaProjectMember(
        project_id=project_id, user_id=member_id, role=MEMBER_ROLE, added_by=actor.id
    )
    db.add(member)
    await db.commit()
    await db.refresh(member)

    logger.info(
        "shema project member added",
        extra={
            "shema_operation": "add_project_member",
            "shema_user_id": actor.id,
            "shema_project_id": project_id,
            "shema_member_id": member_id,
        },
    )
    return project_member(member, account)
