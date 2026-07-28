"""The advisory single-editor lock.

Acquire and renew are one route: they are the same operation, and the client's
heartbeat calls it every 15s. Losing the lock is not an error here — the response
carries the current holder and the SPA opens the session in review mode off it.

Every route resolves the session before touching the lease, so the holder's name
(which falls back to their email) is only ever shown to somebody who can already
reach the project.
"""

from fastapi import APIRouter, status

from app.api.projects._deps import assert_project_access
from app.api.sound_necklace._deps import CurrentUser, Db
from app.models.sound_necklace import LockHolder, LockStatusResponse
from app.services import sound_necklace_service as sn_service
from app.services.sound_necklace.get_lock_status import LockState

router = APIRouter()


def _status(state: LockState) -> LockStatusResponse:
    if not state.held or state.user_id is None or state.expires_at is None:
        return LockStatusResponse(held=False)
    return LockStatusResponse(
        held=True,
        holder=LockHolder(user_id=state.user_id, display_name=state.display_name or ""),
        expires_at=state.expires_at.isoformat(),
    )


@router.put("/sessions/{session_id}/lock", response_model=LockStatusResponse)
async def acquire_lock(session_id: str, db: Db, user: CurrentUser) -> LockStatusResponse:
    """Acquire or renew the advisory editor lock."""
    session = await sn_service.get_session(db, session_id)
    await assert_project_access(db, user, session.project_id)
    return _status(await sn_service.acquire_lock(db, session, user))


@router.get("/sessions/{session_id}/lock", response_model=LockStatusResponse)
async def lock_status(session_id: str, db: Db, user: CurrentUser) -> LockStatusResponse:
    """Report the current lock holder and expiry."""
    session = await sn_service.get_session(db, session_id)
    await assert_project_access(db, user, session.project_id)
    return _status(await sn_service.get_lock_status(db, session_id))


@router.delete("/sessions/{session_id}/lock", status_code=status.HTTP_204_NO_CONTENT)
async def release_lock(session_id: str, db: Db, user: CurrentUser) -> None:
    """Release the advisory lock."""
    session = await sn_service.get_session(db, session_id)
    await assert_project_access(db, user, session.project_id)
    await sn_service.release_lock(db, session, user.id)
