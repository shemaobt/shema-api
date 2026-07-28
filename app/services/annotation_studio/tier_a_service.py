from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.as_enums import AsAudioFormat as AudioFormat
from app.core.as_enums import AsUploadStatus as UploadStatus
from app.core.exceptions import ConflictError, ValidationError
from app.db.models.as_speaker import AsSpeaker
from app.db.models.as_tier_a import AsTierARecording, AsTierAWord
from app.models.annotation_studio import PresignedUpload
from app.services.annotation_studio import storage
from app.services.annotation_studio.common import enforce_audio_size, get_or_404
from app.services.annotation_studio.content_types import content_type_for_format
from app.services.annotation_studio.naming import is_valid_emblem, raw_object_key, tier_a_filename
from app.services.language.get_language_or_404 import get_language_or_404

TIER_DIR = "tier_a"
REFERENCE_DIR = "tier_a/reference"

_UNSET: object = object()


def _clean_gloss(gloss: str | None) -> str | None:
    if gloss is None:
        return None
    gloss = gloss.strip()
    return gloss or None


def _clean_emblem(emblem: str | None) -> str | None:
    if emblem is None:
        return None
    emblem = emblem.strip()
    if not emblem:
        return None
    if not is_valid_emblem(emblem):
        raise ValidationError("Unknown emblem")
    return emblem


async def list_words(db: AsyncSession, language_id: str) -> list[AsTierAWord]:
    rows = await db.execute(
        select(AsTierAWord)
        .where(AsTierAWord.language_id == language_id)
        .order_by(AsTierAWord.label)
    )
    return list(rows.scalars().all())


async def create_word(
    db: AsyncSession,
    language_id: str,
    gloss: str | None = None,
    emblem: str | None = None,
) -> AsTierAWord:
    await get_language_or_404(db, language_id)
    gloss = _clean_gloss(gloss)
    emblem = _clean_emblem(emblem)
    count = (
        await db.execute(
            select(func.count())
            .select_from(AsTierAWord)
            .where(AsTierAWord.language_id == language_id)
        )
    ).scalar_one()
    # auto-id with NO separator so the {word}_{speaker}_{rep} filename stays unambiguous
    for seq in range(count + 1, count + 51):
        word = AsTierAWord(
            language_id=language_id, label=f"word{seq:03d}", gloss=gloss, emblem=emblem
        )
        db.add(word)
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            continue
        await db.refresh(word)
        return word
    raise ConflictError("Could not allocate a word id")


async def update_word(
    db: AsyncSession,
    word_id: str,
    gloss: str | None | object = _UNSET,
    emblem: str | None | object = _UNSET,
) -> AsTierAWord:
    word = await get_or_404(db, AsTierAWord, word_id, "Word")
    if gloss is not _UNSET:
        word.gloss = _clean_gloss(gloss)  # type: ignore[arg-type]
    if emblem is not _UNSET:
        word.emblem = _clean_emblem(emblem)  # type: ignore[arg-type]
    await db.commit()
    await db.refresh(word)
    return word


async def delete_word(db: AsyncSession, word_id: str) -> None:
    word = await get_or_404(db, AsTierAWord, word_id, "Word")
    reference_key = word.reference_storage_key
    await db.delete(word)
    await db.commit()
    # Delete storage only after the DB row is gone, so a failed commit can't
    # leave a record pointing at a deleted object.
    if reference_key:
        storage.delete(reference_key)


async def set_reference(
    db: AsyncSession, word_id: str, upload_format: str
) -> tuple[AsTierAWord, PresignedUpload]:
    word = await get_or_404(db, AsTierAWord, word_id, "Word")
    fmt = AudioFormat(upload_format)
    language = await get_language_or_404(db, word.language_id)
    old_key = word.reference_storage_key
    key = raw_object_key(language.code, REFERENCE_DIR, word_id, fmt)
    word.reference_storage_key = key
    word.reference_status = UploadStatus.PENDING.value
    await db.commit()
    await db.refresh(word)
    # Drop the previous object only after the new key is committed.
    if old_key and old_key != key:
        storage.delete(old_key)
    presigned = storage.presign_put(key, content_type_for_format(fmt))
    return word, presigned


async def complete_reference(db: AsyncSession, word_id: str) -> AsTierAWord:
    word = await get_or_404(db, AsTierAWord, word_id, "Word")
    if word.reference_storage_key:
        enforce_audio_size(word.reference_storage_key)
    word.reference_status = UploadStatus.STORED.value
    await db.commit()
    await db.refresh(word)
    return word


async def clear_reference(db: AsyncSession, word_id: str) -> AsTierAWord:
    word = await get_or_404(db, AsTierAWord, word_id, "Word")
    reference_key = word.reference_storage_key
    word.reference_storage_key = None
    word.reference_status = None
    await db.commit()
    await db.refresh(word)
    if reference_key:
        storage.delete(reference_key)
    return word


async def list_recordings(db: AsyncSession, language_id: str) -> list[AsTierARecording]:
    rows = await db.execute(
        select(AsTierARecording)
        .join(AsTierAWord, AsTierARecording.word_id == AsTierAWord.id)
        .where(AsTierAWord.language_id == language_id)
    )
    return list(rows.scalars().all())


async def create_recording(
    db: AsyncSession,
    word_id: str,
    speaker_id: str,
    rep_index: int,
    upload_format: str,
    duration_ms: int | None = None,
) -> tuple[AsTierARecording, PresignedUpload]:
    word = await get_or_404(db, AsTierAWord, word_id, "Word")
    speaker = await get_or_404(db, AsSpeaker, speaker_id, "Speaker")
    if speaker.language_id != word.language_id:
        raise ValidationError("Speaker and word belong to different languages")
    fmt = AudioFormat(upload_format)
    language = await get_language_or_404(db, word.language_id)

    recording_id = str(uuid.uuid4())
    storage_key = raw_object_key(language.code, TIER_DIR, recording_id, fmt)
    recording = AsTierARecording(
        id=recording_id,
        word_id=word_id,
        speaker_id=speaker_id,
        rep_index=rep_index,
        storage_key=storage_key,
        export_filename=tier_a_filename(word.label, speaker.label, rep_index),
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


async def complete_recording(db: AsyncSession, recording_id: str) -> AsTierARecording:
    recording = await get_or_404(db, AsTierARecording, recording_id, "Recording")
    enforce_audio_size(recording.storage_key)
    recording.upload_status = UploadStatus.STORED.value
    await db.commit()
    await db.refresh(recording)
    return recording


async def delete_recording(db: AsyncSession, recording_id: str) -> None:
    recording = await get_or_404(db, AsTierARecording, recording_id, "Recording")
    storage_key = recording.storage_key
    await db.delete(recording)
    await db.commit()
    storage.delete(storage_key)
