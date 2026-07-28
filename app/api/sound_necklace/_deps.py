"""Shared dependencies for sound-necklace routers.

``CurrentUser`` requires any sound-necklace role (or platform admin), gating the
whole ``/api/sound-necklace`` surface via the shared per-app RBAC guard.
Role-specific guards (facilitator / project_admin) are added when a route needs
them.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access_control import require_app_access, require_role
from app.core.database import get_db
from app.db.models.auth import User
from app.models.sound_necklace import SessionLockChangedResponse, SessionLockedResponse
from app.services.sound_necklace.lock_fence import SessionLockedByOther

APP_KEY = "sound-necklace"

CurrentUser = Annotated[User, require_app_access(APP_KEY)]
# The auditor. Reading who reached whose voice is not part of doing the work, so it takes
# more than a facilitator's role — and project membership is still checked on top, or an
# admin of one project could read another's trail. require_role already returns a
# Depends(), so it goes straight into the Annotated.
ProjectAdmin = Annotated[User, require_role(APP_KEY, "project_admin")]
Db = Annotated[AsyncSession, Depends(get_db)]

LOCKED_RESPONSE: dict[int | str, dict[str, Any]] = {
    status.HTTP_409_CONFLICT: {
        "model": SessionLockedResponse | SessionLockChangedResponse,
        "description": (
            "Refused by the editor lock. `code` says which and what to do: SESSION_LOCKED "
            "means somebody else holds it — stop writing and open in review mode, off the "
            "holder_name and expires_at in the body. SESSION_LOCK_CHANGED means the lease "
            "refused the write and then lapsed, leaving nobody to name — just try again."
        ),
    }
}


def locked_body(exc: SessionLockedByOther) -> JSONResponse:
    """The SESSION_LOCKED 409, built by hand on every route that can raise it.

    The global ConflictError handler emits {detail, code} and constructs a fresh
    response, so the holder and expiry would not survive it.
    """
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content=SessionLockedResponse(
            detail=str(exc),
            holder_name=exc.holder_name,
            expires_at=exc.expires_at.isoformat(),
        ).model_dump(),
    )
