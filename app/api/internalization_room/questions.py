"""The hand: a team's question, and the person who answers it.

Two audiences meet on this router. The team's app carries a device key and never signs in —
the room is operated by voice and has no keyboard. The facilitator is a person, signs in, and
comes through the platform's own app access. They never see each other's routes.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, File, Header, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.internalization_room._deps import CurrentUser, room_key_dep
from app.core.database import get_db
from app.core.exceptions import NotFoundError, ValidationError
from app.models.internalization_room import (
    HandRepliesResponse,
    HandReplyView,
    OpenQuestionsResponse,
    OpenQuestionView,
    QuestionRaisedResponse,
)
from app.services.internalization_room import questions as service
from app.services.internalization_room import sessions as session_service
from app.services.internalization_room.voice_handles import audio_url

router = APIRouter()

MAX_AUDIO_BYTES = 25 * 1024 * 1024


async def _device(x_room_device: str | None = Header(default=None)) -> str:
    """Which tablet is asking.

    The room has no accounts, so a question is addressed to the device that raised it. The
    app mints this once and keeps it, which is what lets an answer find the team days later.
    """
    if not x_room_device:
        raise ValidationError("Missing X-Room-Device header")
    return x_room_device


DeviceId = Depends(_device)


@router.post("/questions", response_model=QuestionRaisedResponse, dependencies=[room_key_dep])
async def raise_question(
    session_id: str,
    device_id: str = DeviceId,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
) -> QuestionRaisedResponse:
    audio = await file.read()
    if len(audio) > MAX_AUDIO_BYTES:
        raise ValidationError("Audio payload exceeds 25 MB limit")
    session = await session_service.get_session(db, session_id)
    question = await service.raise_question(
        db,
        device_id=device_id,
        session_id=session.id,
        pericope=session.pericope,
        audio=audio,
    )
    return QuestionRaisedResponse(question_id=question.id, status=str(question.status))


@router.get("/questions/replies", response_model=HandRepliesResponse, dependencies=[room_key_dep])
async def replies(
    device_id: str = DeviceId, db: AsyncSession = Depends(get_db)
) -> HandRepliesResponse:
    waiting = await service.replies_for(db, device_id)
    return HandRepliesResponse(
        replies=[
            HandReplyView(
                question_id=question.id,
                audio_url=audio_url(question.reply_audio_key or ""),
                pericope=question.pericope,
            )
            for question in waiting
        ]
    )


@router.post("/questions/{question_id}/heard", dependencies=[room_key_dep])
async def heard(
    question_id: str, device_id: str = DeviceId, db: AsyncSession = Depends(get_db)
) -> dict[str, str]:
    question = await service.get_question(db, question_id)
    if question.device_id != device_id:
        raise NotFoundError(f"Question {question_id} not found")
    await service.mark_heard(db, question)
    return {"status": "heard"}


@router.get("/facilitator/questions", response_model=OpenQuestionsResponse)
async def open_questions(
    user: CurrentUser, db: AsyncSession = Depends(get_db)
) -> OpenQuestionsResponse:
    waiting = await service.open_questions(db)
    return OpenQuestionsResponse(
        questions=[
            OpenQuestionView(
                question_id=question.id,
                device_id=question.device_id,
                pericope=question.pericope,
                audio_url=audio_url(question.audio_key),
                asked_at=_stamp(question.created_at),
            )
            for question in waiting
        ]
    )


@router.post("/facilitator/questions/{question_id}/reply")
async def reply(
    question_id: str,
    user: CurrentUser,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    audio = await file.read()
    if len(audio) > MAX_AUDIO_BYTES:
        raise ValidationError("Audio payload exceeds 25 MB limit")
    question = await service.get_question(db, question_id)
    await service.answer_with_voice(db, question, audio=audio, answered_by=user.id)
    return {"status": "answered"}


@router.post("/facilitator/questions/{question_id}/resolve")
async def resolve(
    question_id: str, user: CurrentUser, db: AsyncSession = Depends(get_db)
) -> dict[str, str]:
    question = await service.get_question(db, question_id)
    await service.resolve_elsewhere(db, question, answered_by=user.id)
    return {"status": "resolved"}


def _stamp(moment: datetime | None) -> str:
    return moment.isoformat() if moment else ""
