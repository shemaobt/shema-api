"""The module's router, mounted in ``app/main.py`` under ``/api/shema``.

It carries no routes. The anchor exists so that the first endpoint of BE-03 arrives
without touching ``app/main.py`` and without re-deciding a prefix three documents
already name — OBT-390's own description, the ecosystem's ``CLAUDE.md`` §3.2 and
FE-44's frozen contract, which writes all twelve of its endpoint sections under it.

Later issues **include their own sub-router on a line of its own** at the end of the
block below, and never reorder or delete somebody else's. ``include_router`` and not
``app/api/annotation_studio/__init__.py``'s ``routes.append`` loop: the sibling that
shipped (``app/api/resource_requests/__init__.py``) uses this form, and a sub-router
here declares its own full path rather than a second prefix, so nothing is applied
twice.

``tests/test_shema/test_mount.py`` proves the wiring by hanging its own route off this
object, which is the check that survives a module with no routes — and the one that
keeps working the day this file's own routes are the thing being moved.

The layout those routes land in, which issue owns each of them, and the capability
audit they rest on, is ``docs/shema.md``.
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()
