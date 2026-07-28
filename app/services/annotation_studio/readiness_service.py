from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.as_enums import AsSortDimension as SortDimension
from app.core.as_enums import AsSortRound as SortRound
from app.core.as_enums import AsUploadStatus as UploadStatus
from app.db.models.as_tier_a import AsTierARecording, AsTierAWord
from app.db.models.as_tier_b import AsTierBPair, AsTierBRecording
from app.db.models.as_tier_c import AsTierCClip, AsTierCSortAssignment
from app.services.annotation_studio.export_plan import MIN_INSTANCES_PER_WORD

# A Tier B pair is "ready" once both sides have at least this many stored takes
# (mirrors the frontend TIER_B.repsPerSide and Tier A's MIN_INSTANCES_PER_WORD).
REPS_PER_SIDE = 5

_STORED = UploadStatus.STORED.value


async def _scalar_int(db: AsyncSession, stmt) -> int:  # type: ignore[no-untyped-def]
    return int((await db.execute(stmt)).scalar_one() or 0)


async def compute_readiness(db: AsyncSession, language_id: str) -> dict:
    """Per-tier collection progress, computed with SQL aggregates (no row loading)."""

    # ── Tier A ──────────────────────────────────────────────────────────────
    words_total = await _scalar_int(
        db,
        select(func.count()).select_from(AsTierAWord).where(AsTierAWord.language_id == language_id),
    )
    a_instances = await _scalar_int(
        db,
        select(func.count())
        .select_from(AsTierARecording)
        .join(AsTierAWord, AsTierARecording.word_id == AsTierAWord.id)
        .where(AsTierAWord.language_id == language_id, AsTierARecording.upload_status == _STORED),
    )
    a_ready_words = (
        select(AsTierARecording.word_id)
        .join(AsTierAWord, AsTierARecording.word_id == AsTierAWord.id)
        .where(AsTierAWord.language_id == language_id, AsTierARecording.upload_status == _STORED)
        .group_by(AsTierARecording.word_id)
        .having(func.count() >= MIN_INSTANCES_PER_WORD)
        .subquery()
    )
    words_ready = await _scalar_int(db, select(func.count()).select_from(a_ready_words))

    # ── Tier B ──────────────────────────────────────────────────────────────
    pairs_total = await _scalar_int(
        db,
        select(func.count()).select_from(AsTierBPair).where(AsTierBPair.language_id == language_id),
    )
    b_recordings = await _scalar_int(
        db,
        select(func.count())
        .select_from(AsTierBRecording)
        .join(AsTierBPair, AsTierBRecording.pair_id == AsTierBPair.id)
        .where(AsTierBPair.language_id == language_id, AsTierBRecording.upload_status == _STORED),
    )
    # A pair side is ready when it has >= REPS_PER_SIDE stored takes; a pair is
    # ready when both of its sides are.
    ready_sides = (
        select(AsTierBRecording.pair_id.label("pair_id"))
        .join(AsTierBPair, AsTierBRecording.pair_id == AsTierBPair.id)
        .where(AsTierBPair.language_id == language_id, AsTierBRecording.upload_status == _STORED)
        .group_by(AsTierBRecording.pair_id, AsTierBRecording.side)
        .having(func.count() >= REPS_PER_SIDE)
        .subquery()
    )
    ready_pairs = (
        select(ready_sides.c.pair_id)
        .group_by(ready_sides.c.pair_id)
        .having(func.count() >= 2)
        .subquery()
    )
    pairs_ready = await _scalar_int(db, select(func.count()).select_from(ready_pairs))

    # ── Tier C ──────────────────────────────────────────────────────────────
    clips_total = await _scalar_int(
        db,
        select(func.count())
        .select_from(AsTierCClip)
        .where(AsTierCClip.language_id == language_id, AsTierCClip.upload_status == _STORED),
    )
    sorted_rows = await db.execute(
        select(AsTierCSortAssignment.dimension, func.count())
        .join(AsTierCClip, AsTierCSortAssignment.clip_id == AsTierCClip.id)
        .where(
            AsTierCClip.language_id == language_id,
            AsTierCSortAssignment.round == SortRound.NORMAL.value,
            AsTierCSortAssignment.group_label.is_not(None),
        )
        .group_by(AsTierCSortAssignment.dimension)
    )
    by_dimension: dict[str, int] = {row[0]: row[1] for row in sorted_rows.all()}

    return {
        "tier_a": {
            "words_total": words_total,
            "words_ready": words_ready,
            "instances": a_instances,
            "min_instances": MIN_INSTANCES_PER_WORD,
        },
        "tier_b": {
            "pairs": pairs_total,
            "pairs_ready": pairs_ready,
            "recordings": b_recordings,
        },
        "tier_c": {
            "clips": clips_total,
            "onset_sorted": int(by_dimension.get(SortDimension.ONSET.value, 0)),
            "coda_sorted": int(by_dimension.get(SortDimension.CODA.value, 0)),
        },
    }
