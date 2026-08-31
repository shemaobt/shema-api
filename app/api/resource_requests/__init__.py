"""The module's router, mounted in ``app/main.py`` under ``/api/resource-requests``.

It carried no routes until BE-04, and the anchor is what let those arrive without touching
``app/main.py`` and without re-deciding a prefix ``tests/test_resource_requests/conftest.py``
already assumed. ``requests.py`` is the request lifecycle; later issues include their own
beside it rather than growing one file.

``test_mount.py`` still proves the wiring by hanging its own route off this object, which is
the check that survives a module with no routes — and the one that keeps working the day
this file's own routes are the thing being moved.

The layout those routes land in, and which issue owns each of them, is
``docs/resource_requests.md``.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.resource_requests.board import router as board_router
from app.api.resource_requests.evaluations import router as evaluations_router
from app.api.resource_requests.fund_assignment import router as fund_assignment_router
from app.api.resource_requests.funds import router as funds_router
from app.api.resource_requests.requests import router as requests_router

router = APIRouter()
router.include_router(requests_router)
router.include_router(evaluations_router)
router.include_router(funds_router)
router.include_router(fund_assignment_router)
router.include_router(board_router)
