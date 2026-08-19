from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.internalization_room._deps import CurrentUser
from app.core.database import get_db
from app.services import internalization_room as room
from app.services.internalization_room.release import build_internalization_release

router = APIRouter()


@router.get("/facilitator/sessions/{session_id}/release")
async def internalization_release(
    session_id: str, user: CurrentUser, db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """The Refine handoff artifact for one finished session, built fail-closed.

    A facilitator route on purpose: the release is the seam between apps, read by the
    person carrying the work into Refine, never by the tablet in front of the team. A
    session that is not ready answers 409 with the blockers named — a partial artifact
    would look downstream exactly like a finished one.
    """
    session = await room.get_session(db, session_id)
    return await build_internalization_release(db, session)
