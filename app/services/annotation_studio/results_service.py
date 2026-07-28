from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.as_analysis_result import AsAnalysisResult
from app.models.annotation_studio import PresignedUpload
from app.services.annotation_studio import storage
from app.services.annotation_studio.common import get_or_404
from app.services.annotation_studio.naming import result_plot_key
from app.services.language.get_language_or_404 import get_language_or_404


async def create_result(
    db: AsyncSession,
    language_id: str,
    results_json: dict,
    export_id: str | None = None,
) -> AsAnalysisResult:
    await get_language_or_404(db, language_id)
    recommended = results_json.get("recommended_layer")
    tiers = results_json.get("tiers")
    result = AsAnalysisResult(
        language_id=language_id,
        export_id=export_id,
        recommended_layer=int(recommended) if recommended is not None else None,
        tiers=",".join(tiers) if isinstance(tiers, list) else tiers,
        summary_json=json.dumps(results_json),
        plot_keys_json=json.dumps({}),
    )
    db.add(result)
    await db.commit()
    await db.refresh(result)
    return result


async def list_results(db: AsyncSession, language_id: str) -> list[AsAnalysisResult]:
    rows = await db.execute(
        select(AsAnalysisResult)
        .where(AsAnalysisResult.language_id == language_id)
        .order_by(AsAnalysisResult.created_at.desc())
    )
    return list(rows.scalars().all())


async def get_result(db: AsyncSession, result_id: str) -> AsAnalysisResult:
    return await get_or_404(db, AsAnalysisResult, result_id, "Result")


def plot_urls(result: AsAnalysisResult) -> dict[str, str]:
    keys = json.loads(result.plot_keys_json) if result.plot_keys_json else {}
    return {name: storage.presign_get(key) for name, key in keys.items()}


async def presign_plot(
    db: AsyncSession,
    result_id: str,
    name: str,
    content_type: str,
) -> PresignedUpload:
    result = await get_result(db, result_id)
    language = await get_language_or_404(db, result.language_id)
    key = result_plot_key(language.code, result.id, name)
    keys = json.loads(result.plot_keys_json) if result.plot_keys_json else {}
    keys[name] = key
    result.plot_keys_json = json.dumps(keys)
    await db.commit()
    return storage.presign_put(key, content_type)
