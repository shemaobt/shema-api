import inngest

from app.core.database import AsyncSessionLocal
from app.core.enums import (
    OCNotificationEvent,
    OCRecordingEvent,
    UploadStatus,
)
from app.core.inngest_client import inngest_client
from app.inngest.helpers import notify_user
from app.inngest.schemas import UploadConfirmedPayload
from app.services.oral_collector.recording_service import (
    fail_stalled_uploads,
    mark_upload_verified,
    purge_failed_uploads,
)


@inngest_client.create_function(
    fn_id="process-upload",
    trigger=inngest.TriggerEvent(event=OCRecordingEvent.UPLOAD_CONFIRMED),
    retries=3,
)
async def process_upload_fn(ctx: inngest.Context, step: inngest.Step) -> str:
    """Mark a recording confirm-upload checked and published as verified, and notify.

    A recording the job cannot mark verified keeps its status, and its owner is told to keep
    the local recording, since only `verified` lets the phone free it.
    """
    payload = UploadConfirmedPayload.model_validate(ctx.event.data)

    async def _finalize_verified() -> str | None:
        async with AsyncSessionLocal() as db:
            return await mark_upload_verified(
                db,
                payload.recording_id,
                md5_hash=payload.expected_md5_hash,
                crc32c=payload.expected_crc32c,
            )

    status = await step.run("mark-verified", _finalize_verified)

    async def _notify_refused() -> None:
        if payload.user_id is None:
            return
        await notify_user(
            payload.user_id,
            OCNotificationEvent.UPLOAD_FAILED,
            "Upload failed — keep local recording",
            "The uploaded audio did not match the recording. "
            "Please keep the local recording and retry the upload.",
        )

    if status is None:
        return str(status)
    if status != UploadStatus.VERIFIED:
        await step.run("notify-upload-refused", _notify_refused)
        return str(status)

    async def _notify() -> None:
        if payload.user_id is None:
            return
        await notify_user(
            payload.user_id,
            OCNotificationEvent.UPLOAD_VERIFIED,
            "Recording uploaded — safe to free device storage",
            "Upload verified. You can safely delete the local recording.",
        )

    await step.run("notify-upload-complete", _notify)

    return UploadStatus.VERIFIED


STALLED_UPLOAD_SWEEP_CRON = "0 4 * * *"


@inngest_client.create_function(
    fn_id="fail-stalled-uploads",
    trigger=inngest.TriggerCron(cron=STALLED_UPLOAD_SWEEP_CRON),
)
async def fail_stalled_uploads_fn(ctx: inngest.Context, step: inngest.Step) -> int:
    """Sweep uploads abandoned mid-transfer into `UPLOAD_FAILED` once a day.

    Inngest is the only scheduler this service has and it already serves these functions, so
    a cron trigger buys the schedule without adding infrastructure to run and watch. Daily is
    fine for a deadline measured in weeks, and the pass is idempotent — a run that finds
    nothing writes nothing.
    """

    async def _sweep() -> int:
        async with AsyncSessionLocal() as db:
            return await fail_stalled_uploads(db)

    return await step.run("fail-stalled-uploads", _sweep)


FAILED_UPLOAD_PURGE_CRON = "30 4 * * *"


@inngest_client.create_function(
    fn_id="purge-failed-uploads",
    trigger=inngest.TriggerCron(cron=FAILED_UPLOAD_PURGE_CRON),
)
async def purge_failed_uploads_fn(ctx: inngest.Context, step: inngest.Step) -> int:
    """Drain the `UPLOAD_FAILED` rows the sweep above leaves behind, once a day.

    Half an hour after the sweep, so a row the sweep just failed is read by a purge that has
    already seen it aged, rather than by one racing the same transaction. Daily suits a
    retention measured in months, and the pass is idempotent — a run that finds nothing writes
    nothing and touches no bucket.

    One run is bounded (`FAILED_UPLOAD_PURGE_BATCH`), so a backlog larger than a batch drains
    over consecutive days rather than in the first run. That is the point: it keeps a single
    run inside the request timeout this function is executed in.
    """

    async def _purge() -> int:
        async with AsyncSessionLocal() as db:
            return await purge_failed_uploads(db)

    return await step.run("purge-failed-uploads", _purge)
