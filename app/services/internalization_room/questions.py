from __future__ import annotations

import base64
import binascii
import hashlib
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import ColumnElement, and_, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.exceptions import NotFoundError, ValidationError
from app.db.models.auth import User
from app.db.models.internalization_room import IRQuestion, IRQuestionStatus
from app.services.oral_collector.gcs_utils import generate_signed_download_url
from app.services.platform.storage import GcsPlatformStore
from app.services.platform.tts import SpeechStore
from app.services.project.facilitated_scope import (
    TEAM_NOT_FOUND,
    confined_to,
    facilitated_project_ids,
)
from app.services.project.facilitates_project import facilitates_project

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


#: §7's own number, and the one the Desk models against fixtures as ``RAISED_HANDS_PAGE_SIZE``.
DEFAULT_PAGE = 50

#: A page is a page. Without a ceiling the parameter is a way to ask for the installation in
#: one request, which is the behaviour this route was written to end.
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
