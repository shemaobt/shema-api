"""The Desk's «Sessões»: every session of every team the reader may read (ENG-1192)."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.facilitator._deps import ReaderUser
from app.core.database import get_db
from app.models.internalization_room_desk_sessions import DeskSessionsPage
from app.services.internalization_room import desk_sessions

facilitator_sessions_router = APIRouter()


@facilitator_sessions_router.get("", response_model=DeskSessionsPage)
async def list_desk_sessions_route(
    user: ReaderUser,
    limit: int = Query(default=desk_sessions.DEFAULT_PAGE, ge=1, le=desk_sessions.MAX_PAGE),
    cursor: str | None = Query(default=None),
    team_id: str | None = Query(default=None),
    pericope: str | None = Query(default=None, min_length=1, max_length=120),
    db: AsyncSession = Depends(get_db),
) -> DeskSessionsPage:
    """List the readable sessions, newest activity first.

    ``team_id`` and ``pericope`` narrow the list, alone or together, for the Desk's passage
    picker (ENG-1229). A ``team_id`` the reader may not read answers 404 «Team not found».
    """
    return await desk_sessions.desk_sessions_page(
        db, user, limit=limit, cursor=cursor, team_id=team_id, pericope=pericope
    )
