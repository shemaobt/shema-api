import logging

import httpx
import inngest
from sqlalchemy import update

from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.core.enums import (
    CleaningStatus,
    OCNotificationEvent,
    OCRecordingEvent,
)
from app.core.inngest_client import inngest_client
from app.db.models.oc_recording import OC_Recording
from app.inngest.helpers import (
    check_recording_verified,
    extract_failure_context,
    notify_user,
    update_recording_fields,
)
from app.inngest.schemas import CleanRequestedPayload
from app.services.oral_collector.constants import gcs_oc_bucket
from app.services.oral_collector.gcs_utils import (
    blob_name_from_url,
    copy_gcs_blob,
    delete_gcs_object,
    gcs_public_base,
    original_blob_name,
    upload_gcs_blob,
)
from app.services.oral_collector.recording_service import replacement_blob_path

logger = logging.getLogger(__name__)


async def _on_clean_failure(ctx: inngest.Context, _step: inngest.Step) -> None:
    fc = extract_failure_context(ctx, "Cleaning failed")

    await update_recording_fields(
        fc.recording_id,
        cleaning_status=CleaningStatus.FAILED,
        cleaning_error=fc.error_message,
    )

    if fc.user_id:
        await notify_user(
            fc.user_id,
            OCNotificationEvent.CLEANING_FAILED,
            "Audio cleaning failed",
            f"Audio cleaning failed: {fc.error_message}",
        )


async def _choose_cleaned_name(recording_id: str) -> str:
    async with AsyncSessionLocal() as db:
        recording = await db.get(OC_Recording, recording_id)
        if not recording:
            raise inngest.NonRetriableError("Recording not found")
        return replacement_blob_path(
            recording.project_id, recording.genre_id, recording.id, recording.format
        )


async def _repoint_to_cleaned(recording_id: str, *, cleaned_from: str, cleaned_url: str) -> bool:
    """Point the recording at its cleaned audio, unless its audio was replaced meanwhile.

    A replacement confirmed while the cleaning ran moved the URL on: the cleaned audio is of
    audio the recording no longer has, so the URL stays and the cleaning is undone. The
    cleaned URL itself also matches, so a retried step finds its own write and keeps it.
    """
    async with AsyncSessionLocal() as db:
        repointed = await db.execute(
            update(OC_Recording)
            .where(
                OC_Recording.id == recording_id,
                OC_Recording.gcs_url.in_([cleaned_from, cleaned_url]),
            )
            .values(
                gcs_url=cleaned_url, cleaning_status=CleaningStatus.CLEANED, cleaning_error=None
            )
        )
        if repointed.rowcount == 0:
            await db.execute(
                update(OC_Recording)
                .where(OC_Recording.id == recording_id)
                .values(cleaning_status=CleaningStatus.NONE, cleaning_error=None)
            )
        await db.commit()
        return bool(repointed.rowcount)


@inngest_client.create_function(
    fn_id="clean-recording",
    trigger=inngest.TriggerEvent(event=OCRecordingEvent.CLEAN_REQUESTED),
    retries=3,
    on_failure=_on_clean_failure,  # type: ignore[arg-type]
)
async def clean_recording_fn(ctx: inngest.Context, step: inngest.Step) -> str:
    payload = CleanRequestedPayload.model_validate(ctx.event.data)

    verified_url = await step.run(
        "check-verified",
        lambda: check_recording_verified(payload.recording_id),
    )

    async def _call_cleaning_api() -> str:
        settings = get_settings()
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                settings.cleaning_api_url,
                json={"input_url": verified_url or payload.gcs_url},
                headers={
                    "Authorization": f"Bearer {settings.cleaning_api_key}",
                    "Content-Type": "application/json",
                },
                timeout=120.0,
            )
            resp.raise_for_status()
            result = resp.json()
        return str(result.get("output_url", ""))

    cleaned_url = await step.run("call-cleaning-api", _call_cleaning_api)

    cleaned_name = await step.run(
        "choose-cleaned-name",
        lambda: _choose_cleaned_name(payload.recording_id),
    )
    previous = blob_name_from_url(verified_url or payload.gcs_url)

    async def _backup_and_upload() -> None:
        async with httpx.AsyncClient() as client:
            resp = await client.get(cleaned_url, timeout=120.0)
            resp.raise_for_status()
        if previous:
            await copy_gcs_blob(previous, original_blob_name(previous))
        await upload_gcs_blob(cleaned_name, resp.content, "application/octet-stream")

    await step.run("backup-and-upload", _backup_and_upload)

    async def _update_status() -> bool:
        repointed = await _repoint_to_cleaned(
            payload.recording_id,
            cleaned_from=verified_url or payload.gcs_url,
            cleaned_url=f"{gcs_public_base()}{cleaned_name}",
        )
        if not repointed:
            await delete_gcs_object(gcs_oc_bucket(), cleaned_name)
            return False
        await notify_user(
            payload.user_id,
            OCNotificationEvent.CLEANING_COMPLETED,
            "Audio cleaning complete",
            "Your recording has been cleaned successfully.",
        )
        return True

    if not await step.run("update-status", _update_status):
        return CleaningStatus.NONE

    async def _delete_previous() -> None:
        if not previous or previous == cleaned_name:
            return
        try:
            await delete_gcs_object(gcs_oc_bucket(), previous)
        except Exception:
            logger.exception("Failed to delete the object the cleaning replaced: %s", previous)

    await step.run("delete-previous", _delete_previous)

    return CleaningStatus.CLEANED
