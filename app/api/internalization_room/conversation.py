from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.facilitator._deps import FacilitatorUser
from app.core.database import get_db
from app.models.internalization_room import ConversationResponse
from app.services import internalization_room as room
from app.services.internalization_room.conversation import conversation_of

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
