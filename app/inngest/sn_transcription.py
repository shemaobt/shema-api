"""The batch transcription of a session's voice answers (ENG-325).

DORMANT since the 2026-09-01 scope cut — kept deliberately, not by neglect.

The Colar's SPA now ends at the scene and phrase segmentation: no interview, no report, no
artifact. Nothing has called this function since. This is not dead code and not an oversight — the
function stays registered with Inngest and still runs when its event arrives, and the module
belongs to the interview package the system that hosts the interview next will pick up whole. Read
``docs/sound_necklace_interview_package.md`` before changing or removing anything here.

Off the API process, so a deploy in the middle of a long session does not strand the run,
and a retry is Inngest's job rather than the facilitator's.

`concurrency` keyed by session is what makes it safe to trigger twice: one run per session
at a time, across every instance. Without it, two runs would read the same `pending` rows
and pay the provider twice for the same answer.

There is no `on_failure` hook: a failure that reaches this level is infrastructure, the
database or the bucket, and never one answer's. Per-answer failures are already recorded as
`failed` rows by the pass itself, and a retry simply re-reads whatever is still `pending`.
"""

import inngest

from app.core.database import AsyncSessionLocal
from app.core.enums import SnTranscriptionEvent
from app.core.inngest_client import inngest_client
from app.inngest.schemas import TranscriptionRequestedPayload
from app.services.sound_necklace.transcribe_answers import run_pending


@inngest_client.create_function(
    fn_id="transcribe-session-answers",
    trigger=inngest.TriggerEvent(event=SnTranscriptionEvent.REQUESTED),
    concurrency=[inngest.Concurrency(key="event.data.session_id", limit=1)],
    retries=3,
)
async def transcribe_session_answers_fn(ctx: inngest.Context, step: inngest.Step) -> str:
    """Run the pending pass for one session, on a session of its own.

    The database session is opened here because this runs long after the request that
    asked for it is gone.
    """
    payload = TranscriptionRequestedPayload.model_validate(ctx.event.data)

    async def _transcribe() -> str:
        async with AsyncSessionLocal() as db:
            await run_pending(db, payload.session_id)
        return payload.session_id

    result: str = await step.run("transcribe-pending", _transcribe)
    return result
