from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.exceptions import NotFoundError, ValidationError
from app.db.models.internalization_room import IRQuestion, IRQuestionStatus
from app.services.oral_collector.gcs_utils import generate_signed_download_url
from app.services.platform.storage import GcsPlatformStore
from app.services.platform.tts import SpeechStore

AUDIO_MIME = "audio/mp4"


def _store(settings: Settings | None = None) -> SpeechStore:
    return GcsPlatformStore(settings or get_settings())


def _key(kind: str, question_id: str, audio: bytes) -> str:
    digest = hashlib.sha256(audio).hexdigest()[:16]
    return f"internalization-room/questions/{question_id}/{kind}-{digest}.m4a"


async def raise_question(
    db: AsyncSession,
    *,
    device_id: str,
    session_id: str,
    pericope: str,
    audio: bytes,
    project_id: str | None = None,
    store: SpeechStore | None = None,
) -> IRQuestion:
    """Keep what the team asked, so the knot on the necklace stands for something.

    The audio is stored before the row exists in any answerable state: a question the app
    confirmed but the server dropped is the one outcome this feature cannot have, because
    the team is told it was received and has no way to find out otherwise.
    """
    if not audio:
        raise ValidationError("A question with no audio is not a question")
    question_id = str(uuid.uuid4())
    key = _key("pergunta", question_id, audio)
    await (store or _store()).put(key, audio, AUDIO_MIME)
    question = IRQuestion(
        id=question_id,
        project_id=project_id,
        device_id=device_id,
        session_id=session_id,
        pericope=pericope,
        audio_key=key,
        status=IRQuestionStatus.OPEN,
    )
    db.add(question)
    await db.commit()
    await db.refresh(question)
    return question


async def get_question(db: AsyncSession, question_id: str) -> IRQuestion:
    result = await db.execute(select(IRQuestion).where(IRQuestion.id == question_id))
    question = result.scalar_one_or_none()
    if question is None:
        raise NotFoundError(f"Question {question_id} not found")
    return question


async def open_questions(db: AsyncSession, *, limit: int = 50) -> list[IRQuestion]:
    """What is still waiting on a person, oldest first — a queue, not a feed."""
    result = await db.execute(
        select(IRQuestion)
        .where(IRQuestion.status == IRQuestionStatus.OPEN)
        .order_by(IRQuestion.created_at)
        .limit(limit)
    )
    return list(result.scalars())


async def answer_with_voice(
    db: AsyncSession,
    question: IRQuestion,
    *,
    audio: bytes,
    answered_by: str,
    store: SpeechStore | None = None,
) -> IRQuestion:
    if not audio:
        raise ValidationError("A reply with no audio is not a reply")
    key = _key("resposta", question.id, audio)
    await (store or _store()).put(key, audio, AUDIO_MIME)
    # A second reply supersedes the first, and the tablet only fetches what it has not
    # heard. Leaving `heard_at` set filtered the correction out forever: the facilitator
    # realises they were wrong, records the right answer, the API says "answered", and the
    # team keeps the wrong rendering with no way to learn otherwise.
    question.heard_at = None
    question.reply_audio_key = key
    question.status = IRQuestionStatus.ANSWERED
    question.answered_by = answered_by
    question.answered_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(question)
    return question


async def resolve_elsewhere(
    db: AsyncSession, question: IRQuestion, *, answered_by: str
) -> IRQuestion:
    """Closed because the facilitator will speak to the team directly.

    Distinct from answered on purpose: nothing will arrive in the app, so the team is never
    left waiting on a reply that was always going to happen face to face.

    A recording the team has not heard yet is not closed over. Resolving on top of it moved
    the row out of the reply filter and left the audio in the bucket, reachable by nothing —
    and the facilitator had no way to know a reply existed, because the queue does not show
    one.
    """
    if question.status is IRQuestionStatus.ANSWERED and question.heard_at is None:
        raise ValidationError("This question already has a spoken reply the team has not heard yet")
    question.status = IRQuestionStatus.RESOLVED
    question.answered_by = answered_by
    question.answered_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(question)
    return question


async def replies_for(db: AsyncSession, device_id: str) -> list[IRQuestion]:
    """Answers this device has not heard yet, from any session it ever held.

    A facilitator may answer hours later, when that passage is long closed. Scoping the
    reply to its session would drop it silently.
    """
    result = await db.execute(
        select(IRQuestion)
        .where(IRQuestion.device_id == device_id)
        .where(IRQuestion.status == IRQuestionStatus.ANSWERED)
        .where(IRQuestion.heard_at.is_(None))
        .order_by(IRQuestion.answered_at)
    )
    return list(result.scalars())


async def mark_heard(db: AsyncSession, question: IRQuestion) -> IRQuestion:
    question.heard_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(question)
    return question


async def fetch_audio(key: str, *, store: SpeechStore | None = None) -> bytes | None:
    return await (store or _store()).get(key)


LISTEN_MINUTES = 15


async def listen_url(key: str, *, settings: Settings | None = None) -> str:
    """A short-lived signed URL for a question or a reply.

    The only address these ever had was the clip route, which is gated on the room key —
    the tablet's credential. A facilitator signs in as a person and carries no room key,
    so every play button in their queue answered 401 and the hand was dead on their side
    as surely as it was on the team's. The takes routes already solve this by redirecting
    to storage rather than proxying; this is the same move.
    """
    cfg = settings or get_settings()
    if not cfg.gcs_platform_bucket:
        raise ValidationError("GCS_PLATFORM_BUCKET is not configured")
    return await generate_signed_download_url(
        cfg.gcs_platform_bucket,
        key,
        expiry_minutes=LISTEN_MINUTES,
        response_content_type=AUDIO_MIME,
    )
