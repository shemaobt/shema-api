"""``GET /api/shema/session`` — who the caller is, in this product's own terms.

The one Shemá-specific session read (``docs/shema.md`` §6.3). Everything about *signing in*
is the platform's and is reused whole: ``POST /api/auth/login``, ``/refresh``, ``/logout``
and ``GET /api/auth/me`` are what INT-01 targets and this module adds no login of its own.
What it adds is the region, because ``GET /api/auth/my-roles`` cannot answer it — the grant
has no region column, which is the gap the whole of §6.1 exists to close — and, since
OBT-523, the roles an account holds across the two apps the PME serves.

The handler is three lines and issues no query, which is the layering rule read literally:
it declares the dependencies, calls one service and returns what it answers.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.shema._deps import Db, DoorUser, SessionRoles
from app.models.shema_session import ShemaSession
from app.services.shema import get_session

router = APIRouter()


@router.get("/session", response_model=ShemaSession)
async def read_session(user: DoorUser, db: Db, roles: SessionRoles) -> ShemaSession:
    """The signed-in persona: roles, region scope and the name the org chart gives it.

    Guarded by the PME's door and not by the Shemá app gate (``docs/shema.md`` §6.8): the
    mesa and the Gestor hold no Shemá role and sign in to the console anyway, and the answer
    to *which roles* is the response body. ``roles`` is the value the door admitted the caller
    on — FastAPI solves it once per request — so the body cannot name a role the door did not
    count.
    """
    return await get_session(db, user, roles=roles)
