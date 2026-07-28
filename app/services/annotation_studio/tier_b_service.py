from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.as_enums import AsAudioFormat as AudioFormat
from app.core.as_enums import AsPairSide as PairSide
from app.core.as_enums import AsUploadStatus as UploadStatus
from app.core.exceptions import ConflictError
from app.db.models.as_tier_b import AsTierBPair, AsTierBRecording
from app.models.annotation_studio import PresignedUpload
from app.services.annotation_studio import storage
from app.services.annotation_studio.common import enforce_audio_size, get_or_404
from app.services.annotation_studio.content_types import content_type_for_format
from app.services.annotation_studio.naming import raw_object_key, tier_b_filename
from app.services.language.get_language_or_404 import get_language_or_404

TIER_DIR = "tier_b"


def _normalize_pair_text(text: str | None) -> str | None:
    """Optional free-text reference note (any script); never used in filenames or CSV."""
    if text is None:
        return None
    text = text.strip()
    return text or None


async def list_pairs(db: AsyncSession, language_id: str) -> list[AsTierBPair]:
    rows = await db.execute(
        select(AsTierBPair)
        .where(AsTierBPair.language_id == language_id)
        .order_by(AsTierBPair.pair_number)
    )
    return list(rows.scalars().all())


async def create_pair(
    db: AsyncSession,
    language_id: str,
    pair_number: int,
    word_a_text: str | None = None,
    word_b_text: str | None = None,
    speaker_id: str | None = None,
) -> AsTierBPair:
    await get_language_or_404(db, language_id)
    word_a_text = _normalize_pair_text(word_a_text)
    word_b_text = _normalize_pair_text(word_b_text)
    pair = AsTierBPair(
        language_id=language_id,
        pair_number=pair_number,
        word_a_text=word_a_text,
        word_b_text=word_b_text,
        speaker_id=speaker_id,
    )
    db.add(pair)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ConflictError("A pair with this number already exists") from exc
    await db.refresh(pair)
    return pair


async def update_pair(
    db: AsyncSession,
    pair_id: str,
    word_a_text: str | None,
    word_b_text: str | None,
) -> AsTierBPair:
    pair = await get_or_404(db, AsTierBPair, pair_id, "Pair")
    pair.word_a_text = _normalize_pair_text(word_a_text)
    pair.word_b_text = _normalize_pair_text(word_b_text)
    await db.commit()
    await db.refresh(pair)
    return pair


async def delete_pair(db: AsyncSession, pair_id: str) -> None:
    pair = await get_or_404(db, AsTierBPair, pair_id, "Pair")
    await db.delete(pair)
    await db.commit()


async def list_recordings(db: AsyncSession, language_id: str) -> list[AsTierBRecording]:
    rows = await db.execute(
        select(AsTierBRecording)
        .join(AsTierBPair, AsTierBRecording.pair_id == AsTierBPair.id)
        .where(AsTierBPair.language_id == language_id)
    )
    return list(rows.scalars().all())


async def create_recording(
    db: AsyncSession,
    pair_id: str,
    side: str,
    rep_index: int,
    upload_format: str,
    duration_ms: int | None = None,
) -> tuple[AsTierBRecording, PresignedUpload]:
    pair = await get_or_404(db, AsTierBPair, pair_id, "Pair")
    side_value = PairSide(side).value
    fmt = AudioFormat(upload_format)
    language = await get_language_or_404(db, pair.language_id)

    recording_id = str(uuid.uuid4())
    storage_key = raw_object_key(language.code, TIER_DIR, recording_id, fmt)
    recording = AsTierBRecording(
        id=recording_id,
        pair_id=pair_id,
        side=side_value,
        rep_index=rep_index,
        storage_key=storage_key,
        export_filename=tier_b_filename(pair.pair_number, side_value, rep_index),
        upload_format=fmt.value,
        duration_ms=duration_ms,
        upload_status=UploadStatus.PENDING.value,
    )
    db.add(recording)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ConflictError("This repetition already exists") from exc
    await db.refresh(recording)
    presigned = storage.presign_put(storage_key, content_type_for_format(fmt))
    return recording, presigned


async def complete_recording(db: AsyncSession, recording_id: str) -> AsTierBRecording:
    recording = await get_or_404(db, AsTierBRecording, recording_id, "Recording")
    enforce_audio_size(recording.storage_key)
    recording.upload_status = UploadStatus.STORED.value
    await db.commit()
    await db.refresh(recording)
    return recording


async def delete_recording(db: AsyncSession, recording_id: str) -> None:
    recording = await get_or_404(db, AsTierBRecording, recording_id, "Recording")
    storage_key = recording.storage_key
    await db.delete(recording)
    await db.commit()
    # Delete storage after the commit so a failed commit can't orphan the row.
    storage.delete(storage_key)
