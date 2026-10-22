"""The pins live sessions hold, saved by the operator as the file a prune is told (ADR 0088)."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.facilitator._deps import ReaderUser
from app.core.database import get_db
from app.models.internalization_room import CanonPinsResponse
from app.services.internalization_room.canon_pins import live_canon_pins

router = APIRouter()


@router.get("/facilitator/canon-pins", response_model=CanonPinsResponse)
async def canon_pins(user: ReaderUser, db: AsyncSession = Depends(get_db)) -> CanonPinsResponse:
    """Every distinct canon pin of a session no Zerar archived, across every team.

    Not scoped to the reader's teams: the answer names commits of a public repository and is
    the same for every reader, and a partial answer would let the prune remove canon another
    team's live session reads.
    """
    return CanonPinsResponse(pins=await live_canon_pins(db))
