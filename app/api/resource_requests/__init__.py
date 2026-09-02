"""The module's router, mounted in ``app/main.py`` under ``/api/resource-requests``.

It carries no routes yet — BE-02 brings the tables, BE-03 the capability checks, BE-04
onwards the endpoints. What exists here first is the anchor: a route added by a later
issue reaches the outside world without touching ``app/main.py``, and without re-deciding
a prefix that ``tests/test_resource_requests/conftest.py`` already assumes.

Mounting a router with no routes registers nothing — no path on the application, no entry
in OpenAPI. So ``tests/test_resource_requests/test_mount.py`` proves the wiring by hanging
a route off this object and looking for it on a freshly built app, rather than by asking
for a response that does not exist yet.

The layout those routes land in, and which issue owns each of them, is
``docs/resource_requests.md``.
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()
