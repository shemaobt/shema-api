"""The Desk's «Sessões»: every session of every team the reader may read (ENG-1192)."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.facilitator._deps import FacilitatorUser
from app.core.database import get_db
from app.models.internalization_room_desk_sessions import DeskSessionsPage
from app.services.internalization_room import desk_sessions

facilitator_sessions_router = APIRouter()


@facilitator_sessions_router.get("", response_model=DeskSessionsPage)
async def list_desk_sessions_route(
    user: FacilitatorUser,
    limit: int = Query(default=desk_sessions.DEFAULT_PAGE, ge=1, le=desk_sessions.MAX_PAGE),
    cursor: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> DeskSessionsPage:
    return await desk_sessions.desk_sessions_page(db, user, limit=limit, cursor=cursor)
