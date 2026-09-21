import logging

import inngest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import CleaningStatus, OCRecordingEvent, UploadStatus
from app.core.exceptions import NotFoundError, ValidationError
from app.core.inngest_client import inngest_client
from app.db.models.oc_recording import OC_Recording
from app.inngest.schemas import CleanRequestedPayload
from app.services.oral_collector.require_manager import require_project_manager

logger = logging.getLogger(__name__)


async def _get_recording(db: AsyncSession, recording_id: str) -> OC_Recording:

    stmt = select(OC_Recording).where(OC_Recording.id == recording_id)
    result = await db.execute(stmt)
    recording = result.scalar_one_or_none()
    if not recording:
        raise NotFoundError("Recording not found")
    return recording


def _original_blob_name(blob_name: str) -> str:

    dot_idx = blob_name.rfind(".")
    if dot_idx == -1:
        return f"{blob_name}_original"
    return f"{blob_name[:dot_idx]}_original{blob_name[dot_idx:]}"


async def trigger_cleaning(db: AsyncSession, recording_id: str, user_id: str) -> OC_Recording:
    recording = await _get_recording(db, recording_id)
    await require_project_manager(
        db, recording.project_id, user_id, action="trigger audio cleaning"
    )

    if not recording.gcs_url:
        raise NotFoundError("Recording has no uploaded audio file")

    if recording.upload_status != UploadStatus.VERIFIED:
        raise ValidationError(
            f"Recording must be verified before cleaning. Current status: {recording.upload_status}"
        )

    recording.cleaning_status = CleaningStatus.CLEANING
    recording.cleaning_error = None
    await db.commit()
    await db.refresh(recording)

    payload = CleanRequestedPayload(
        recording_id=recording_id,
        user_id=user_id,
        gcs_url=recording.gcs_url,
    )
    await inngest_client.send(
        inngest.Event(name=OCRecordingEvent.CLEAN_REQUESTED, data=payload.model_dump())
    )

    return recording


async def get_cleaning_status(db: AsyncSession, recording_id: str) -> OC_Recording:

    return await _get_recording(db, recording_id)
