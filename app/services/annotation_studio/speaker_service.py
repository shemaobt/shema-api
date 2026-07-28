from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, ValidationError
from app.db.models.as_speaker import AsSpeaker
from app.services.annotation_studio.common import get_or_404
from app.services.annotation_studio.naming import is_valid_label
from app.services.language.get_language_or_404 import get_language_or_404


async def list_speakers(db: AsyncSession, language_id: str) -> list[AsSpeaker]:
    rows = await db.execute(
        select(AsSpeaker).where(AsSpeaker.language_id == language_id).order_by(AsSpeaker.label)
    )
    return list(rows.scalars().all())


async def get_speaker(db: AsyncSession, speaker_id: str) -> AsSpeaker:
    return await get_or_404(db, AsSpeaker, speaker_id, "Speaker")


async def create_speaker(
    db: AsyncSession,
    language_id: str,
    label: str | None = None,
    display_name: str | None = None,
) -> AsSpeaker:
    await get_language_or_404(db, language_id)
    display_name = (display_name or "").strip() or None

    if label is not None and label.strip():
        # explicit, filename-safe label (kept for back-compat / scripts)
        label = label.strip().lower()
        if not is_valid_label(label):
            raise ValidationError("Speaker label may contain only lowercase letters and digits")
        existing = (
            await db.execute(
                select(AsSpeaker).where(
                    AsSpeaker.language_id == language_id, AsSpeaker.label == label
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            raise ConflictError("A speaker with this label already exists")
        speaker = AsSpeaker(language_id=language_id, label=label, display_name=display_name)
        db.add(speaker)
        await db.commit()
        await db.refresh(speaker)
        return speaker

    # zero-typing: auto-id speaker1, speaker2, ... (no separator → filename-safe)
    count = (
        await db.execute(
            select(func.count()).select_from(AsSpeaker).where(AsSpeaker.language_id == language_id)
        )
    ).scalar_one()
    for seq in range(count + 1, count + 51):
        speaker = AsSpeaker(
            language_id=language_id, label=f"speaker{seq}", display_name=display_name
        )
        db.add(speaker)
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            continue
        await db.refresh(speaker)
        return speaker
    raise ConflictError("Could not allocate a speaker id")


async def update_speaker(db: AsyncSession, speaker_id: str, display_name: str | None) -> AsSpeaker:
    speaker = await get_speaker(db, speaker_id)
    speaker.display_name = display_name
    await db.commit()
    await db.refresh(speaker)
    return speaker


async def delete_speaker(db: AsyncSession, speaker_id: str) -> None:
    speaker = await get_speaker(db, speaker_id)
    await db.delete(speaker)
    await db.commit()
