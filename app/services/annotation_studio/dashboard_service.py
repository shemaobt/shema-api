"""Dashboard listing: which tripod languages currently have studio data.

A language is "active" once it has any speaker, word, pair, clip or export.
Returns the tripod language plus its collection readiness so the studio
dashboard can render progress without an N+1 of per-tier calls.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.as_export import AsExport
from app.db.models.as_speaker import AsSpeaker
from app.db.models.as_tier_a import AsTierAWord
from app.db.models.as_tier_b import AsTierBPair
from app.db.models.as_tier_c import AsTierCClip
from app.db.models.auth import User
from app.db.models.language import Language
from app.models.annotation_studio import AsLanguageSummary
from app.services.annotation_studio.access import accessible_language_ids
from app.services.annotation_studio.readiness_service import compute_readiness

_DATA_MODELS = (AsSpeaker, AsTierAWord, AsTierBPair, AsTierCClip, AsExport)


async def list_active_languages(db: AsyncSession, user: User) -> list[AsLanguageSummary]:
    active_ids: set[str] = set()
    for model in _DATA_MODELS:
        rows = await db.execute(select(model.language_id).distinct())
        active_ids.update(row[0] for row in rows.all())
    if not active_ids:
        return []

    # Non-admins only see languages they're a member of.
    allowed = await accessible_language_ids(db, user)
    if allowed is not None:
        active_ids &= allowed
        if not active_ids:
            return []

    languages = (
        (
            await db.execute(
                select(Language).where(Language.id.in_(active_ids)).order_by(Language.name)
            )
        )
        .scalars()
        .all()
    )
    summaries: list[AsLanguageSummary] = []
    for language in languages:
        readiness = await compute_readiness(db, language.id)
        summaries.append(
            AsLanguageSummary(
                id=language.id,
                code=language.code,
                name=language.name,
                created_at=language.created_at,
                readiness=readiness,
            )
        )
    return summaries
