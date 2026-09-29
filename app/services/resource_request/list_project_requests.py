from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.auth import User
from app.db.models.resource_request import RRRequest
from app.db.models.shema import ShemaProject
from app.services.resource_request._cards import CardFacts, cards_of
from app.services.resource_request._editing import Editing
from app.services.resource_request._membership import granted_roles, is_member_of
from app.services.shema._scope import (
    ADMIN_ROLE,
    GESTOR_ROLE,
    MESA_ROLE,
    reaches,
    refuse_out_of_scope,
    scope_from_roles,
)
from app.services.shema._scope import granted_roles as shema_granted_roles

#: The form's roles that reach every project: they already reach the whole board.
_BOARD_ROLES = frozenset({ADMIN_ROLE, MESA_ROLE, GESTOR_ROLE})


async def list_project_requests(
    db: AsyncSession, project_id: str, user: User, app_key: str, shema_app_key: str
) -> list[CardFacts]:
    """The requests of one PME project, as cards — BE-24 (OBT-536).

    What the PME's project page draws (OBT-544): each request and where it is, and the open
    instance if there is one, so the *Solicitar recurso* button knows whether to say
    *Iniciar* or *em preenchimento por X*. Cancelled instances are not listed, as in
    ``list_requests``.

    **Who reads it** — the issue's guard, read across the two apps the PME session carries
    (OBT-523):

    * the platform admin, and ``admin``, ``mesa`` or ``gestor`` in either app — the Admin of
      OBT-522 is one role seeded in both, and the mesa and the Gestor already reach the whole
      board;
    * a regional role of the PME whose scope reaches the project's region — ``region_scope``'s
      rule, read through ``scope_from_roles`` so the grants are read once, which is also what
      gives ``globalStrategist`` every project;
    * a live member of the project (OBT-524).

    **Everyone else gets 404**, a missing project included — the Shemá module's convention,
    because a 403 would confirm that a project the caller may not see exists. The refusal is
    logged through ``refuse_out_of_scope`` so it reads like every other scoped miss in the PME.

    The route asks for a session and nothing else: this module's own door (``_app_member``)
    would refuse a regional coordinator who holds no role in the form, and that coordinator is
    exactly who this read is for.
    """
    form_granted = await granted_roles(db, user.id, app_key)
    shema_granted = await shema_granted_roles(db, user.id, shema_app_key)
    scope = await scope_from_roles(db, user, shema_granted)

    project = await db.get(ShemaProject, project_id)
    sees = project is not None and (
        user.is_platform_admin
        or bool(form_granted & _BOARD_ROLES)
        or bool(shema_granted & _BOARD_ROLES)
        or reaches(scope, project.region_key)
        or await is_member_of(db, user.id, project_id)
    )
    if not sees:
        raise refuse_out_of_scope(
            scope, user=user, operation="resource_request_cards", project_id=project_id
        )

    rows = await db.execute(
        select(RRRequest)
        .where(RRRequest.shema_project_id == project_id, RRRequest.cancelled_at.is_(None))
        .order_by(RRRequest.created_at.desc())
    )
    editing = Editing(user_id=user.id, admin=user.is_platform_admin or ADMIN_ROLE in form_granted)
    return await cards_of(db, list(rows.scalars().all()), editing)
