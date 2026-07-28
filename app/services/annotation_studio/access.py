"""Per-language access control for annotation-studio.

App-wide ``annotation-studio`` access (``UserAppRole``) lets a user into the
studio; this module narrows a ``facilitator`` to the languages they are a member
of (``AsLanguageMember``). The ``admin`` role and platform admins bypass the
check and see every language.

Routers call :func:`assert_language_access` with a ``language_id`` — taken
directly from the path for ``/languages/{language_id}/...`` routes, or resolved
from the resource via the ``language_id_for_*`` helpers for by-id routes.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthorizationError, NotFoundError
from app.db.models.as_analysis_result import AsAnalysisResult
from app.db.models.as_export import AsExport
from app.db.models.as_language_member import AsLanguageMember
from app.db.models.as_speaker import AsSpeaker
from app.db.models.as_tier_a import AsTierARecording, AsTierAWord
from app.db.models.as_tier_b import AsTierBPair, AsTierBRecording
from app.db.models.as_tier_c import AsTierCClip
from app.db.models.auth import User
from app.services.authorization.has_role import has_role

APP_KEY = "annotation-studio"


async def _is_admin(db: AsyncSession, user: User) -> bool:
    """Platform admins and annotation-studio ``admin`` role members see all languages."""
    if user.is_platform_admin:
        return True
    return await has_role(db, user.id, APP_KEY, "admin")


async def assert_language_access(db: AsyncSession, user: User, language_id: str) -> None:
    """Raise ``AuthorizationError`` unless ``user`` may act on ``language_id``."""
    if await _is_admin(db, user):
        return
    member = (
        await db.execute(
            select(AsLanguageMember.id).where(
                AsLanguageMember.language_id == language_id,
                AsLanguageMember.user_id == user.id,
            )
        )
    ).scalar_one_or_none()
    if member is None:
        raise AuthorizationError("You don't have access to this language.")


async def accessible_language_ids(db: AsyncSession, user: User) -> set[str] | None:
    """The languages ``user`` may see. ``None`` means "all" (admin / platform admin)."""
    if await _is_admin(db, user):
        return None
    rows = await db.execute(
        select(AsLanguageMember.language_id).where(AsLanguageMember.user_id == user.id)
    )
    return {row[0] for row in rows.all()}


# ── language_id resolvers for by-id routes ────────────────────────────────────


async def _resolve(db: AsyncSession, stmt, label: str) -> str:  # type: ignore[no-untyped-def]
    language_id = (await db.execute(stmt)).scalar_one_or_none()
    if language_id is None:
        raise NotFoundError(f"{label} not found")
    return str(language_id)


async def language_id_for_word(db: AsyncSession, word_id: str) -> str:
    return await _resolve(
        db, select(AsTierAWord.language_id).where(AsTierAWord.id == word_id), "Word"
    )


async def language_id_for_recording_a(db: AsyncSession, recording_id: str) -> str:
    return await _resolve(
        db,
        select(AsTierAWord.language_id)
        .join(AsTierARecording, AsTierARecording.word_id == AsTierAWord.id)
        .where(AsTierARecording.id == recording_id),
        "Recording",
    )


async def language_id_for_pair(db: AsyncSession, pair_id: str) -> str:
    return await _resolve(
        db, select(AsTierBPair.language_id).where(AsTierBPair.id == pair_id), "Pair"
    )


async def language_id_for_recording_b(db: AsyncSession, recording_id: str) -> str:
    return await _resolve(
        db,
        select(AsTierBPair.language_id)
        .join(AsTierBRecording, AsTierBRecording.pair_id == AsTierBPair.id)
        .where(AsTierBRecording.id == recording_id),
        "Recording",
    )


async def language_id_for_clip(db: AsyncSession, clip_id: str) -> str:
    return await _resolve(
        db, select(AsTierCClip.language_id).where(AsTierCClip.id == clip_id), "Clip"
    )


async def language_id_for_speaker(db: AsyncSession, speaker_id: str) -> str:
    return await _resolve(
        db, select(AsSpeaker.language_id).where(AsSpeaker.id == speaker_id), "Speaker"
    )


async def language_id_for_export(db: AsyncSession, export_id: str) -> str:
    return await _resolve(
        db, select(AsExport.language_id).where(AsExport.id == export_id), "Export"
    )


async def language_id_for_result(db: AsyncSession, result_id: str) -> str:
    return await _resolve(
        db, select(AsAnalysisResult.language_id).where(AsAnalysisResult.id == result_id), "Result"
    )


# ── storage-key access (audio/url) ────────────────────────────────────────────


async def language_id_for_storage_key(db: AsyncSession, key: str) -> str:
    """Resolve the owning language of a stored object by its storage key.

    Searches every as_* column that holds a storage key. Raises ``NotFoundError``
    if the key belongs to no annotation-studio resource (blocks arbitrary-key
    presigning).
    """
    # Tier A reference audio lives on the word itself.
    word_lang = (
        await db.execute(
            select(AsTierAWord.language_id).where(AsTierAWord.reference_storage_key == key)
        )
    ).scalar_one_or_none()
    if word_lang is not None:
        return str(word_lang)

    rec_a_lang = (
        await db.execute(
            select(AsTierAWord.language_id)
            .join(AsTierARecording, AsTierARecording.word_id == AsTierAWord.id)
            .where(AsTierARecording.storage_key == key)
        )
    ).scalar_one_or_none()
    if rec_a_lang is not None:
        return str(rec_a_lang)

    rec_b_lang = (
        await db.execute(
            select(AsTierBPair.language_id)
            .join(AsTierBRecording, AsTierBRecording.pair_id == AsTierBPair.id)
            .where(AsTierBRecording.storage_key == key)
        )
    ).scalar_one_or_none()
    if rec_b_lang is not None:
        return str(rec_b_lang)

    clip_lang = (
        await db.execute(select(AsTierCClip.language_id).where(AsTierCClip.storage_key == key))
    ).scalar_one_or_none()
    if clip_lang is not None:
        return str(clip_lang)

    raise NotFoundError("Audio not found")
