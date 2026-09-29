from typing import NamedTuple

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.auth import User
from app.services.resource_request._membership import TEAM_ROLE, granted_roles, member_project_ids


class FormIdentity(NamedTuple):
    #: The roles this account holds **in the form**: its grants, plus ``equipe`` when it is a
    #: live member of any PME project.
    roles: tuple[str, ...]
    #: The PME projects it is a live member of — the ones it may open a request from.
    projects: tuple[str, ...]


async def who_am_i(db: AsyncSession, user: User, app_key: str) -> FormIdentity:
    """What the form needs to know about the signed-in account — FE-52 (OBT-538).

    ``GET /api/auth/my-roles`` answers the **grants** alone, and since ``20260928_rr08``
    (BE-19, OBT-520) the team holds no grant here: ``equipe`` is a membership of a PME project
    (GATE-04 D1). So for every team account that route answers an empty list, and the form —
    which translated that list into its session role — refused the team at login and signed
    it out at every boot revalidation. This is the form's own answer, read by the same rule
    its door applies (``enters_the_form``): a grant, or a live membership.

    **The membership is read once and serves both fields**: the project ids, and whether
    ``equipe`` is among the roles. That route is platform surface and serves every app; the
    membership is this module's reading, so the answer lives here.
    """
    granted = await granted_roles(db, user.id, app_key)
    projects = tuple(sorted(set((await db.execute(member_project_ids(user.id))).scalars())))
    roles = granted | {TEAM_ROLE} if projects else granted
    return FormIdentity(roles=tuple(sorted(roles)), projects=projects)
