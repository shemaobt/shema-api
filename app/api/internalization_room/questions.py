"""The hand: a team's question, and the person who answers it.

Two audiences meet on this router. The team's app carries a device key and never signs in —
the room is operated by voice and has no keyboard. The facilitator is a person, signs in, and
comes through the platform's own app access. They never see each other's routes.
"""

from datetime import datetime
from hashlib import sha256

from fastapi import APIRouter, Depends, File, Response, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.internalization_room._deps import CurrentUser, device_dep, room_key_dep
from app.api.internalization_room.voice import IMMUTABLE
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
from app.services.internalization_room.voice_handles import (
    facilitator_audio_url,
    from_question_handle,
    team_audio_url,
)

router = APIRouter()

MAX_AUDIO_BYTES = 25 * 1024 * 1024


DeviceId = device_dep


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
                audio_url=team_audio_url(question.reply_audio_key or ""),
                pericope=question.pericope,
            )
            for question in waiting
        ]
    )


@router.get("/questions/audio/{handle}", dependencies=[room_key_dep])
async def team_audio(handle: str) -> Response:
    """Serve a facilitator's spoken reply to the app that asked.

    The room's voice route cannot carry these bytes: it only answers for keys under the
    room's synthesized speech, so every reply address it was handed came back a 404 and
    the answer never reached the team. This route reads the one folder a question writes.
    """
    return await _audio(handle)


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
                session_id=question.session_id,
                pericope=question.pericope,
                audio_url=facilitator_audio_url(question.audio_key),
                asked_at=_stamp(question.created_at),
            )
            for question in waiting
        ]
    )


@router.get("/facilitator/questions/audio/{handle}")
async def facilitator_audio(handle: str, user: CurrentUser) -> Response:
    """Serve a team's recorded question to the person deciding how to answer it.

    A facilitator signs in and holds no device key, so the same bytes need a route their
    own credential opens — the queue is unusable if the only thing in it cannot be heard.
    """
    return await _audio(handle)


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


async def _audio(handle: str) -> Response:
    """The bytes behind one question handle, for whichever audience asked.

    Both keys carry a digest of their own audio, so what a handle addresses can never
    change and either app may keep it for as long as it has room.
    """
    key = from_question_handle(handle)
    if key is None:
        raise NotFoundError("No such audio")
    audio = await service.fetch_audio(key)
    if audio is None:
        raise NotFoundError("No such audio")
    return Response(
        content=audio,
        media_type=service.AUDIO_MIME,
        headers={"Cache-Control": IMMUTABLE, "ETag": sha256(audio).hexdigest()[:32]},
    )


def _stamp(moment: datetime | None) -> str:
    return moment.isoformat() if moment else ""
