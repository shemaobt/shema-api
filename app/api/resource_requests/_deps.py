"""Shared dependencies for resource-request routers.

``CurrentUser`` gates on holding *any* role in the app, the three role aliases gate
on a specific one, and the nine capability aliases gate on what the product
actually models. Capabilities are the ones routes should reach for: four of the
nine belong to more than one role, and ``require_role`` cannot say OR — guarding
``view_evaluation`` as ``MesaUser`` would refuse the Gestor, which is the whole of
that role's point. The table and the query behind them are
``app/services/resource_request/capabilities.py``; what lives here is the wiring.

``CanReadRequests`` is the one alias built on an OR of capabilities rather than on
one, because reading is not a row of the contract's table and must not become one:
it rides on ``edit_requests`` for the three roles that write, and on
``endorse_request`` for the Líder de Base, whose whole role is the reading his
signature requires (BE-16). Which rows that reading reaches stays ``_scope.py``'s.

``APP_KEY`` is named here and nowhere else in the module, which is where every
other application in this repository keeps its own. The service layer takes it as
a parameter rather than re-declaring it, so the literal has one home even now that
the module has two halves.

The four role keys are the ids of the frontend's ``capabilities.ts`` verbatim —
``equipe``, ``mesa``, ``gestor``, ``lider`` — and since BE-03 the pairing is no
longer held by hand: ``capabilities.json`` is vendored from that file's own
emission and ``test_capabilities.py`` refuses a mismatch.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access_control import require_app_access, require_role
from app.core.database import get_db
from app.core.exceptions import AuthorizationError
from app.db.models.auth import User
from app.services.resource_request import holds_capability

APP_KEY = "resource-request-form"

Db = Annotated[AsyncSession, Depends(get_db)]

CurrentUser = Annotated[User, require_app_access(APP_KEY)]
EquipeUser = Annotated[User, require_role(APP_KEY, "equipe")]
MesaUser = Annotated[User, require_role(APP_KEY, "mesa")]
GestorUser = Annotated[User, require_role(APP_KEY, "gestor")]


def require_capability(capability: str) -> Any:
    """Gate on one capability, resolved through the roles the account holds here.

    Chained behind ``CurrentUser`` rather than beside it, so an account with no role in
    this app is refused by the app gate with the message that names the app, and only a
    member gets as far as being asked what they may do.

    **A platform admin passes, as they pass the two guards above.** That is the
    installation's standing rule and not a hole this file punches: ``require_app_access``
    and ``require_role`` both return early on ``is_platform_admin``, so refusing here
    would make one route in this module stricter than the route beside it — and buy
    nothing, since a platform admin can grant themselves ``mesa`` with one call to
    ``grant_app_role``. The cost is real and lands on the tests: a negative test written
    per role **must not** use an admin account, or it passes for the wrong reason.
    """

    async def _check(user: CurrentUser, db: Db) -> User:
        if user.is_platform_admin:
            return user
        if not await holds_capability(db, user.id, APP_KEY, capability):
            raise AuthorizationError(f"Capability '{capability}' is required for this action.")
        return user

    return Depends(_check)


def require_any_capability(*capabilities: str) -> Any:
    """Gate on holding at least one of ``capabilities`` — the OR a single guard cannot say.

    Everything ``require_capability`` records holds here too: chained behind
    ``CurrentUser``, admits a platform admin by the installation's standing rule, and an
    unknown capability raises out of ``holds_capability`` rather than refusing forever.
    The refusal names every capability that would have opened the door, because the
    person reading the message holds none of them and should learn what the door is.
    """

    async def _check(user: CurrentUser, db: Db) -> User:
        if user.is_platform_admin:
            return user
        for capability in capabilities:
            if await holds_capability(db, user.id, APP_KEY, capability):
                return user
        raise AuthorizationError(
            f"One of the capabilities {', '.join(capabilities)} is required for this action."
        )

    return Depends(_check)


CanEditRequests = Annotated[User, require_capability("edit_requests")]
CanViewEvaluation = Annotated[User, require_capability("view_evaluation")]
CanEditEvaluation = Annotated[User, require_capability("edit_evaluation")]
CanManageFunds = Annotated[User, require_capability("manage_funds")]
CanMoveBoard = Annotated[User, require_capability("move_board")]
CanAssignFund = Annotated[User, require_capability("assign_fund")]
CanAllocateFunds = Annotated[User, require_capability("allocate_funds")]
CanEndorseRequest = Annotated[User, require_capability("endorse_request")]
CanAdministerFunds = Annotated[User, require_capability("administer_funds")]
CanReadRequests = Annotated[User, require_any_capability("edit_requests", "endorse_request")]
