"""The hand: a team's question, and the person who answers it.

Two audiences meet on this router. The team's app carries a device key and never signs in —
the room is operated by voice and has no keyboard. The facilitator is a person, signs in, and
comes through the platform's own app access. They never see each other's routes.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.facilitator._deps import FacilitatorUser
from app.api.internalization_room._deps import device_dep, room_key_dep
from app.core.database import get_db
from app.core.exceptions import NotFoundError, ValidationError
from app.db.models.internalization_room import IRQuestion, IRQuestionStatus
from app.models.internalization_room import (
    HandRepliesResponse,
    HandReplyView,
    InboxQuestionView,
    QuestionInboxResponse,
    QuestionRaisedResponse,
)
from app.services.internalization_room import questions as service
from app.services.internalization_room import sessions as session_service
from app.services.internalization_room.voice_handles import audio_url

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
        project_id=session.project_id,
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


@router.get("/facilitator/questions", response_model=QuestionInboxResponse)
async def question_inbox(
    user: FacilitatorUser,
    team_id: str | None = Query(default=None),
    status_wanted: IRQuestionStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=service.DEFAULT_PAGE, ge=1, le=service.MAX_PAGE),
    cursor: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> QuestionInboxResponse:
    """The inbox, scoped to the caller's teams whether or not ``team_id`` narrows it.

    Both the order and the count are the route's rather than the reader's, for the same
    reason: the page is a cut of something larger, so what the cut kept and how much it left
    out are only knowable here.
    """
    page = await service.inbox_page(
        db, user, team_id=team_id, wanted=status_wanted, limit=limit, cursor=cursor
    )
    return QuestionInboxResponse(
        questions=[
            InboxQuestionView(
                question_id=question.id,
                team_id=_team_of(question),
                device_id=question.device_id,
                pericope=question.pericope,
                status=str(question.status),
                heard_at=_moment(question.heard_at),
                audio_url=f"/api/internalization-room/facilitator/questions/{question.id}/audio",
                asked_at=_stamp(question.created_at),
            )
            for question in page.questions
        ],
        open_total=page.open_total,
        next_cursor=page.next_cursor,
    )


@router.get(
    "/facilitator/questions/{question_id}/audio",
    status_code=status.HTTP_307_TEMPORARY_REDIRECT,
    response_class=RedirectResponse,
    response_model=None,
)
async def listen_to_question(
    question_id: str, user: FacilitatorUser, db: AsyncSession = Depends(get_db)
) -> RedirectResponse:
    """Redirect to a short-lived signed URL, the way the takes routes already do.

    The queue used to hand the facilitator the clip route, which is gated on the room key
    the tablet carries. They sign in as a person: every play button answered 401.
    """
    question = await service.get_question(db, question_id)
    if not question.audio_key:
        raise NotFoundError("No such recording")
    return RedirectResponse(
        await service.listen_url(question.audio_key),
        status_code=status.HTTP_307_TEMPORARY_REDIRECT,
    )


@router.post("/facilitator/questions/{question_id}/reply")
async def reply(
    question_id: str,
    user: FacilitatorUser,
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
    question_id: str, user: FacilitatorUser, db: AsyncSession = Depends(get_db)
) -> dict[str, str]:
    question = await service.get_question(db, question_id)
    await service.resolve_elsewhere(db, question, answered_by=user.id)
    return {"status": "resolved"}


def _team_of(question: IRQuestion) -> str:
    """Whose question this is, which an answered card always knows.

    The column is nullable and the answer's field is not, because every shape of the inbox
    restriction drops a row that names no team. Asserted rather than branched on: there is no
    behaviour to write for the other case, and typing the field nullable to avoid saying so
    would hand the Desk a null it has to draw something for.
    """
    assert question.project_id is not None
    return question.project_id


def _stamp(moment: datetime | None) -> str:
    return moment.isoformat() if moment else ""


def _moment(when: datetime | None) -> str | None:
    """An instant that may genuinely be absent, kept absent.

    Distinct from ``_stamp``, which answers ``""`` for nothing — right for a column that is
    never null, and wrong for one that is: an empty string is a value the reader has to be
    taught to treat as missing, and null already is missing.
    """
    return when.isoformat() if when else None
