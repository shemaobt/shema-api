from fastapi import APIRouter, Depends, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.facilitator._deps import FacilitatorUser
from app.core.database import get_db
from app.models.internalization_room import ConversationResponse, SessionTurnsResponse
from app.services import internalization_room as room
from app.services.internalization_room.conversation import conversation_of
from app.services.internalization_room.session_turns import turn_clip_url, turns_of

router = APIRouter()


@router.get(
    "/facilitator/sessions/{session_id}/conversation",
    response_model=ConversationResponse,
)
async def read_the_conversation(
    session_id: str, user: FacilitatorUser, db: AsyncSession = Depends(get_db)
) -> ConversationResponse:
    session = await room.get_session_for_facilitator(db, user, session_id)
    return conversation_of(session)


@router.get(
    "/facilitator/sessions/{session_id}/turns",
    response_model=SessionTurnsResponse,
)
async def read_the_turns(
    session_id: str, user: FacilitatorUser, db: AsyncSession = Depends(get_db)
) -> SessionTurnsResponse:
    session = await room.get_session_for_facilitator(db, user, session_id)
    return turns_of(session)


@router.get(
    "/facilitator/sessions/{session_id}/turns/{number}/audio",
    status_code=status.HTTP_307_TEMPORARY_REDIRECT,
    response_class=RedirectResponse,
    response_model=None,
)
async def listen_to_turn(
    session_id: str, number: int, user: FacilitatorUser, db: AsyncSession = Depends(get_db)
) -> RedirectResponse:
    """Redirect to a short-lived signed URL of the turn's clip, as a take's audio door does.

    The database is let go before the clip is looked up, because a missing clip is voiced on
    the way.
    """
    session = await room.get_session_for_facilitator(db, user, session_id)
    await db.commit()
    return RedirectResponse(
        await turn_clip_url(session, number), status_code=status.HTTP_307_TEMPORARY_REDIRECT
    )
