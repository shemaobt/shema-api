import asyncio
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.facilitator._deps import FacilitatorUser
from app.api.facilitator.teams import TEAM_NOT_FOUND
from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.services.internalization_room.nudge_channel import subscribe
from app.services.project.facilitates_project import facilitates_project

KEEP_ALIVE_SECONDS = 15.0

facilitator_nudges_router = APIRouter()


@facilitator_nudges_router.get("/{team_id}/nudges")
async def nudge_channel(
    team_id: str, user: FacilitatorUser, db: AsyncSession = Depends(get_db)
) -> StreamingResponse:
    if not await facilitates_project(db, user, team_id):
        raise NotFoundError(TEAM_NOT_FOUND)

    async def _nudges() -> AsyncIterator[bytes]:
        async with subscribe(team_id) as queue:
            while True:
                try:
                    what = await asyncio.wait_for(queue.get(), timeout=KEEP_ALIVE_SECONDS)
                except TimeoutError:
                    yield b": keep-alive\n\n"
                    continue
                yield f'event: nudge\ndata: {{"what":"{what}"}}\n\n'.encode()

    return StreamingResponse(
        _nudges(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
