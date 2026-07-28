"""Transcription drafts for the recorded answers (ENG-325).

Two routes: one that starts the job and one the SPA polls. Both answer the same body, so
the trigger's reply is already the first frame of progress.

The work is async because it is slow and because the provider key must stay server-side.
The POST only puts an event on the queue: the pass itself runs in Inngest
(`app/inngest/sn_transcription.py`), off this process, so a deploy mid-session does not
strand it. It is triggered when the report opens rather than when an answer is uploaded: a
take that gets re-recorded first is then never paid for.
"""

from fastapi import APIRouter, status

from app.api.projects._deps import assert_project_access
from app.api.sound_necklace._deps import CurrentUser, Db
from app.models.sound_necklace import (
    AnswerTranscript,
    TranscriptionProgressResponse,
    TranscriptionRequest,
)
from app.services import sound_necklace_service as sn_service
from app.services.sound_necklace.transcribe_answers import TranscriptionProgress

router = APIRouter()


def _body(progress: TranscriptionProgress) -> TranscriptionProgressResponse:
    return TranscriptionProgressResponse(
        total=progress.total,
        ready=progress.ready,
        failed=progress.failed,
        pending=progress.pending,
        answers=[
            AnswerTranscript(
                path=draft.resource_path,
                status=draft.status,
                transcript_source=draft.transcript_source,
                translation_en=draft.translation_en,
                error=draft.error,
            )
            for draft in progress.answers
        ],
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
        db, session_id, language=payload.language, force=payload.force
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
