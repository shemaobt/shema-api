"""``DELETE /api/shema/projects/{id}/members/{userId}`` — the Admin takes an account off a team.

**It marks, it never deletes.** A request the member sent is still the project's after they leave
— the reason OBT-520 stamps the project on a request rather than deriving it — so the row that says
they were on the team stays, with ``removed_at`` and ``removed_by`` written on it. That is the
opposite of the intercessor network's erasure (``remove_intercessor``), and deliberately: there the
row *is* a person's contact held on consent; here it is the record of a stay.

Leaving closes what the membership opened, on the next request and with no cleanup step: the
roster, ``/me/projects`` and the session's ``equipe`` all read live rows only.

An account with no live row on the project is a 404 — there is nothing to remove, and a second
``DELETE`` of the same member answers it too.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.db.models.auth import User
from app.db.models.shema import ShemaProject
from app.services.shema._roster import live_membership
from app.services.shema._scope import RosterReach, refuse_out_of_scope, roster_projects

logger = logging.getLogger(__name__)


async def remove_project_member(
    db: AsyncSession, reach: RosterReach, project_id: str, member_id: str, *, actor: User
) -> None:
    """Mark ``member_id``'s live membership of ``project_id`` as ended, now, by ``actor``."""
    reachable = roster_projects(reach, actor.id).where(ShemaProject.id == project_id)
    if (await db.execute(reachable)).scalar_one_or_none() is None:
        raise refuse_out_of_scope(
            reach.scope, user=actor, operation="remove_project_member", project_id=project_id
        )

    member = await live_membership(db, project_id, member_id)
    if member is None:
        raise NotFoundError("This account is not a member of this project.")

    member.removed_at = datetime.now(UTC)
    member.removed_by = actor.id
    await db.commit()

    logger.info(
        "shema project member removed",
        extra={
            "shema_operation": "remove_project_member",
            "shema_user_id": actor.id,
            "shema_project_id": project_id,
            "shema_member_id": member_id,
        },
    )
