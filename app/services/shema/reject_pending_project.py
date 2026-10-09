"""``POST /api/shema/projects/{id}/reject`` — the Admin discards a project an approval filed.

OBT-547. The project is marked, never deleted: ``discarded_at``, ``discarded_by`` and the reason,
which is required. It stays pending, so it stays out of every read through the scope, and it
frees its link — a later approved request of the same team files a new one for the Admin to look
at again.

**The request is left exactly as it was** — approved, with no project — which is the issue's own
sentence, and the answer says so: ``requestProjectId`` is read off the request after the commit
rather than assumed, and ``detail`` says it in words. Undoing the mesa's decision is the board's
transaction, not the Admin's.

Refused like the confirmation, by the same ``decidable_project``: the Admin alone, whose standing
is read fresh; a 404 for an id no approval filed; a 409 for one already decided.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.auth import User
from app.db.models.resource_request import RRRequest
from app.models.shema_pending import DiscardedProject, ProjectDiscard
from app.services.shema import _trail
from app.services.shema._grant_rules import require_admin_in
from app.services.shema.confirm_project import decidable_project

logger = logging.getLogger(__name__)

#: What the answer says of the request, for whoever reads the body without the screen.
REQUEST_STAYS = "The request stays approved, with no project."


async def reject_pending_project(
    db: AsyncSession,
    project_id: str,
    *,
    payload: ProjectDiscard,
    actor: User,
    app_key: str,
) -> DiscardedProject:
    """Mark the pending project discarded, with the reason, and leave its request alone."""
    await require_admin_in(db, actor, (app_key,))
    project = await decidable_project(db, project_id)

    now = datetime.now(UTC)
    project.discarded_at = now
    project.discarded_by = actor.id
    project.discard_reason = payload.reason
    _trail.stage(
        db,
        actor=actor,
        subject="pending_project",
        action="rejected",
        subject_id=project.id,
        project_id=project.id,
        region_key=_trail.region_value(project.region_key),
        fields=("discardReason",),
    )
    discarded_id, request_id = project.id, project.source_request_id or ""
    await db.commit()

    request_project_id = (
        await db.execute(select(RRRequest.shema_project_id).where(RRRequest.id == request_id))
    ).scalar_one_or_none()

    logger.info(
        "shema pending project discarded",
        extra={
            "shema_operation": "reject_pending_project",
            "shema_user_id": actor.id,
            "shema_project_id": discarded_id,
            "shema_request_id": request_id,
        },
    )
    return DiscardedProject(
        id=discarded_id,
        reason=payload.reason,
        discardedAt=now,
        requestId=request_id,
        requestProjectId=request_project_id,
        detail=REQUEST_STAYS,
    )
