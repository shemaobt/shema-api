"""``GET /api/shema/pending-projects`` — what the Admin has to confirm or discard (OBT-547).

The projects the mesa's approval filed and nobody decided yet, oldest first, each with the
people it proposes and the name of the request that filed it — the section *Aguardando
confirmação* of the Admin's access screen reads this and nothing else. It is the one read of a
pending project there is: ``_scope.pending_projects`` is a statement of its own, and no reader of
the collection composes it.

**Built for the Admin's reader, like the record** (OBT-528). A pending project names the place the
team typed, so it leaves through :class:`~app.models.shema_privacy.LeavingShape`, and the reader is
``_scope.readership``'s answer for the caller — coordination for the Admin, on
``COORDINATION_EVERYWHERE``'s hypothesis. Nothing here decides that the Admin reads the truth.

**Three reads for the whole list**, never one per project: the projects, their proposed members,
and the requests' registered names. The name is read off the request rather than copied onto the
project, because it is the request's (A0) and a project has no column for it.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.resource_request import RRRequest
from app.db.models.shema import ShemaProject
from app.db.models.shema_pending_member import ShemaProjectPendingMember
from app.models.shema_pending import PendingMember, PendingProject
from app.services.shema._scope import Readership, pending_projects


async def list_pending_projects(
    db: AsyncSession, *, readership: Readership
) -> list[PendingProject]:
    """Every project waiting for the Admin, oldest first, as the Admin reads it."""
    stmt = pending_projects().order_by(ShemaProject.created_at, ShemaProject.id)
    projects = list((await db.execute(stmt)).scalars())
    if not projects:
        return []

    members: dict[str, list[PendingMember]] = {}
    rows = await db.execute(
        select(ShemaProjectPendingMember)
        .where(ShemaProjectPendingMember.project_id.in_([project.id for project in projects]))
        .order_by(ShemaProjectPendingMember.project_id, ShemaProjectPendingMember.position)
    )
    for row in rows.scalars():
        members.setdefault(row.project_id, []).append(PendingMember.model_validate(row))

    request_ids = [project.source_request_id for project in projects if project.source_request_id]
    names: dict[str, str] = dict(
        (
            await db.execute(
                select(RRRequest.id, RRRequest.reg_name).where(RRRequest.id.in_(request_ids))
            )
        )
        .tuples()
        .all()
    )

    return [
        PendingProject.read_by(project, readership.reader_of(project.region_key)).model_copy(
            update={
                "request_id": project.source_request_id or "",
                "request_name": names.get(project.source_request_id or "", ""),
                "members": members.get(project.id, []),
            }
        )
        for project in projects
    ]
