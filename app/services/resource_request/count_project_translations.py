"""How many translation requests a project has submitted — the count OBT-508 limits on.

Karina, 21/sep/2026: *"uma por equipe"*. GATE-04 D1 gave the team its subject — the members of
a PME project — and D6 (Daniel, 23/sep) made it **one per project**. This is the number that
rule reads: submitted ``traducao`` requests of the project, counted on ``shema_project_id``
(BE-19, OBT-520). What the limit refuses, and with which status, is OBT-508's and OBT-534's
to decide; this answers the count and nothing more.

**Submitted only.** A draft is an instance still being written, and the open instance is
OBT-534's lock, not this count. **A revision counts once with its original**: it is a new
request linked to the evaluated snapshot, so ``revision_of_id IS NULL`` keeps a project that
was asked to revise from reading as two translations.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.resource_request import RRRequest, RRRequestType


async def count_project_translations(db: AsyncSession, project_id: str) -> int:
    """Submitted translation requests of ``project_id``, revisions not counted twice."""
    stmt = select(func.count()).where(
        RRRequest.shema_project_id == project_id,
        RRRequest.request_type == RRRequestType.TRADUCAO,
        RRRequest.submitted_at.is_not(None),
        RRRequest.revision_of_id.is_(None),
    )
    return int((await db.execute(stmt)).scalar_one())
