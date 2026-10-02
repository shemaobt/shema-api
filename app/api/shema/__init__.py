"""The module's router, mounted in ``app/main.py`` under ``/api/shema``.

It carried no routes until BE-03, and the anchor is what let that first endpoint
arrive without touching ``app/main.py`` and without re-deciding a prefix three documents
already name — OBT-390's own description, the ecosystem's ``CLAUDE.md`` §3.2 and
FE-44's frozen contract, which writes all twelve of its endpoint sections under it.

Later issues **include their own sub-router on a line of its own** at the end of the
block below, and never reorder or delete somebody else's. ``include_router`` and not
``app/api/annotation_studio/__init__.py``'s ``routes.append`` loop: the sibling that
shipped (``app/api/resource_requests/__init__.py``) uses this form, and a sub-router
here declares its own full path rather than a second prefix, so nothing is applied
twice.

**Deny by default, and it is a property of this file rather than a thing to remember**
(BE-03). Sub-routers are included into ``authenticated``, which carries
``require_app_access(APP_KEY)`` once, so a route added by a later issue is refused for an
account with no Shemá grant **whether or not its author wired a guard**. A route added
straight to ``router`` is the only way past that, and it is exactly what BE-12's two
unauthenticated intake routes needed (``docs/shema.md`` §6.6, FE-44 §9.0), and then the
intercessor's exit link (OBT-531) — which is why each hole is a named, deliberate line in a
diff instead of a dependency somebody has to notice is missing.
``tests/test_shema/test_access.py`` reads the built application's route table and fails on
any ``/api/shema`` route that does not carry the guard and is not in its allowlist.

**The PME's door is the other deliberate exception, and it is narrower rather than wider**
(OBT-523, ``docs/shema.md`` §6.8). ``GET /api/shema/session`` is the console's sign-in read,
and the mesa and the Gestor sign in holding no Shemá grant. So ``door`` carries ``DOOR`` —
a Shemá role, or ``gestor``/``mesa`` held in the form, or the ``equipe`` a live project
membership adds (OBT-524) — and holds the session, the two reads a member has — a
project's roster and ``/me/projects`` — and, since OBT-541, the notification panel and its read
mark, because the resource-request form's notices are addressed to accounts only the door
admits. An account the form made gets those answered and is
still refused by every route under ``authenticated``. A route belongs on ``door`` only if
every account at the door may call it and the service decides what it answers;
``tests/test_shema/test_access.py`` pins the door's routes, by method and path, in
``DOOR_ROUTES``, so adding one is an edit somebody has to justify.

**A validation error says nothing about the value it refused, and that is this file's too**
(OBT-556). The three routers are ``ShemaRouter``, so every route included into them — a later
issue's included — is a ``ShemaRoute``: a 422 drops each field error's ``input``, and an
unexpected Pydantic error reaches the log named by its location and never by its value.
``app/api/shema/_routing.py`` carries the argument, and ``tests/test_shema/test_quiet_errors.py``
reads the built application's route table for a route that is not one.

``tests/test_shema/test_mount.py`` proves the wiring by hanging its own route off this
object, which is the check that survives a module with no routes — and the one that
keeps working the day this file's own routes are the thing being moved.

The layout those routes land in, which issue owns each of them, and the capability
audit they rest on, is ``docs/shema.md``.
"""

from __future__ import annotations

from app.api.shema._deps import APP_KEY, DOOR
from app.api.shema._routing import ShemaRouter
from app.api.shema.access import router as access_router
from app.api.shema.eten import router as eten_router
from app.api.shema.forms import intake as intake_router
from app.api.shema.forms import router as forms_router
from app.api.shema.health_assessments import router as health_assessments_router
from app.api.shema.intercessor_exit import router as exit_router
from app.api.shema.intercessors import router as intercessors_router
from app.api.shema.meetings import router as meetings_router
from app.api.shema.members import door_router as members_door_router
from app.api.shema.members import router as members_router
from app.api.shema.notifications import door_router as notifications_door_router
from app.api.shema.notifications import router as notifications_router
from app.api.shema.pending_projects import router as pending_projects_router
from app.api.shema.prayer import router as prayer_router
from app.api.shema.projects import router as projects_router
from app.api.shema.regions import router as regions_router
from app.api.shema.session import router as session_router
from app.api.shema.transfer import router as transfer_router
from app.core.access_control import require_app_access

router = ShemaRouter()

#: Everything in this module that needs a signed-in Shemá account. The guard is declared
#: once here and inherited by every route included below, which is what makes the module
#: deny-by-default; see the note above for the exceptions this shape leaves room for.
authenticated = ShemaRouter(dependencies=[require_app_access(APP_KEY)])

authenticated.include_router(regions_router)  # BE-13
authenticated.include_router(intercessors_router)  # BE-13
authenticated.include_router(projects_router)  # BE-05
authenticated.include_router(health_assessments_router)  # BE-07
authenticated.include_router(forms_router)  # BE-12
authenticated.include_router(notifications_router)  # BE-15
authenticated.include_router(meetings_router)  # BE-10
authenticated.include_router(members_router)  # OBT-524
authenticated.include_router(access_router)  # BE-22, OBT-543
authenticated.include_router(eten_router)  # BE-11
authenticated.include_router(prayer_router)  # BE-09
authenticated.include_router(pending_projects_router)  # OBT-547
authenticated.include_router(transfer_router)  # BE-14

#: **The module's first deliberate hole**, and it is this line rather than a missing dependency.
#: ``GET`` and ``POST /api/shema/intake/{token}`` carry no ``Authorization`` requirement, by
#: FE-44 §9.0 and ``docs/shema.md`` §6.6: the token *is* the guard, and the guard is a service
#: function (``verify_intake_token``) so the rule holds for any future caller of it rather than
#: for the two routes it was written under. Included into ``router`` and not ``authenticated``,
#: which is what makes the exemption visible in a diff; ``tests/test_shema/test_access.py``
#: carries the two paths in ``UNAUTHENTICATED_PATHS`` and fails on a third that arrives without
#: a line added there. BE-12.
router.include_router(intake_router)

#: **The module's second deliberate hole** (OBT-531). ``GET`` and ``POST
#: /api/shema/intercessors/leave/{token}`` carry no ``Authorization`` requirement: a person in
#: the prayer network has no account, and the exit link is how they leave. The token is the
#: guard and the guard is a service function (``leave_intercessor.py``); the ``GET`` changes
#: nothing and the ``POST`` erases. Listed in ``UNAUTHENTICATED_PATHS`` beside the intake's.
router.include_router(exit_router)

#: The PME's door: the session read, for any account holding a role of the session's
#: vocabulary in either app (OBT-523), the member's two reads (OBT-524), and the notification
#: panel and its read mark (OBT-541). Everything else stays under ``authenticated``.
door = ShemaRouter(dependencies=[DOOR])

door.include_router(session_router)  # BE-03, OBT-523
door.include_router(members_door_router)  # OBT-524
door.include_router(notifications_door_router)  # OBT-541

router.include_router(door)

# Keep this the last statement in the file. ``include_router`` copies routes at call time,
# so a line added below it is included into a router the application never sees: the route
# would not 500, it would simply 404.
# ``test_every_authenticated_route_reaches_the_application`` is what catches that.
router.include_router(authenticated)
