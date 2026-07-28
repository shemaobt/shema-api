from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.as_enums import AsAudioFormat as AudioFormat
from app.core.as_enums import AsSortDimension as SortDimension
from app.core.as_enums import AsSortRound as SortRound
from app.core.as_enums import AsUploadStatus as UploadStatus
from app.core.exceptions import ConflictError
from app.db.models.as_tier_c import AsTierCClip, AsTierCSortAssignment
from app.models.annotation_studio import PresignedUpload
from app.services.annotation_studio import storage
from app.services.annotation_studio.common import enforce_audio_size, get_or_404
from app.services.annotation_studio.content_types import content_type_for_format
from app.services.annotation_studio.export_plan import SortAssignmentInput, compute_agreement
from app.services.annotation_studio.naming import raw_object_key, tier_c_clip_id, tier_c_filename
from app.services.language.get_language_or_404 import get_language_or_404

TIER_DIR = "tier_c"


async def list_clips(db: AsyncSession, language_id: str) -> list[AsTierCClip]:
    rows = await db.execute(
        select(AsTierCClip)
        .where(AsTierCClip.language_id == language_id)
        .order_by(AsTierCClip.clip_number)
    )
    return list(rows.scalars().all())


async def create_clip(
    db: AsyncSession,
    language_id: str,
    clip_number: int,
    upload_format: str,
    source_recording_id: str | None = None,
    source_word_text: str | None = None,
    position: str | None = None,
    duration_ms: int | None = None,
) -> tuple[AsTierCClip, PresignedUpload]:
    language = await get_language_or_404(db, language_id)
    fmt = AudioFormat(upload_format)

    clip_id = str(uuid.uuid4())
    storage_key = raw_object_key(language.code, TIER_DIR, clip_id, fmt)
    clip = AsTierCClip(
        id=clip_id,
        language_id=language_id,
        clip_number=clip_number,
        source_recording_id=source_recording_id,
        source_word_text=source_word_text,
        position=position,
        storage_key=storage_key,
        export_clip_id=tier_c_clip_id(clip_number),
        export_filename=tier_c_filename(clip_number),
        upload_format=fmt.value,
        duration_ms=duration_ms,
        upload_status=UploadStatus.PENDING.value,
    )
    db.add(clip)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ConflictError("A clip with this number already exists") from exc
    await db.refresh(clip)
    presigned = storage.presign_put(storage_key, content_type_for_format(fmt))
    return clip, presigned


async def complete_clip(db: AsyncSession, clip_id: str) -> AsTierCClip:
    clip = await get_or_404(db, AsTierCClip, clip_id, "Clip")
    enforce_audio_size(clip.storage_key)
    clip.upload_status = UploadStatus.STORED.value
    await db.commit()
    await db.refresh(clip)
    return clip


async def delete_clip(db: AsyncSession, clip_id: str) -> None:
    clip = await get_or_404(db, AsTierCClip, clip_id, "Clip")
    storage_key = clip.storage_key
    await db.delete(clip)
    await db.commit()
    # Delete storage after the commit so a failed commit can't orphan the row.
    storage.delete(storage_key)


async def upsert_sort(
    db: AsyncSession,
    clip_id: str,
    dimension: str,
    sort_round: str,
    group_label: str | None,
) -> AsTierCSortAssignment:
    clip = await get_or_404(db, AsTierCClip, clip_id, "Clip")
    dimension_value = SortDimension(dimension).value
    round_value = SortRound(sort_round).value
    label = group_label.strip() if group_label else None

    existing = (
        await db.execute(
            select(AsTierCSortAssignment).where(
                AsTierCSortAssignment.clip_id == clip.id,
                AsTierCSortAssignment.dimension == dimension_value,
                AsTierCSortAssignment.round == round_value,
            )
        )
    ).scalar_one_or_none()

    if existing is None:
        existing = AsTierCSortAssignment(
            clip_id=clip.id,
            dimension=dimension_value,
            round=round_value,
            group_label=label,
        )
        db.add(existing)
    else:
        existing.group_label = label
    await db.commit()
    await db.refresh(existing)
    return existing


async def _assignments(
    db: AsyncSession, language_id: str, dimension: str, sort_round: str
) -> list[tuple[AsTierCSortAssignment, AsTierCClip]]:
    rows = await db.execute(
        select(AsTierCSortAssignment, AsTierCClip)
        .join(AsTierCClip, AsTierCSortAssignment.clip_id == AsTierCClip.id)
        .where(
            AsTierCClip.language_id == language_id,
            AsTierCSortAssignment.dimension == SortDimension(dimension).value,
            AsTierCSortAssignment.round == SortRound(sort_round).value,
        )
    )
    return [(assignment, clip) for assignment, clip in rows.all()]


async def list_assignments(
    db: AsyncSession, language_id: str, dimension: str, sort_round: str
) -> list[tuple[AsTierCSortAssignment, AsTierCClip]]:
    return await _assignments(db, language_id, dimension, sort_round)


async def reliability(db: AsyncSession, language_id: str, dimension: str) -> dict:
    normal = [
        SortAssignmentInput(clip.export_clip_id, assignment.group_label)
        for assignment, clip in await _assignments(
            db, language_id, dimension, SortRound.NORMAL.value
        )
        if assignment.group_label
    ]
    repeat = [
        SortAssignmentInput(clip.export_clip_id, assignment.group_label)
        for assignment, clip in await _assignments(
            db, language_id, dimension, SortRound.RELIABILITY.value
        )
        if assignment.group_label
    ]
    result = compute_agreement(tuple(normal), tuple(repeat))
    if result is None:
        return {"dimension": dimension, "n_compared": 0, "agreement_pct": None}
    return {"dimension": dimension, **result}
