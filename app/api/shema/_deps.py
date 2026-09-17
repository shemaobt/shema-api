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

**One role key is also asked as a value and not only as a guard**, which is :data:`MayApply`
below. It is not the capability map this file refuses: there is no table, no second
vocabulary and no OR — it is ``coordinator``, the same key the route beside it is guarded on,
read as a boolean because the answer shapes a payload rather than admitting a request. The
grant is read once per request by :func:`_granted` and both consumers share it, so asking the
second question costs no second query: a scope and a role resolved from two separate reads of
one fact is the defect ``app/services/shema/_scope.py``'s ``scope_from_roles`` was written to
close, and it would come straight back through this file.
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
    granted_roles,
    scope_from_roles,
)

APP_KEY = "shema"

Db = Annotated[AsyncSession, Depends(get_db)]

CurrentUser = Annotated[User, require_app_access(APP_KEY)]
GlobalStrategistUser = Annotated[User, require_role(APP_KEY, GLOBAL_ROLE)]
CoordinatorUser = Annotated[User, require_role(APP_KEY, COORDINATOR_ROLE)]
ObtLabUser = Annotated[User, require_role(APP_KEY, OBT_LAB_ROLE)]
ResourceCircleUser = Annotated[User, require_role(APP_KEY, RESOURCE_CIRCLE_ROLE)]


async def _granted(user: CurrentUser, db: Db) -> frozenset[str]:
    """The Shemá role keys this account holds, read once and shared by everything below.

    FastAPI caches a dependency's result for the life of one request, so a handler that
    declares both :data:`Scope` and :data:`MayApply` reads the grant once. That is the whole
    reason this is a dependency of its own rather than a line inside each of them.

    **A platform admin is answered without reading the table**, as they are by every guard in
    this repository. The empty set is not a claim that they hold nothing — it is that nothing
    below depends on what they hold, because every consumer asks ``is_platform_admin`` first.
    """
    if user.is_platform_admin:
        return frozenset()
    return frozenset(await granted_roles(db, user.id, APP_KEY))


#: The caller's Shemá roles, read once per request.
Granted = Annotated[frozenset[str], Depends(_granted)]


async def _scope(user: CurrentUser, db: Db, granted: Granted) -> RegionScope:
    """Resolve the caller's region scope, once, for a handler to hand down.

    Chained behind ``CurrentUser`` rather than beside it, so an account with no role in this
    app is refused by the app gate with the message that names the app, and only a member
    gets as far as being asked how far they reach.

    **The router receives this value and does nothing with it but pass it on.**
    ``docs/shema.md`` §6.2 refuses two temptations by name, and the first is a scope the
    router applies: ``app/api/shema/`` may declare this dependency and hand the value to a
    service; it may not ``WHERE`` anything. Zero database access in ``app/api/`` is ADR 0009,
    and a filter applied in a handler is a filter the next handler writes slightly
    differently.
    """
    return await scope_from_roles(db, user, set(granted))


#: The caller's reach, for a handler to pass straight into a service.
Scope = Annotated[RegionScope, Depends(_scope)]


async def _may_apply(user: CurrentUser, granted: Granted) -> bool:
    """Whether this caller may apply a submission to the record — ``coordinator``, or an admin.

    The question ``POST /forms/submissions/{id}/import`` is already guarded on, asked as a
    value so that the read beside it can show the person who will answer it what they are
    answering. ``app/services/shema/read_submission.py`` carries why that matters: the answers
    an import writes are on no other surface until it has written them, so a coordinator who
    cannot read them decides blind — and one of them is the consent level that decides whether
    a prayer request leaves coordination at all.

    No database read of its own: :func:`_granted` has already been resolved for this request.
    """
    return user.is_platform_admin or COORDINATOR_ROLE in granted


#: Whether the caller can apply what they are being shown. **A payload's shape, never a guard**
#: — a route that must refuse a non-coordinator uses :data:`CoordinatorUser`, which refuses.
MayApply = Annotated[bool, Depends(_may_apply)]
