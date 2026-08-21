from __future__ import annotations

import base64
import binascii
import hashlib
import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx
from sqlalchemy import ColumnElement, and_, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.exceptions import (
    NotFoundError,
    TranscriptionDefect,
    UpstreamServiceError,
    ValidationError,
)
from app.db.models.auth import User
from app.db.models.internalization_room import IRQuestion, IRQuestionStatus
from app.services.oral_collector.gcs_utils import generate_signed_download_url
from app.services.platform.audio_duration import measure_ms
from app.services.platform.storage import GcsPlatformStore
from app.services.platform.stt import SpeechToText, transcribe_speech
from app.services.platform.tts import SpeechStore
from app.services.project.facilitated_scope import (
    TEAM_NOT_FOUND,
    confined_to,
    facilitated_project_ids,
)
from app.services.project.facilitates_project import facilitates_project

logger = logging.getLogger(__name__)

AUDIO_MIME = "audio/mp4"

#: The room is run in Portuguese, the same default the rest of `services/internalization_room`
#: carries. A hint and not a detection request: letting the provider guess is how a
#: Portuguese question comes back as phonetic Spanish.
ROOM_LANGUAGE = "pt"


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
    element_key: str | None = None,
    store: SpeechStore | None = None,
    stt: SpeechToText | None = None,
) -> IRQuestion:
    """Keep what the team asked, so the knot on the necklace stands for something.

    The audio is stored before the row exists in any answerable state: a question the app
    confirmed but the server dropped is the one outcome this feature cannot have, because
    the team is told it was received and has no way to find out otherwise.

    **The question is committed before anything is transcribed**, and the two commits are
    two different promises. By the first the hand exists, is scoped to a team and is
    answerable; the second only adds what was said. So a provider outage, a timeout or a
    process that dies mid-transcription costs the transcript and never the question — which
    is the acceptance criterion, and is not something a single commit around a network call
    can offer.

    ``element_key`` is whichever bead the app says the hand went up on, and ``None`` is a
    normal answer: no row written before ENG-447 has one and no app sends one until ENG-456.
    ``duration_ms`` is measured here, from the bytes, and there is deliberately no parameter
    to hand it in with.
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
        element_key=element_key,
        audio_key=key,
        duration_ms=await measure_ms(audio),
        status=IRQuestionStatus.OPEN,
    )
    db.add(question)
    await db.commit()
    await db.refresh(question)

    await _transcribe_for_the_desk(db, question, audio, stt)
    return question


async def _transcribe_for_the_desk(
    db: AsyncSession, question: IRQuestion, audio: bytes, stt: SpeechToText | None
) -> None:
    """Read the question back in text, for the facilitator's eyes only.

    The boundary is here: the provider is another company's machine, and the three ways it
    fails a caller — an outage, a refused request, a connection that never opens — all mean
    the same thing to a raised hand. The card appears with audio and no transcript, and the
    facilitator answers it by listening, which is what they did before this column existed.

    **``ValidationError`` is in that tuple deliberately, and it is not hiding a defect of
    ours behind "the audio was bad".** Four places can raise it on this path, and none of
    them is a mistake in this repository: an empty payload, which `raise_question` refuses
    several lines above and a test holds; an empty language, which cannot happen because
    `ROOM_LANGUAGE` is a constant; a missing provider key, which is a machine without the
    tool, the same situation as a missing ffprobe and answered the same way; and a 4xx from
    the provider, which is the provider refusing this clip. A bug of ours reaches the
    `except` below instead.

    The mime type is the one the clip was stored under rather than the one the app declared,
    which is the same string today for every question (ENG-526).
    """
    try:
        said = await (stt or transcribe_speech)(audio, language=ROOM_LANGUAGE, mime_type=AUDIO_MIME)
    except (UpstreamServiceError, ValidationError, httpx.HTTPError):
        logger.warning("question %s could not be transcribed", question.id, exc_info=True)
        return
    except Exception as defect:
        logger.exception("question %s hit a defect on our side while transcribing", question.id)
        raise TranscriptionDefect(question_id=question.id, status=str(question.status)) from defect

    question.transcript = said or None
    await db.commit()
    await db.refresh(question)


async def get_question(db: AsyncSession, question_id: str) -> IRQuestion:
    result = await db.execute(select(IRQuestion).where(IRQuestion.id == question_id))
    question = result.scalar_one_or_none()
    if question is None:
        raise NotFoundError(f"Question {question_id} not found")
    return question


#: §7's own number, and the one the Desk models against fixtures as ``RAISED_HANDS_PAGE_SIZE``.
DEFAULT_PAGE = 50

#: The ceiling on ``limit``, and **this number does not come from ENG-452** — the issue never
#: mentions a page size. It is a decision made here and it should be contestable as one.
#:
#: Two arguments hold it up. Without a ceiling the parameter is a way to ask for the whole
#: installation in one request, which is the behaviour this route was written to end. And the
#: issue forbids a *silent* cut, not a cut: a hundred with ``open_total`` beside it is a
#: different thing from fifty said nothing about, because the reader can tell what was left
#: out. Take the total away and no ceiling is defensible, this one included.
#:
#: The number is arguable. That there is one is not.
MAX_PAGE = 100

#: Open first, then settled. Spelled as a rank rather than as a sort on the enum because the
#: enum's own order is its declaration order, which no reader of a query would think to check.
_QUEUE_FIRST: ColumnElement[int] = case((IRQuestion.status == IRQuestionStatus.OPEN, 0), else_=1)

#: The record: the answered and the resolved together. RF-04 gives those two no order
#: between them, so neither does this — the record reads by recency alone.
_IN_THE_RECORD = IRQuestion.status != IRQuestionStatus.OPEN


@dataclass(frozen=True)
class _Place:
    """Where the previous page stopped: the three columns the order is made of."""

    settled: bool
    at: datetime
    question_id: str


@dataclass(frozen=True)
class InboxPage:
    """A page of the inbox, the count it was cut out of, and where to resume.

    ``open_total`` counts the open hands **in the scope asked about**, not the ones on this
    page and not the ones the ``status`` filter let through. A total larger than the page is
    the correct answer and the whole reason it travels: a consumer that counts what arrived
    reads a smaller number than the team list it opened from, with neither screen looking
    wrong, and the smaller number is the one that gets believed.
    """

    questions: list[IRQuestion]
    open_total: int
    next_cursor: str | None


def _encode(place: _Place) -> str:
    raw = f"{int(place.settled)}|{place.at.isoformat()}|{place.question_id}".encode()
    return base64.urlsafe_b64encode(raw).decode()


def _decode(cursor: str) -> _Place:
    """Read a cursor, or refuse.

    Refused rather than answered with the first page: a cursor the route quietly ignores
    hands the caller page one while they believe they are on page four, and the loop that
    was paging never ends.
    """
    try:
        settled, at, question_id = base64.urlsafe_b64decode(cursor.encode()).decode().split("|", 2)
        return _Place(
            settled=bool(int(settled)),
            at=datetime.fromisoformat(at),
            question_id=question_id,
        )
    except (ValueError, binascii.Error, UnicodeDecodeError) as broken:
        raise ValidationError("This cursor cannot be read") from broken


def _after(place: _Place) -> ColumnElement[bool]:
    """Everything the order puts after that place — the same three columns, in the same order.

    Keyset and not ``OFFSET``, because a question arrives **open, at the top**: every offset
    into the list moves by one, and the next page re-serves a card the facilitator has read
    while dropping one they never saw. Neither looks wrong on screen.

    Written over ``status`` rather than over the rank the ORDER BY uses, because the rank has
    only two values and naming them is what the reader needs: the record, or above it.
    """
    same_group = _IN_THE_RECORD if place.settled else ~_IN_THE_RECORD
    below_it = [] if place.settled else [_IN_THE_RECORD]
    return or_(
        *below_it,
        and_(same_group, IRQuestion.created_at < place.at),
        and_(
            same_group,
            IRQuestion.created_at == place.at,
            IRQuestion.id < place.question_id,
        ),
    )


async def inbox_page(
    db: AsyncSession,
    user: User,
    *,
    team_id: str | None = None,
    wanted: IRQuestionStatus | None = None,
    limit: int = DEFAULT_PAGE,
    cursor: str | None = None,
) -> InboxPage:
    """The facilitator's inbox: their teams' questions, in RF-04's order, beside the count.

    **The scope holds with or without ``team_id``.** Without it the page is the caller's
    teams; with a team they do not facilitate the request is refused. The parameter narrows
    what they already reach and never widens it — the route answered the whole installation
    before this, and a facilitator read hands that were never addressed to them.

    **The order is served.** Open first, and the newest of those first; the answered and the
    resolved settle below as the record, by recency alone. It is applied before the page is
    cut, which is the reason it cannot be the client's: the order is what decides which
    questions fit in the answer, so a page cut first and arranged afterwards is an arbitrary
    sample the reader has no way of recognising as one.

    A question with no ``project_id`` belongs to no team and reaches nobody, which is the
    common case today — the room's app does not send its device credential yet. It errs low,
    and low is the honest direction: there is nothing to attribute the row to.
    """
    if team_id is not None:
        if not await facilitates_project(db, user, team_id):
            raise NotFoundError(TEAM_NOT_FOUND)
        restriction = IRQuestion.project_id == team_id
    else:
        restriction = confined_to(IRQuestion.project_id, await facilitated_project_ids(db, user))

    page = select(IRQuestion).where(restriction)
    if wanted is not None:
        page = page.where(IRQuestion.status == wanted)
    if cursor is not None:
        page = page.where(_after(_decode(cursor)))

    found = list(
        (
            await db.execute(
                page.order_by(
                    _QUEUE_FIRST.asc(), IRQuestion.created_at.desc(), IRQuestion.id.desc()
                ).limit(limit + 1)
            )
        ).scalars()
    )
    more = len(found) > limit
    questions = found[:limit]

    open_total = (
        await db.execute(
            select(func.count())
            .select_from(IRQuestion)
            .where(restriction, IRQuestion.status == IRQuestionStatus.OPEN)
        )
    ).scalar_one()

    return InboxPage(
        questions=questions,
        open_total=open_total,
        next_cursor=_encode(_place_of(questions[-1])) if more and questions else None,
    )


def _place_of(question: IRQuestion) -> _Place:
    return _Place(
        settled=question.status is not IRQuestionStatus.OPEN,
        at=question.created_at,
        question_id=question.id,
    )


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
