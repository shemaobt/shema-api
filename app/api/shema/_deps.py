"""Shared dependencies for the Shemá routers — the app key, the roles, the scope, the door.

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

**The Admin has an alias of its own, ahead of the routes that need it.** ``AdminUser`` is
``require_role(APP_KEY, "admin")`` — the Annotation Studio's shape — for the Admin of OBT-522
(*"Admin da plataforma"*), which is a role somebody is granted and **not** the installation's
``is_platform_admin``. OBT-524 (*só admin escreve*) and OBT-543 (*só admin alcança*) both
guard on it, and one line here is what keeps two sibling branches from adding it twice. It
reads the ``shema`` grant, like every guard below the door.

**The PME's door is the one guard here that looks past this app** (OBT-523).
``GET /api/shema/session`` is the console's sign-in read, and since 25/set the mesa and the
Gestor — whose grants live in ``resource-request-form`` — sign in to the console too. So the
session sits on a router of its own, ``door`` in ``__init__.py``, guarded by :data:`DOOR`:
an account passes when ``_scope.session_roles`` answers anything at all, which is a Shemá
role or the ``admin`` role held in ``shema``, ``gestor``/``mesa`` held in the form, or — since
OBT-524 — ``equipe``, which a live project membership adds. It is **one** ``Depends`` object
shared by the router and :data:`DoorUser`, so FastAPI solves it once per request, and the roles
it read are the ones the handler answers — the door and the body cannot disagree. Every other
route stays behind ``require_app_access(APP_KEY)``: the door opens the session and, since
OBT-524, the two reads a member has — a project's roster and ``/me/projects``.
``FORM_APP_KEY`` is the form's key written a second time, as ``get_rr_app_id.py`` writes it,
and ``tests/test_shema/test_access.py`` holds it to the form's own ``APP_KEY`` rather than this
file importing the form's router package.

**Two role questions are also asked as values and not only as guards**, which are
:data:`MayApply` and :data:`Reading` below. Neither is the capability map this file refuses:
there is no table and no second vocabulary. :data:`MayApply` is ``coordinator``, the same key the
route beside it is guarded on, read as a boolean. :data:`Reading` is OBT-528's reader — who reads
the truth of a sensitive place — and its OR (``globalStrategist``, the ``admin`` hypothesis, or
``coordinator`` in its own regions) is written once, in ``app/services/shema/_scope.py``'s
``readership``, which owns the region half of it; this file only hands it the grant and the
scope it already read. Both shape a payload rather than admit a request. The grant is read once
per request by :func:`_granted` and every consumer shares it, so asking a second question costs
no second query: a scope and a role resolved from two separate reads of one fact is the defect
``scope_from_roles`` was written to close, and it would come straight back through this file.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access_control import require_app_access, require_role
from app.core.auth_middleware import get_current_user
from app.core.database import get_db
from app.core.exceptions import AuthorizationError
from app.db.models.auth import User
from app.services.shema._scope import (
    ADMIN_ROLE,
    COORDINATOR_ROLE,
    GLOBAL_ROLE,
    OBT_LAB_ROLE,
    RESOURCE_CIRCLE_ROLE,
    Readership,
    RegionScope,
    RosterReach,
    granted_roles,
    readership,
    scope_from_roles,
    session_roles,
)

APP_KEY = "shema"

#: The resource-request form's app key, whose ``gestor`` and ``mesa`` open the PME's door.
FORM_APP_KEY = "resource-request-form"

Db = Annotated[AsyncSession, Depends(get_db)]

CurrentUser = Annotated[User, require_app_access(APP_KEY)]
GlobalStrategistUser = Annotated[User, require_role(APP_KEY, GLOBAL_ROLE)]
CoordinatorUser = Annotated[User, require_role(APP_KEY, COORDINATOR_ROLE)]
ObtLabUser = Annotated[User, require_role(APP_KEY, OBT_LAB_ROLE)]
ResourceCircleUser = Annotated[User, require_role(APP_KEY, RESOURCE_CIRCLE_ROLE)]
AdminUser = Annotated[User, require_role(APP_KEY, ADMIN_ROLE)]

SignedIn = Annotated[User, Depends(get_current_user)]


async def _session_roles(user: SignedIn, db: Db) -> tuple[str, ...]:
    """The roles the PME's session counts, across both apps, read once per request."""
    return await session_roles(db, user.id, app_key=APP_KEY, form_app_key=FORM_APP_KEY)


#: The caller's session roles, in precedence order — what the door admitted them on.
SessionRoles = Annotated[tuple[str, ...], Depends(_session_roles)]


async def _door(user: SignedIn, roles: SessionRoles) -> User:
    """Admit an account holding any role of the session's vocabulary, or an installation admin.

    The refusal is the app gate's own sentence, so an account holding nothing reads the same
    403 it read before the door existed.
    """
    if user.is_platform_admin or roles:
        return user
    raise AuthorizationError(
        f"You don't have access to the '{APP_KEY}' application. "
        "Please contact support to request access."
    )


#: The door, as the one ``Depends`` both ``door``'s router-level dependency and
#: :data:`DoorUser` use. A factory would build a new callable per use, and FastAPI would then
#: run the door — and read the grants — twice per request.
DOOR = Depends(_door)
DoorUser = Annotated[User, DOOR]


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


async def _reading(user: CurrentUser, granted: Granted, scope: Scope) -> Readership:
    """Where this caller reads the truth of a sensitive place — the reader of OBT-528.

    No database read of its own: :func:`_granted` and :func:`_scope` are resolved once per
    request, and the rule is ``_scope.readership``'s. Like :data:`Scope`, the router hands the
    value to a service and does nothing else with it.
    """
    return readership(scope, granted, platform_admin=user.is_platform_admin)


#: The caller's readership, for a handler to pass into the service that builds the payload.
#: **A payload's shape, never a guard.** Which routes take it is a list somebody writes:
#: ``tests/test_shema/test_privacy_owners.py``'s ``READER_ROUTES``.
Reading = Annotated[Readership, Depends(_reading)]


async def _roster(user: SignedIn, db: Db, roles: SessionRoles) -> RosterReach:
    """How far the caller reaches over the projects' rosters (OBT-524).

    Built on the session's roles rather than on the Shemá grant, because a roster is read behind
    the door: a project member may hold no Shemá role at all. It is the same :data:`SessionRoles`
    the door already solved, so the grants are read once per request, and the region scope is
    ``scope_from_roles`` over it — which is what ``GET /session`` answers ``regionScope`` from, and
    which counts a row only under a regional role.

    ``admin`` is the ``shema`` grant (the only ``admin`` the session counts), and it reaches every
    roster and nothing else — ``_scope.RosterReach`` is why that cannot become a wider region.
    """
    scope = await scope_from_roles(db, user, set(roles))
    return RosterReach(scope=scope, admin=ADMIN_ROLE in roles)


#: The caller's reach over rosters, for a members route to pass straight into a service.
Roster = Annotated[RosterReach, Depends(_roster)]


async def _door_scope(user: SignedIn, db: Db, roles: SessionRoles) -> RegionScope:
    """The region scope of a caller behind the door, where no Shemá grant is required (OBT-541).

    :data:`Scope` is chained behind the app gate, so it refuses the Gestor and the member the
    notification panel now answers — the resource-request form's notices are addressed to them
    (``_request_notices.py``). This is the same value ``GET /session`` answers ``regionScope``
    from and :func:`_roster` builds on: ``scope_from_roles`` over the session's roles, which
    counts a region row only under a regional role. So a Gestor, a mesa or a member reaches no
    region — the fail-closed floor — and a Shemá role-holder reaches exactly what
    :data:`Scope` would have given them.
    """
    return await scope_from_roles(db, user, set(roles))


#: The caller's region scope behind the door — for a route every door account may call.
DoorScope = Annotated[RegionScope, Depends(_door_scope)]
