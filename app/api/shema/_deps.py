"""Shared dependencies for the Shemá routers — the app key, the four roles, the scope.

``CurrentUser`` gates on holding *any* role in the app and the four role aliases gate on
one. Both are the platform's own guards (``app/core/access_control.py``) with this module's
key bound in: ``docs/shema.md`` §4.2's verdict is *reuse the spine, extend the scope*, and
the extension is the region, not a second guard.

**Shemá has no capability map, and that is a decision with a written reason.** The sibling
built ``capabilities.py`` + ``holds_capability.py`` because four of its eight capabilities
belong to more than one role and ``require_role`` cannot say OR. FE-44's authorization is
``{role, regionScope}`` and nothing in the twelve screens asks a question the four keys do
not answer, so a map here would be a table with one role per row — a layer of indirection
over ``require_role`` that costs a query per guarded request and buys an OR nobody needs.
If a later issue finds the question, the sibling's pair is the shape to copy;
``permissions``/``role_permissions`` are **not** (``docs/shema.md`` §4.10 — they exist as
tables and are wired into neither guard).

``APP_KEY`` is named here and nowhere else in the module, which is where all eight
applications in this repository keep theirs and where
``test_the_app_key_is_named_once_in_the_module`` looks.

**The role keys are camelCase on purpose**, against this repository's mostly snake_case
habit. They are the frontend's own ids verbatim (``SessionRole`` in ``src/types/role.ts``),
which is the precedent ``resource-request-form`` set with ``equipe``/``mesa``/``gestor``/
``lider``: ``GET /api/shema/session`` must answer a ``SessionRole`` the console uses as a
key, and a translation table between two spellings of one vocabulary is a second place to
be wrong, read on every request. They are **imported** from
``app/services/shema/_scope.py`` rather than retyped, because that module has to know which
of the four is the unscoped one and two copies of a four-key vocabulary is exactly the
defect this paragraph is about.

**A platform admin passes every guard here**, as they pass every guard in this repository:
both platform guards return early on ``is_platform_admin``, and refusing inside this module
would make one route stricter than the route beside it while buying nothing — an admin can
grant themselves ``coordinator`` with one call to ``grant_app_role``. The cost is real and
lands on the tests: **a negative test written per role must not use an admin account**, or
it passes for the wrong reason.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access_control import require_app_access, require_role
from app.core.database import get_db
from app.db.models.auth import User
from app.services.shema._scope import (
    COORDINATOR_ROLE,
    GLOBAL_ROLE,
    OBT_LAB_ROLE,
    RESOURCE_CIRCLE_ROLE,
    RegionScope,
    region_scope,
)

APP_KEY = "shema"

Db = Annotated[AsyncSession, Depends(get_db)]

CurrentUser = Annotated[User, require_app_access(APP_KEY)]
GlobalStrategistUser = Annotated[User, require_role(APP_KEY, GLOBAL_ROLE)]
CoordinatorUser = Annotated[User, require_role(APP_KEY, COORDINATOR_ROLE)]
ObtLabUser = Annotated[User, require_role(APP_KEY, OBT_LAB_ROLE)]
ResourceCircleUser = Annotated[User, require_role(APP_KEY, RESOURCE_CIRCLE_ROLE)]


async def _scope(user: CurrentUser, db: Db) -> RegionScope:
    """Resolve the caller's region scope, once, for a handler to hand down.

    Chained behind ``CurrentUser`` rather than beside it, so an account with no role in this
    app is refused by the app gate with the message that names the app, and only a member
    gets as far as being asked how far they reach.

    **The router receives this value and does nothing with it but pass it on.**
    ``docs/shema.md`` §6.2 refuses two temptations by name, and the first is a scope the
    router applies: ``app/api/shema/`` may declare this dependency and hand the value to a
    service; it may not ``WHERE`` anything, because zero database access in ``app/api/`` is
    [ADR 0009](../../../docs/adr/0009-routers-never-touch-the-database.md) and a filter
    applied in a handler is a filter the next handler writes slightly differently.
    """
    return await region_scope(db, user, APP_KEY)


#: The caller's reach, for a handler to pass straight into a service.
Scope = Annotated[RegionScope, Depends(_scope)]
