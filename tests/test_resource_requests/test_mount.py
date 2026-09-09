"""BE-01's mount, asserted through the mechanism that will carry BE-04's first route.

``include_router`` on a router with no routes registers nothing — no path on the
application, no entry in OpenAPI — so today there is no response to probe. Hanging a
route off the module's own router and rebuilding the app exercises the real wiring
anyway, and keeps doing so once the module has routes of its own: a route mounted under
a prefix nobody registered does not fail loudly, it 404s.
"""

from __future__ import annotations

from app.api.resource_requests import router
from app.main import create_app

PREFIX = "/api/resource-requests"


def test_main_mounts_the_module_router_under_its_prefix() -> None:
    probe = "/_mount_probe"
    mark = len(router.routes)

    try:

        @router.get(probe)
        async def _probe() -> None:
            return None

        app = create_app()
        paths = {getattr(route, "path", "") for route in app.routes}
    finally:
        del router.routes[mark:]

    assert f"{PREFIX}{probe}" in paths
