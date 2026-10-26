from fastapi import APIRouter, Depends, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.facilitator._deps import ReaderUser
from app.core.database import get_db
from app.models.internalization_room import SessionReRecordedSentences
from app.services import internalization_room as room
from app.services.internalization_room.re_recorded_sentences import (
    re_recorded_sentence_url,
    re_recorded_sentences_of,
)

router = APIRouter()


@router.get(
    "/facilitator/sessions/{session_id}/re-recorded-sentences",
    response_model=SessionReRecordedSentences,
)
async def read_the_re_recorded_sentences(
    session_id: str, user: ReaderUser, db: AsyncSession = Depends(get_db)
) -> SessionReRecordedSentences:
    session = await room.get_session_for_reader(db, user, session_id)
    return await re_recorded_sentences_of(db, session)


@router.get(
    "/facilitator/sessions/{session_id}/re-recorded-sentences/{sentence_id}/audio",
    status_code=status.HTTP_307_TEMPORARY_REDIRECT,
    response_class=RedirectResponse,
    response_model=None,
)
async def listen_to_the_re_recorded_sentence(
    session_id: str, sentence_id: str, user: ReaderUser, db: AsyncSession = Depends(get_db)
) -> RedirectResponse:
    session = await room.get_session_for_reader(db, user, session_id)
    url = await re_recorded_sentence_url(session, sentence_id)
    await db.commit()
    return RedirectResponse(url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)
