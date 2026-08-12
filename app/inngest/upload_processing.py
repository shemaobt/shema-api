import asyncio
import base64
import logging
from datetime import UTC, datetime
from typing import Any

import inngest
from google.cloud import storage

from app.core.database import AsyncSessionLocal
from app.core.enums import (
    OCNotificationEvent,
    OCRecordingEvent,
    UploadStatus,
)
from app.core.inngest_client import inngest_client
from app.db.models.oc_recording import OC_Recording
from app.inngest.helpers import (
    extract_failure_context,
    notify_user,
    update_recording_fields,
)
from app.inngest.schemas import BlobVerificationResult, UploadConfirmedPayload
from app.services.oral_collector.constants import GCS_OC_BUCKET, GCS_OC_PROJECT
from app.services.oral_collector.gcs_utils import GCS_PUBLIC_BASE
from app.services.oral_collector.recording_service import (
    fail_stalled_uploads,
    purge_failed_uploads,
)

logger = logging.getLogger(__name__)


async def verify_gcs_blob(payload: UploadConfirmedPayload) -> BlobVerificationResult:
    def _blocking() -> BlobVerificationResult:
        client = storage.Client(project=GCS_OC_PROJECT)
        bucket = client.bucket(GCS_OC_BUCKET)
        blob = bucket.blob(payload.expected_blob_path)

        if not blob.exists():
            raise inngest.NonRetriableError("Blob does not exist in GCS — upload may have failed")

        blob.reload()
        actual_size = blob.size or 0
        if payload.expected_size_bytes > 0 and actual_size != payload.expected_size_bytes:
            raise inngest.NonRetriableError(
                f"Size mismatch: expected {payload.expected_size_bytes}, got {actual_size}"
            )

        if payload.expected_md5_hash and blob.md5_hash:
            gcs_md5_bytes = base64.b64decode(blob.md5_hash)
            gcs_md5_hex = gcs_md5_bytes.hex()
            if gcs_md5_hex != payload.expected_md5_hash.lower():
                raise inngest.NonRetriableError(
                    f"MD5 mismatch: client={payload.expected_md5_hash}, gcs={gcs_md5_hex}"
                )

        if payload.expected_crc32c and blob.crc32c != payload.expected_crc32c:
            raise inngest.NonRetriableError(
                f"CRC32C mismatch: client={payload.expected_crc32c}, gcs={blob.crc32c}"
            )

        return BlobVerificationResult(size=actual_size)

    return await asyncio.to_thread(_blocking)


async def _on_upload_failure(ctx: inngest.Context, _step: inngest.Step) -> None:
    fc = extract_failure_context(ctx, "Upload processing failed")

    await update_recording_fields(
        fc.recording_id,
        upload_status=UploadStatus.UPLOAD_FAILED,
        upload_error=fc.error_message,
    )

    if fc.user_id:
        await notify_user(
            fc.user_id,
            OCNotificationEvent.UPLOAD_FAILED,
            "Upload failed — keep local recording",
            f"Upload processing failed: {fc.error_message}. "
            "Please keep the local recording and retry the upload.",
        )


@inngest_client.create_function(
    fn_id="process-upload",
    trigger=inngest.TriggerEvent(event=OCRecordingEvent.UPLOAD_CONFIRMED),
    retries=3,
    on_failure=_on_upload_failure,  # type: ignore[arg-type]
)
async def process_upload_fn(ctx: inngest.Context, step: inngest.Step) -> str:
    """Process a recording upload: verify integrity, finalize status, notify."""
    payload = UploadConfirmedPayload.model_validate(ctx.event.data)

    async def _set_upload_metadata() -> str:
        async with AsyncSessionLocal() as db:
            recording = await db.get(OC_Recording, payload.recording_id)
            if not recording:
                raise inngest.NonRetriableError("Recording not found")
            gcs_url = f"{GCS_PUBLIC_BASE}{payload.expected_blob_path}"
            recording.gcs_url = gcs_url
            recording.uploaded_at = datetime.now(UTC)
            recording.upload_status = UploadStatus.UPLOADED
            recording.upload_error = None
            await db.commit()
            return gcs_url

    await step.run("set-upload-metadata", _set_upload_metadata)

    async def _verify_blob() -> dict[str, Any]:
        result = await verify_gcs_blob(payload)
        return result.model_dump()

    blob_info = BlobVerificationResult.model_validate(
        await step.run("verify-gcs-blob", _verify_blob)
    )

    await step.run(
        "finalize-verified",
        lambda: update_recording_fields(payload.recording_id, upload_status=UploadStatus.VERIFIED),
    )

    async def _notify() -> None:
        if payload.user_id is None:
            return
        await notify_user(
            payload.user_id,
            OCNotificationEvent.UPLOAD_VERIFIED,
            "Recording uploaded — safe to free device storage",
            f"Upload verified ({blob_info.size} bytes). You can safely delete the local recording.",
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
