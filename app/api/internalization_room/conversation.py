from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.facilitator._deps import ReaderUser
from app.core.database import get_db
from app.models.internalization_room import (
    ConversationResponse,
    QuestionAudioResponse,
    SessionBoundaryTurnsResponse,
    SessionCoverageResponse,
    SessionTurnsResponse,
)
from app.services import internalization_room as room
from app.services.internalization_room.conversation import conversation_of
from app.services.internalization_room.session_coverage import coverage_of
from app.services.internalization_room.session_turns import (
    boundary_turns_of,
    turn_clip_url,
    turns_of,
)

router = APIRouter()


@router.get(
    "/facilitator/sessions/{session_id}/conversation",
    response_model=ConversationResponse,
)
async def read_the_conversation(
    session_id: str, user: ReaderUser, db: AsyncSession = Depends(get_db)
) -> ConversationResponse:
    session = await room.get_session_for_reader(db, user, session_id)
    return conversation_of(session)


@router.get(
    "/facilitator/sessions/{session_id}/turns",
    response_model=SessionTurnsResponse,
)
async def read_the_turns(
    session_id: str, user: ReaderUser, db: AsyncSession = Depends(get_db)
) -> SessionTurnsResponse:
    session = await room.get_session_for_reader(db, user, session_id)
    return turns_of(session)


@router.get(
    "/facilitator/sessions/{session_id}/coverage",
    response_model=SessionCoverageResponse,
)
async def read_the_coverage(
    session_id: str, user: ReaderUser, db: AsyncSession = Depends(get_db)
) -> SessionCoverageResponse:
    session = await room.get_session_for_reader(db, user, session_id)
    return coverage_of(session)


@router.get(
    "/facilitator/sessions/{session_id}/boundary-turns",
    response_model=SessionBoundaryTurnsResponse,
)
async def read_the_boundary_turns(
    session_id: str, user: ReaderUser, db: AsyncSession = Depends(get_db)
) -> SessionBoundaryTurnsResponse:
    session = await room.get_session_for_reader(db, user, session_id)
    return boundary_turns_of(session)


@router.get(
    "/facilitator/sessions/{session_id}/turns/{number}/audio",
    response_model=QuestionAudioResponse,
)
async def listen_to_turn(
    session_id: str, number: int, user: ReaderUser, db: AsyncSession = Depends(get_db)
) -> QuestionAudioResponse:
    """A short-lived signed address of the turn's clip and when it dies, as the question's door.

    The database is let go before the clip is looked up, because a missing clip is voiced on
    the way.
    """
    session = await room.get_session_for_reader(db, user, session_id)
    await db.commit()
    signed = await turn_clip_url(session, number)
    return QuestionAudioResponse(url=signed.url, expires_at=signed.expires_at.isoformat())
