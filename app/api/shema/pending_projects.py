"""The projects the mesa's approval filed — the Admin's list, and the Admin's two acts (OBT-547).

Three routes, each behind :data:`~app.api.shema._deps.AdminUser`, inside the ``authenticated``
router that already refuses anybody with no Shemá role:

* ``GET /pending-projects`` — what waits for a conference, built for the Admin's reader;
* ``POST /projects/{project_id}/confirm`` — the adjustments, the flag and the list of people;
* ``POST /projects/{project_id}/reject`` — the discard, with its reason.

**The list is not** ``/projects/pending``: the ficha's ``GET /projects/{project_id}`` is included
before this router and would take ``pending`` for an id. The two acts sit under the project's own
path, as the issue names them, and collide with nothing there.

Its own file, on ``members.py``'s precedent: the record's routes are another issue's, and the
handlers here only declare the guard, the reader or the body, and call one service each (ADR
0009). ``docs/shema.md`` §6.11 is the contract.
"""

from __future__ import annotations

from fastapi import APIRouter, Response

from app.api.shema._deps import APP_KEY, PER_READER_CACHE_CONTROL, AdminUser, Db, Reading
from app.models.shema_pending import (
    ConfirmedProject,
    DiscardedProject,
    PendingProject,
    ProjectConfirmation,
    ProjectDiscard,
)
from app.services.shema import confirm_project, list_pending_projects, reject_pending_project

router = APIRouter()


@router.get("/pending-projects", response_model=list[PendingProject])
async def read_pending_projects(
    admin: AdminUser, reading: Reading, db: Db, response: Response
) -> list[PendingProject]:
    """Every project waiting for the Admin, oldest first, with the people it proposes."""
    response.headers["Cache-Control"] = PER_READER_CACHE_CONTROL
    return await list_pending_projects(db, readership=reading)


@router.post("/projects/{project_id}/confirm", response_model=ConfirmedProject)
async def confirm(
    project_id: str, payload: ProjectConfirmation, admin: AdminUser, db: Db
) -> ConfirmedProject:
    """Register the project: the adjustments, the flag, the requests, the team, the invitations."""
    return await confirm_project(db, project_id, payload=payload, actor=admin, app_key=APP_KEY)


@router.post("/projects/{project_id}/reject", response_model=DiscardedProject)
async def reject(
    project_id: str, payload: ProjectDiscard, admin: AdminUser, db: Db
) -> DiscardedProject:
    """Discard the project with its reason; the request stays approved and without one."""
    return await reject_pending_project(
        db, project_id, payload=payload, actor=admin, app_key=APP_KEY
    )
