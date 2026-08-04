import logging
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path

import inngest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.core.enums import (
    CleaningStatus,
    OCNotificationEvent,
    OCRecordingEvent,
    SplittingStatus,
    UploadStatus,
)
from app.core.inngest_client import inngest_client
from app.db.models.oc_recording import OC_Recording
from app.inngest.helpers import (
    check_recording_verified,
    extract_failure_context,
    notify_user,
    update_recording_fields,
)
from app.inngest.schemas import SegmentResult, SplitRequestedPayload
from app.services.oral_collector.gcs_utils import content_type_for_format, upload_gcs_blob
from app.services.oral_collector.recording_service import FORMAT_EXTENSIONS, _gcs_blob_path
from app.services.oral_collector.review_flags import recompute_review_flags
from app.services.oral_collector.split_service import (
    _download_audio,
    _ffmpeg_split_segment,
)

logger = logging.getLogger(__name__)


async def persist_split_segments(
    db: AsyncSession,
    payload: SplitRequestedPayload,
    segment_results: list[SegmentResult],
) -> list[str]:
    new_ids: list[str] = []
    total_segments = len(segment_results)
    # Fields below are snapshotted from the payload (frozen at request time).
    # Do NOT refetch the parent here — see SplitRequestedPayload docstring.
    for seg in segment_results:
        source_seg = payload.segments[seg.index]
        new_recording = OC_Recording(
            id=seg.id,
            project_id=payload.project_id,
            genre_id=source_seg.genre_id,
            subcategory_id=source_seg.subcategory_id,
            register_id=source_seg.register_id,
            secondary_genre_id=payload.secondary_genre_id,
            secondary_subcategory_id=payload.secondary_subcategory_id,
            secondary_register_id=payload.secondary_register_id,
            user_id=payload.user_id,
            storyteller_id=payload.storyteller_id,
            title=f"{payload.title} (segment {seg.index + 1})",
            description=payload.description,
            duration_seconds=seg.duration_seconds,
            file_size_bytes=seg.file_size_bytes,
            format=payload.format,
            gcs_url=seg.gcs_url,
            upload_status=UploadStatus.VERIFIED,
            cleaning_status=CleaningStatus.NONE,
            splitting_status=SplittingStatus.NONE,
            split_from_id=payload.recording_id,
            split_index=seg.index,
            split_segment_count=total_segments,
            recorded_at=(
                datetime.fromisoformat(payload.recorded_at)
                if isinstance(payload.recorded_at, str)
                else payload.recorded_at
            ),
            uploaded_at=datetime.now(UTC),
        )
        recompute_review_flags(new_recording)
        db.add(new_recording)
        new_ids.append(seg.id)
    await db.commit()

    parent = await db.get(OC_Recording, payload.recording_id)
    if parent:
        parent.splitting_status = SplittingStatus.ARCHIVED_AFTER_SPLIT
        await db.commit()

    return new_ids


async def _on_split_failure(ctx: inngest.Context, _step: inngest.Step) -> None:
    fc = extract_failure_context(ctx, "Splitting failed")

    await update_recording_fields(
        fc.recording_id,
        splitting_status=SplittingStatus.FAILED,
    )

    if fc.user_id:
        await notify_user(
            fc.user_id,
            OCNotificationEvent.SPLIT_FAILED,
            "Recording split failed",
            f"Recording split failed: {fc.error_message}",
        )


@inngest_client.create_function(
    fn_id="split-recording",
    trigger=inngest.TriggerEvent(event=OCRecordingEvent.SPLIT_REQUESTED),
    retries=1,
    on_failure=_on_split_failure,  # type: ignore[arg-type]
)
async def split_recording_fn(ctx: inngest.Context, step: inngest.Step) -> str:
    payload = SplitRequestedPayload.model_validate(ctx.event.data)

    gcs_url = await step.run(
        "check-verified",
        lambda: check_recording_verified(payload.recording_id),
    )

    async def _split_and_upload() -> list[dict[str, object]]:
        audio_data = await _download_audio(gcs_url)
        fmt = payload.format.lower()
        ext = FORMAT_EXTENSIONS.get(fmt, f".{fmt}")
        content_type = content_type_for_format(fmt)
        results: list[SegmentResult] = []

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            input_file = tmp / f"original{ext}"
            input_file.write_bytes(audio_data)

            for i, seg in enumerate(payload.segments):
                new_id = str(uuid.uuid4())
                output_file = tmp / f"segment_{i}{ext}"

                await _ffmpeg_split_segment(
                    input_file, output_file, seg.start_seconds, seg.end_seconds
                )

                segment_bytes = output_file.read_bytes()
                blob_path = _gcs_blob_path(payload.project_id, seg.genre_id, new_id, fmt)
                segment_gcs_url = await upload_gcs_blob(blob_path, segment_bytes, content_type)

                results.append(
                    SegmentResult(
                        id=new_id,
                        gcs_url=segment_gcs_url,
                        duration_seconds=seg.end_seconds - seg.start_seconds,
                        file_size_bytes=len(segment_bytes),
                        index=i,
                    )
                )

        return [r.model_dump() for r in results]

    raw_results = await step.run("split-and-upload", _split_and_upload)
    segment_results = [SegmentResult.model_validate(r) for r in raw_results]

    async def _save_segments() -> list[str]:
        async with AsyncSessionLocal() as db:
            return await persist_split_segments(db, payload, segment_results)

    new_ids = await step.run("save-segments", _save_segments)

    async def _notify() -> None:
        await notify_user(
            payload.user_id,
            OCNotificationEvent.SPLIT_COMPLETED,
            f"Recording split into {len(new_ids)} segments",
            f"Recording has been split into {len(new_ids)} segments successfully.",
        )

    await step.run("notify", _notify)

    return SplittingStatus.COMPLETED
