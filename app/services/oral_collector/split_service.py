import asyncio
import logging
from pathlib import Path

import inngest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import OCRecordingEvent, SplittingStatus, UploadStatus
from app.core.exceptions import (
    NotFoundError,
    SegmentClassificationConflictError,
    ValidationError,
)
from app.core.inngest_client import inngest_client
from app.db.models.oc_recording import OC_Recording
from app.inngest.schemas import SplitRequestedPayload, SplitSegmentData
from app.models.oc_recording import SplitSegment
from app.services.oral_collector.recording_service import (
    check_recording_access,
    get_recording,
    secondary_equals_primary,
)

logger = logging.getLogger(__name__)


async def _download_audio(gcs_url: str) -> bytes:

    import httpx

    async with httpx.AsyncClient() as client:
        resp = await client.get(gcs_url, timeout=120.0)
        resp.raise_for_status()
        return resp.content


async def _ffmpeg_split_segment(
    input_path: Path, output_path: Path, start: float, end: float
) -> None:

    duration = end - start
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(input_path),
        "-ss",
        str(start),
        "-t",
        str(duration),
        "-c",
        "copy",
        str(output_path),
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"FFmpeg failed: {stderr.decode()}")


async def request_split(
    db: AsyncSession,
    recording_id: str,
    segments: list[SplitSegment],
    user_id: str,
) -> OC_Recording:
    recording = await get_recording(db, recording_id)
    await check_recording_access(db, recording, user_id)

    if not recording.gcs_url:
        raise NotFoundError("Recording has no uploaded audio file")

    if recording.upload_status != UploadStatus.VERIFIED:
        raise ValidationError(
            "Recording must be verified before splitting. "
            f"Current status: {recording.upload_status}"
        )

    for index, seg in enumerate(segments):
        effective_genre = seg.genre_id or recording.genre_id
        effective_sub = seg.subcategory_id or recording.subcategory_id
        effective_register = (
            seg.register_id if seg.register_id is not None else recording.register_id
        )
        if secondary_equals_primary(
            primary_register_id=effective_register,
            primary_genre_id=effective_genre,
            primary_subcategory_id=effective_sub,
            secondary_register_id=recording.secondary_register_id,
            secondary_genre_id=recording.secondary_genre_id,
            secondary_subcategory_id=recording.secondary_subcategory_id,
        ):
            raise SegmentClassificationConflictError(index)

    recording.splitting_status = SplittingStatus.SPLITTING
    await db.commit()
    await db.refresh(recording)

    payload = SplitRequestedPayload(
        recording_id=recording_id,
        user_id=user_id,
        segments=[
            SplitSegmentData(
                start_seconds=s.start_seconds,
                end_seconds=s.end_seconds,
                genre_id=s.genre_id or recording.genre_id,
                subcategory_id=s.subcategory_id or recording.subcategory_id,
                register_id=s.register_id if s.register_id is not None else recording.register_id,
                gain_db=s.gain_db,
            )
            for s in segments
        ],
        project_id=recording.project_id,
        format=recording.format,
        title=recording.title or "Recording",
        recorded_at=recording.recorded_at.isoformat(),
        description=recording.description,
        storyteller_id=recording.storyteller_id,
        secondary_genre_id=recording.secondary_genre_id,
        secondary_subcategory_id=recording.secondary_subcategory_id,
        secondary_register_id=recording.secondary_register_id,
    )
    await inngest_client.send(
        inngest.Event(name=OCRecordingEvent.SPLIT_REQUESTED, data=payload.model_dump())
    )

    return recording


async def backfill_split_indices(db: AsyncSession) -> tuple[int, int]:
    parent_ids_stmt = (
        select(OC_Recording.split_from_id).where(OC_Recording.split_from_id.is_not(None)).distinct()
    )
    parent_ids_result = await db.execute(parent_ids_stmt)
    parent_ids = [row for row in parent_ids_result.scalars().all() if row]

    total_updated = 0
    total_groups = 0

    for parent_id in parent_ids:
        siblings_stmt = (
            select(OC_Recording)
            .where(OC_Recording.split_from_id == parent_id)
            .order_by(OC_Recording.created_at, OC_Recording.id)
        )
        siblings_result = await db.execute(siblings_stmt)
        siblings = list(siblings_result.scalars().all())

        if not siblings:
            continue

        needs_backfill = any(
            s.split_index is None or s.split_segment_count is None for s in siblings
        )
        if not needs_backfill:
            continue

        total_groups += 1
        segment_count = len(siblings)
        for i, sibling in enumerate(siblings):
            sibling.split_index = i
            sibling.split_segment_count = segment_count
            total_updated += 1

        await db.commit()

    return total_updated, total_groups


async def get_split_status(db: AsyncSession, recording_id: str) -> tuple[OC_Recording, list[str]]:
    recording = await get_recording(db, recording_id)

    segment_ids: list[str] = []
    if recording.splitting_status in (
        SplittingStatus.COMPLETED,
        SplittingStatus.ARCHIVED_AFTER_SPLIT,
    ):
        stmt = (
            select(OC_Recording.id)
            .where(OC_Recording.split_from_id == recording_id)
            .order_by(
                OC_Recording.split_index.asc().nulls_last(),
                OC_Recording.created_at,
                OC_Recording.id,
            )
        )
        result = await db.execute(stmt)
        segment_ids = list(result.scalars().all())

    return recording, segment_ids
