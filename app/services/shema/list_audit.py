"""The audit feed — every act on the PME the caller's regions cover, newest first (OBT-577).

Two ledgers, one list. ``shema_record_edits`` holds the project record's fields with both
sides of each change, and ``shema_change_log`` holds every other act with the keys it touched
and no value. A reader who wants *who changed anything, and when* should not have to know which
of the two a given act landed in, so this merges them; the ``source`` of each entry says which
it came from.

**Who reads it: the coordination and the Admin**, Daniel's proposal on the issue (7/out/2026).
:data:`AUDIT_AUDIENCE` is the one place that is written; the Resource Circle, the OBT Lab and the
project team do not read the trail of who changed what.

**What the record's side tells a reader is what their read of the record tells them.** A field
the reader is handed reduced (a withheld place, a prayer request kept in coordination, a team's
health outside the audience) has its rows left out, exactly as ``changes_since`` leaves them out
of a 409 (OBT-556): *the place changed* is itself the fact the reduction hides. The change log
needs no such filter, because it has no value to leak.

**Region-scoped in the query**, as ``list_role_changes`` is: a regional coordinator reads their
regions' acts and the acts that belong to no region (the intercessor network, a global meeting),
and a caller who reaches nothing reads nothing.
"""

from __future__ import annotations

import json

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthorizationError
from app.db.models.shema import ShemaProject
from app.db.models.shema_audit import ShemaRecordEdit
from app.db.models.shema_change_log import ShemaChangeLog
from app.models.shema_audit import AuditEntry
from app.services.shema._audit import keys_hidden_from
from app.services.shema._scope import (
    ADMIN_ROLE,
    COORDINATOR_ROLE,
    Readership,
    visible_projects,
)
from app.utils.stored_time import as_utc

#: The roles that read the trail. The platform admin passes every guard here, as everywhere.
AUDIT_AUDIENCE: tuple[str, ...] = (COORDINATOR_ROLE, ADMIN_ROLE)

DEFAULT_LIMIT = 200
MAX_LIMIT = 500


def may_read_audit(granted: frozenset[str] | set[str], *, platform_admin: bool) -> bool:
    """Whether this grant is in :data:`AUDIT_AUDIENCE`."""
    return platform_admin or any(role in granted for role in AUDIT_AUDIENCE)


async def list_audit(
    db: AsyncSession,
    readership: Readership,
    *,
    allowed: bool,
    project_id: str | None = None,
    limit: int = DEFAULT_LIMIT,
) -> list[AuditEntry]:
    """The most recent acts the caller may be told of, newest first.

    **The reach is the reader's coordination**, not the session's scope: the ``admin`` role holds
    no region row and reaches nothing as a scope, yet coordinates everywhere
    (``COORDINATION_EVERYWHERE``), and the trail is the coordination's to read.
    """
    scope = readership.coordination
    if not allowed:
        raise AuthorizationError("The audit trail is read by the coordination and the Admin.")
    if not scope.global_ and not scope.regions:
        return []
    limit = max(1, min(limit, MAX_LIMIT))

    log_stmt = select(ShemaChangeLog)
    if project_id is not None:
        log_stmt = log_stmt.where(ShemaChangeLog.project_id == project_id)
    if not scope.global_:
        log_stmt = log_stmt.where(
            or_(
                ShemaChangeLog.region_key.is_(None),
                ShemaChangeLog.region_key.in_(sorted(scope.regions)),
            )
        )
    log_stmt = log_stmt.order_by(ShemaChangeLog.occurred_at.desc(), ShemaChangeLog.id.desc())
    log_rows = (await db.execute(log_stmt.limit(limit))).scalars().all()

    reachable = visible_projects(scope)
    if project_id is not None:
        reachable = reachable.where(ShemaProject.id == project_id)
    projects = {project.id: project for project in (await db.execute(reachable)).scalars()}
    edit_rows: list[ShemaRecordEdit] = []
    if projects:
        edit_stmt = (
            select(ShemaRecordEdit)
            .where(ShemaRecordEdit.project_id.in_(list(projects)))
            .order_by(ShemaRecordEdit.changed_at.desc(), ShemaRecordEdit.id.desc())
            .limit(limit)
        )
        edit_rows = list((await db.execute(edit_stmt)).scalars())

    hidden = {pid: keys_hidden_from(project, readership) for pid, project in projects.items()}
    entries = [
        AuditEntry.model_validate(
            {
                "source": "log",
                "subject": row.subject,
                "subjectId": row.subject_id,
                "action": row.action,
                "projectId": row.project_id,
                "regionKey": row.region_key,
                "fields": json.loads(row.field_keys) if row.field_keys else [],
                "changedBy": row.actor_name,
                "changedAt": as_utc(row.occurred_at),
            }
        )
        for row in log_rows
    ] + [
        AuditEntry.model_validate(
            {
                "source": "record",
                "subject": "project",
                "subjectId": row.project_id,
                "action": "updated",
                "projectId": row.project_id,
                "regionKey": projects[row.project_id].region_key.value,
                "fields": [row.field_key],
                "oldValue": row.old_value,
                "newValue": row.new_value,
                "changedBy": row.changed_by_name,
                "changedAt": as_utc(row.changed_at),
            }
        )
        for row in edit_rows
        if row.field_key not in hidden[row.project_id]
    ]
    entries.sort(key=lambda entry: entry.changed_at, reverse=True)
    return entries[:limit]
