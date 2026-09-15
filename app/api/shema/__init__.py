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
unauthenticated intake routes will need (``docs/shema.md`` §6.6, FE-44 §9.0) — which is
why the hole is a named, deliberate line in a diff instead of a dependency somebody has to
notice is missing. ``tests/test_shema/test_access.py`` reads the built application's route
table and fails on any ``/api/shema`` route that does not carry the guard, with the intake
allowlist stated there and empty today.

``tests/test_shema/test_mount.py`` proves the wiring by hanging its own route off this
object, which is the check that survives a module with no routes — and the one that
keeps working the day this file's own routes are the thing being moved.

The layout those routes land in, which issue owns each of them, and the capability
audit they rest on, is ``docs/shema.md``.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.shema._deps import APP_KEY
from app.api.shema.health_assessments import router as health_assessments_router
from app.api.shema.projects import router as projects_router
from app.api.shema.session import router as session_router
from app.core.access_control import require_app_access

router = APIRouter()

#: Everything in this module that needs a signed-in Shemá account. The guard is declared
#: once here and inherited by every route included below, which is what makes the module
#: deny-by-default; see the note above for the one exception this shape leaves room for.
authenticated = APIRouter(dependencies=[require_app_access(APP_KEY)])

authenticated.include_router(session_router)  # BE-03
authenticated.include_router(projects_router)  # BE-05
authenticated.include_router(health_assessments_router)  # BE-07

# Keep this the last statement in the file. ``include_router`` copies routes at call time,
# so a line added below it is included into a router the application never sees: the route
# would not 500, it would simply 404.
# ``test_every_authenticated_route_reaches_the_application`` is what catches that.
router.include_router(authenticated)
