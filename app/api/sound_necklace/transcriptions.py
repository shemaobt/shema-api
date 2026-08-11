"""Transcription drafts for the recorded answers (ENG-325), and their confirmation
(ENG-394).

One route starts the job and one the SPA polls; both answer the same body, so the
trigger's reply is already the first frame of progress. The third takes the draft back
once a human has corrected it.

The work is async because it is slow and because the provider key must stay server-side.
The POST only puts an event on the queue: the pass itself runs in Inngest
(`app/inngest/sn_transcription.py`), off this process, so a deploy mid-session does not
strand it. It is triggered when the report opens rather than when an answer is uploaded: a
take that gets re-recorded first is then never paid for.

The confirm is synchronous instead, because it is one answer's worth of work and the
facilitator is waiting on the result they just typed.
"""

from typing import Any

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from app.api.projects._deps import assert_project_access
from app.api.sound_necklace._deps import CurrentUser, Db, locked_body
from app.db.models.sound_necklace import SnAnswerTranscript
from app.models.sound_necklace import (
    AnswerTranscript,
    SessionLockChangedResponse,
    SessionLockedResponse,
    TranscriptConfirmConflictResponse,
    TranscriptConfirmRequest,
    TranscriptionProgressResponse,
    TranscriptionRequest,
)
from app.services import sound_necklace_service as sn_service
from app.services.sound_necklace.transcribe_answers import TranscriptionProgress

router = APIRouter()

# Three ways to lose a confirm, and the client has to tell them apart: the shared
# LOCKED_RESPONSE is not reused here because its 409 admits only the two lock codes, and a
# generation conflict typed as one of those would be retried on the spot — forever, with
# the same stale generation, since retrying is exactly what SESSION_LOCK_CHANGED asks for.
CONFIRM_RESPONSES: dict[int | str, dict[str, Any]] = {
    status.HTTP_409_CONFLICT: {
        "model": (
            SessionLockedResponse | SessionLockChangedResponse | TranscriptConfirmConflictResponse
        ),
        "description": (
            "Refused, and `code` says by what. SESSION_LOCKED means somebody else is "
            "editing the session — stop writing and open in review mode, off the "
            "holder_name and expires_at in the body. SESSION_LOCK_CHANGED means the lease "
            "refused the write and then lapsed, leaving nobody to name: just try again. "
            "CONFLICT means the draft was rewritten under you, and only re-reading it "
            "helps — a retry sends the same superseded generation and loses again."
        ),
    }
}


def _answer(draft: SnAnswerTranscript) -> AnswerTranscript:
    return AnswerTranscript(
        path=draft.resource_path,
        status=draft.status,
        transcript_source=draft.transcript_source,
        translation_en=draft.translation_en,
        error=draft.error,
        generation=draft.generation,
    )


def _body(progress: TranscriptionProgress) -> TranscriptionProgressResponse:
    return TranscriptionProgressResponse(
        total=progress.total,
        ready=progress.ready,
        failed=progress.failed,
        pending=progress.pending,
        answers=[_answer(draft) for draft in progress.answers],
    )


@router.post(
    "/sessions/{session_id}/transcriptions",
    response_model=TranscriptionProgressResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_transcriptions(
    session_id: str,
    payload: TranscriptionRequest,
    db: Db,
    user: CurrentUser,
) -> TranscriptionProgressResponse:
    """Queue the drafts and answer 202 with the progress as it stands.

    Idempotent: a draft already made is not made again, so a reloaded report costs
    nothing. ``force`` is the re-record case and redoes everything.
    """
    session = await sn_service.get_session(db, session_id)
    await assert_project_access(db, user, session.project_id)

    progress = await sn_service.start_transcription(
        db, session_id, language=payload.language, force=payload.force, paths=payload.paths
    )
    if progress.pending:
        await sn_service.request_transcription(session_id)
    return _body(progress)


@router.get("/sessions/{session_id}/transcriptions", response_model=TranscriptionProgressResponse)
async def get_transcriptions(
    session_id: str, db: Db, user: CurrentUser
) -> TranscriptionProgressResponse:
    """Poll the job: how many are done, how many failed, and each answer's draft.

    A failed answer reports its own reason here — the job itself has no failure state,
    because one dead answer must never hold the report shut.
    """
    session = await sn_service.get_session(db, session_id)
    await assert_project_access(db, user, session.project_id)

    return _body(await sn_service.transcription_progress(db, session_id))


@router.put(
    "/sessions/{session_id}/transcriptions/{resource_path:path}",
    response_model=AnswerTranscript,
    responses=CONFIRM_RESPONSES,
)
async def confirm_transcription(
    session_id: str,
    resource_path: str,
    payload: TranscriptConfirmRequest,
    db: Db,
    user: CurrentUser,
) -> AnswerTranscript | JSONResponse:
    """Store the transcript a human corrected, and the English re-derived from it.

    The route exists because the report reads `translation_en`: an edit the SPA applied on
    its own would leave the report carrying the English of the sentence it replaced. So the
    body says only what was spoken, and the English is never the client's to send.

    Idempotent — confirming the text already stored costs nothing and changes nothing,
    which is what a facilitator re-confirming an answer they did not edit is doing.
    """
    session = await sn_service.get_session(db, session_id)
    await assert_project_access(db, user, session.project_id)

    try:
        draft = await sn_service.retranslate_answer(
            db,
            session_id,
            resource_path,
            transcript_source=payload.transcript_source,
            expected_generation=payload.generation,
            actor_user_id=user.id,
        )
    except sn_service.SessionLockedByOther as exc:
        return locked_body(exc)
    return _answer(draft)
