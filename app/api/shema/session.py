"""``GET /api/shema/session`` — who the caller is, in this product's own terms.

The one Shemá-specific session read (``docs/shema.md`` §6.3). Everything about *signing in*
is the platform's and is reused whole: ``POST /api/auth/login``, ``/refresh``, ``/logout``
and ``GET /api/auth/me`` are what INT-01 targets and this module adds no login of its own.
What it adds is the region, because ``GET /api/auth/my-roles`` cannot answer it — the grant
has no region column, which is the gap the whole of §6.1 exists to close.

The handler is three lines and issues no query, which is the layering rule read literally:
it declares the dependencies, calls one service and returns what it answers.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.shema._deps import APP_KEY, CurrentUser, Db
from app.models.shema_session import ShemaSession
from app.services.shema import get_session

router = APIRouter()


@router.get("/session", response_model=ShemaSession)
async def read_session(user: CurrentUser, db: Db) -> ShemaSession:
    """The signed-in persona: role, region scope and the name the org chart gives it.

    Guarded by ``CurrentUser`` and not by one of the four role aliases, which is the right
    shape rather than a looser one: every account that reaches this route holds *some* Shemá
    role — that is what ``require_app_access`` tested — and the answer to *which* is the
    response body. A role alias here would refuse three of the four personas the endpoint
    exists to describe.
    """
    return await get_session(db, user, APP_KEY)
