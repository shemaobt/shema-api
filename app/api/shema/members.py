"""Project members — the roster of a project, and the projects an account belongs to (OBT-524).

Four routes in two routers, and the split is who may reach them:

* ``door_router`` is included into the PME's door (``docs/shema.md`` §6.8): ``GET`` of a project's
  roster and ``GET /me/projects``. A project member may hold no Shemá role at all — a live
  membership is what puts ``equipe`` in their session — so these two reads cannot sit behind the
  Shemá app gate. The door admits them; the service decides the rest, and a caller who reaches
  neither the project's region nor its team is answered the same 404 as a project that does not
  exist.
* ``router`` is included into ``authenticated`` and carries the two writes, each guarded by
  ``AdminUser``: only the Admin puts people on a team or takes them off (OBT-522).

Its own file rather than a block at the end of ``projects.py``, on ``health_assessments.py``'s
precedent for a sub-resource of ``/projects/{id}``: the record's routes are another issue's
(OBT-528) to rewrite, and a sub-resource with its own owner is the collision rule — *create your
own file* — applied to a router.

The handlers declare their dependencies, call one service and return what it answers; the reach
arrives as a ``RosterReach`` from ``_deps.py`` and is handed straight down (ADR 0009).
"""

from __future__ import annotations

from fastapi import APIRouter, status

from app.api.shema._deps import AdminUser, Db, DoorUser, Roster
from app.models.shema_project_member import ProjectMember, ProjectMemberCreate, ProjectRef
from app.services.shema import (
    add_project_member,
    list_my_projects,
    list_project_members,
    remove_project_member,
)

#: The Admin's two writes — included into ``authenticated``.
router = APIRouter()

#: The two reads a member has — included into the PME's door.
door_router = APIRouter()

_MEMBERS = "/projects/{project_id}/members"


@door_router.get(_MEMBERS, response_model=list[ProjectMember])
async def read_members(
    project_id: str, user: DoorUser, reach: Roster, db: Db
) -> list[ProjectMember]:
    """Who is on the project's team now, and since which day.

    Read by whoever reaches the project's region, by its own live members, and by the Admin.
    """
    return await list_project_members(db, reach, project_id, user=user)


@door_router.get("/me/projects", response_model=list[ProjectRef])
async def read_my_projects(user: DoorUser, db: Db) -> list[ProjectRef]:
    """The projects the caller is a live member of — what the form and *Solicitar recurso* read."""
    return await list_my_projects(db, user)


@router.post(_MEMBERS, response_model=ProjectMember, status_code=status.HTTP_201_CREATED)
async def add_member(
    project_id: str, payload: ProjectMemberCreate, admin: AdminUser, reach: Roster, db: Db
) -> ProjectMember:
    """Put an account on the project's team. A live member already there is a 409."""
    return await add_project_member(db, reach, project_id, member_id=payload.user_id, actor=admin)


@router.delete(
    _MEMBERS + "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
async def remove_member(
    project_id: str, user_id: str, admin: AdminUser, reach: Roster, db: Db
) -> None:
    """Take an account off the team — the row is marked, never deleted.

    ``response_model=None`` because ``-> None`` reaches FastAPI as the string ``"None"`` under
    ``from __future__ import annotations``, and a 204 must not declare a body.
    """
    await remove_project_member(db, reach, project_id, user_id, actor=admin)
