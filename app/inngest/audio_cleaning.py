import logging

import httpx
import inngest

from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.core.enums import (
    CleaningStatus,
    OCNotificationEvent,
    OCRecordingEvent,
)
from app.core.inngest_client import inngest_client
from app.inngest.helpers import (
    check_recording_verified,
    extract_failure_context,
    notify_user,
    update_recording_fields,
)
from app.inngest.schemas import CleanRequestedPayload
from app.services.oral_collector.gcs_utils import (
    blob_name_from_url,
    copy_gcs_blob,
    discard_gcs_object,
    gcs_public_base,
    original_blob_name,
    upload_gcs_blob,
)
from app.services.oral_collector.recording_service import (
    choose_cleaned_name,
    repoint_to_cleaned,
)

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

    async def _choose_cleaned_name() -> str:
        async with AsyncSessionLocal() as db:
            return await choose_cleaned_name(db, payload.recording_id)

    cleaned_name = await step.run("choose-cleaned-name", _choose_cleaned_name)
    previous = blob_name_from_url(verified_url or payload.gcs_url)

    async def _backup_and_upload() -> None:
        async with httpx.AsyncClient() as client:
            resp = await client.get(cleaned_url, timeout=120.0)
            resp.raise_for_status()
        if previous:
            await copy_gcs_blob(previous, original_blob_name(previous))
        await upload_gcs_blob(cleaned_name, resp.content, "application/octet-stream")

    await step.run("back-up-and-write-cleaned-audio", _backup_and_upload)

    async def _update_status() -> bool:
        async with AsyncSessionLocal() as db:
            repointed = await repoint_to_cleaned(
                db,
                payload.recording_id,
                cleaned_from=verified_url or payload.gcs_url,
                cleaned_url=f"{gcs_public_base()}{cleaned_name}",
            )
        if not repointed:
            await discard_gcs_object(cleaned_name)
            return False
        await notify_user(
            payload.user_id,
            OCNotificationEvent.CLEANING_COMPLETED,
            "Audio cleaning complete",
            "Your recording has been cleaned successfully.",
        )
        return True

    if not await step.run("repoint-to-cleaned-audio", _update_status):
        return CleaningStatus.NONE

    async def _delete_previous() -> None:
        if previous and previous != cleaned_name:
            await discard_gcs_object(previous)

    await step.run("delete-replaced-audio", _delete_previous)

    return CleaningStatus.CLEANED
