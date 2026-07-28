"""Transcription + translation drafts for a session's voice answers (ENG-325).

One async pass per answer: transcribe in the language it was spoken, then, if that is not
English, translate. Both are drafts for a human to confirm — this module never touches an
artifact.

It runs when the SPA enters the Report, not on upload: a take that gets re-recorded before
the report is never paid for. The per-answer rows carry the whole state of the job, which
is what makes it idempotent (``ready`` is never redone), resumable (a lost worker leaves
``pending``) and partial-failure-proof (a bad answer is one ``failed`` row, never a 500).
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass

import inngest
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import SnTranscriptionEvent
from app.core.inngest_client import inngest_client
from app.db.models.sound_necklace import SnAnswerTranscript, SnVoiceAnswer, TranscriptStatus
from app.services.oral_collector import gcs_utils
from app.services.platform.stt import SpeechToText, transcribe_speech
from app.services.platform.translation import Translator, translate_to_english
from app.services.platform.voices import language_hint
from app.services.sound_necklace.constants import GCS_SN_BUCKET

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TranscriptionProgress:
    """What the polling endpoint answers with — counts plus the per-answer detail."""

    total: int
    ready: int
    failed: int
    pending: int
    answers: list[SnAnswerTranscript]


async def start_transcription(
    db: AsyncSession, session_id: str, *, language: str, force: bool = False
) -> TranscriptionProgress:
    """Queue the drafts that are missing, and return the progress right away.

    A ``ready`` draft is left alone — that is the idempotency, and it is what keeps a
    reloaded report from re-billing every answer. A ``failed`` one is queued again without
    ``force``: retrying a provider outage is the expected path, not an override.

    ``force`` is the re-record case: it throws the existing drafts away, because a draft
    of a take that no longer exists is worse than no draft at all. It is also the only
    thing that touches a draft already queued: a plain re-trigger leaves ``pending`` alone,
    so a pass in flight is not made to throw away an answer it has already paid for.

    Two queries, never one per answer: a session carries a draft for every question of
    every scene and every phrase, and this runs on the request the report is waiting for.

    Two triggers landing together both read before either commits, so the loser insert hits
    the primary key. Seeding a draft somebody else just seeded is this caller's goal already
    met, so the collision is answered with the state that won rather than with a 500.
    """
    answers = (
        (
            await db.execute(
                select(SnVoiceAnswer)
                .where(SnVoiceAnswer.session_id == session_id)
                .order_by(SnVoiceAnswer.resource_path)
            )
        )
        .scalars()
        .all()
    )

    existing = await _existing_drafts(db, session_id)

    for answer in answers:
        draft = existing.get(answer.resource_path)
        if draft is None:
            db.add(
                SnAnswerTranscript(
                    session_id=session_id, resource_path=answer.resource_path, language=language
                )
            )
            continue
        if draft.status != TranscriptStatus.FAILED and not force:
            continue

        draft.language = language
        draft.status = TranscriptStatus.PENDING
        draft.generation += 1
        draft.transcript_source = None
        draft.translation_en = None
        draft.error = None

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()

    return await transcription_progress(db, session_id)


async def _existing_drafts(db: AsyncSession, session_id: str) -> dict[str, SnAnswerTranscript]:
    """Every draft the session already has, by the answer it belongs to."""
    rows = await db.execute(
        select(SnAnswerTranscript).where(SnAnswerTranscript.session_id == session_id)
    )
    return {draft.resource_path: draft for draft in rows.scalars()}


async def transcription_progress(db: AsyncSession, session_id: str) -> TranscriptionProgress:
    """The state of every answer's draft, counted.

    ``total`` counts the DRAFTS, not the recordings: an answer recorded after the trigger
    has no draft yet and is not work this job was asked to do.
    """
    drafts = (
        (
            await db.execute(
                select(SnAnswerTranscript)
                .where(SnAnswerTranscript.session_id == session_id)
                .order_by(SnAnswerTranscript.resource_path)
            )
        )
        .scalars()
        .all()
    )
    by_status = [d.status for d in drafts]
    return TranscriptionProgress(
        total=len(drafts),
        ready=by_status.count(TranscriptStatus.READY),
        failed=by_status.count(TranscriptStatus.FAILED),
        pending=by_status.count(TranscriptStatus.PENDING),
        answers=list(drafts),
    )


async def run_pending(
    db: AsyncSession,
    session_id: str,
    *,
    stt: SpeechToText = transcribe_speech,
    translator: Translator = translate_to_english,
) -> None:
    """Fill in every pending draft of the session, one answer at a time.

    Sequential on purpose: one session, one row committed per answer, so progress is
    visible while it runs and a crash costs at most the answer in flight.

    ponytail: a 200-answer session takes 200 round trips end to end. If that becomes the
    complaint, fan out with one DB session per worker — not with a shared one, which is
    not concurrency-safe.
    """
    pending = (
        (
            await db.execute(
                select(SnAnswerTranscript, SnVoiceAnswer)
                .join(
                    SnVoiceAnswer,
                    (SnVoiceAnswer.session_id == SnAnswerTranscript.session_id)
                    & (SnVoiceAnswer.resource_path == SnAnswerTranscript.resource_path),
                )
                .where(
                    SnAnswerTranscript.session_id == session_id,
                    SnAnswerTranscript.status == TranscriptStatus.PENDING,
                )
                .order_by(SnAnswerTranscript.resource_path)
            )
        )
        .tuples()
        .all()
    )

    for draft, answer in pending:
        generation, path, language = draft.generation, draft.resource_path, draft.language
        try:
            audio = await gcs_utils.download_gcs_object(GCS_SN_BUCKET, answer.storage_key)
            transcript = await stt(audio, language=language, mime_type=answer.content_type)
            translation = (
                transcript
                if language_hint(language) == "en"
                else await translator(transcript, source_language=language)
            )
            values = {
                "status": TranscriptStatus.READY,
                "transcript_source": transcript,
                "translation_en": translation,
                "error": None,
            }
        except Exception as exc:
            logger.warning("transcription failed session=%s path=%s: %s", session_id, path, exc)
            values = {"status": TranscriptStatus.FAILED, "error": str(exc)}

        await _write_draft(db, session_id, path, generation=generation, values=values)


async def _write_draft(
    db: AsyncSession,
    session_id: str,
    resource_path: str,
    *,
    generation: int,
    values: Mapping[str, object],
) -> None:
    """Write a result only if the row is still the one the pass read.

    Compare-and-swap on ``generation``, the way the autosave does on ``version``. A
    ``force`` that lands while the pass is running has already replaced the recording and
    reset the row; writing this result over it would leave ``ready`` holding a draft of a
    take that no longer exists, and the run that ``force`` queued finds nothing pending to
    heal it. Losing the swap means the answer stays ``pending`` for that run — the work is
    lost, which is the cheap half of the trade.
    """
    written = await db.execute(
        update(SnAnswerTranscript)
        .where(
            SnAnswerTranscript.session_id == session_id,
            SnAnswerTranscript.resource_path == resource_path,
            SnAnswerTranscript.generation == generation,
        )
        .values(**values)
    )
    await db.commit()
    if not written.rowcount:
        logger.info(
            "transcription superseded session=%s path=%s generation=%s",
            session_id,
            resource_path,
            generation,
        )


async def request_transcription(session_id: str) -> None:
    """Hand the pass to the queue — the request does not wait for it or run it.

    The event carries the session and nothing else: the run reads whatever is `pending`
    when it starts, so a retry or a replay costs no provider call it has already made.
    """
    # Imported here, not at module scope: `app.inngest` registers the function that imports
    # this module, so a top-level import would close the loop. The queue is the outer layer
    # and knows the service; the service only needs the payload's shape, and only when it
    # sends.
    from app.inngest.schemas import TranscriptionRequestedPayload

    await inngest_client.send(
        inngest.Event(
            name=SnTranscriptionEvent.REQUESTED,
            data=TranscriptionRequestedPayload(session_id=session_id).model_dump(),
        )
    )
