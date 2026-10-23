"""The pins live sessions hold, saved by the operator as the file a prune is told (ADR 0088)."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.facilitator._deps import ReaderUser
from app.core.config import get_settings
from app.core.database import get_db
from app.models.internalization_room import CanonPinsResponse
from app.services.internalization_room.canon import kept
from app.services.internalization_room.canon_pins import live_canon_pins

router = APIRouter()


@router.get("/facilitator/canon-pins", response_model=CanonPinsResponse)
async def canon_pins(user: ReaderUser, db: AsyncSession = Depends(get_db)) -> CanonPinsResponse:
    """Every distinct canon pin of a session no Zerar archived, across every team, with the
    Cloud Run service that answered, the pin it serves, which the prune also keeps, and the
    moment it answered, past which the prune refuses the file.

    Not scoped to the reader's teams: the answer names commits of a public repository and is
    the same for every reader, and a partial answer would let the prune remove canon another
    team's live session reads.
    """
    return CanonPinsResponse(
        environment=get_settings().cloud_run_service,
        deployed_pin=kept.deployed_pin(),
        answered_at=datetime.now(UTC),
        pins=await live_canon_pins(db),
    )
