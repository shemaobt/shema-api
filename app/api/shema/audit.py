"""``GET /api/shema/audit`` — who changed what in the PME, and when (OBT-577).

The coordination and the Admin read it; the service says why and owns the rule
(``list_audit.AUDIT_AUDIENCE``). The route passes the reader through and decides nothing, like
every read here.
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.api.shema._deps import CurrentUser, Db, MayReadAudit, Reading
from app.models.shema_audit import AuditEntry
from app.services.shema import list_audit
from app.services.shema.list_audit import DEFAULT_LIMIT, MAX_LIMIT

router = APIRouter()


@router.get("/audit", response_model=list[AuditEntry])
async def read_audit(
    user: CurrentUser,
    db: Db,
    reading: Reading,
    may_read: MayReadAudit,
    project_id: str | None = Query(default=None, alias="projectId"),
    limit: int = Query(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
) -> list[AuditEntry]:
    """Every act the caller's regions cover — record fields with both sides, other acts with keys.

    Newest first. ``projectId`` narrows to one project's acts. A field the caller is handed
    reduced on the record is left out of the feed, and nothing in the change log carries a value.
    """
    return await list_audit(db, reading, allowed=may_read, project_id=project_id, limit=limit)
