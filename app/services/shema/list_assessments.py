"""The assessment history of one project — the read half, and the narrower door it goes through.

``read_record.py`` already joins this history into the record, and this is not a second copy of
that query: it is the same history behind **the narrower gate**, for the screen whose whole
subject is the readings rather than the project. The issue's fourth line is that read access to
an assessment is at least as narrow as the record's and narrower where the product says so, and
``_health_audience.py`` is where that question is answered for both halves at once.

**Two gates, in this order, and the order is the message.** The region scope first, so a project
outside the caller's reach is refused exactly as one that does not exist is — the indistinguishable
404 ``_scope.py`` argues for, because a Shemá slug names a place. The audience second, as a 403,
because by then the only fact in the answer is the caller's own grant.

Oldest first, keyed the way the record's read keys it, so the last entry a client sees is the one
the record's flat fields project.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.auth import User
from app.db.models.shema_health import ShemaHealthAssessment
from app.models.shema_record import ShemaHealthAssessmentEntry
from app.services.shema._health_audience import require_reads_assessments
from app.services.shema._scope import RegionScope
from app.services.shema.get_project import get_project


async def list_assessments(
    db: AsyncSession,
    scope: RegionScope,
    project_id: str,
    *,
    user: User,
    app_key: str,
) -> list[ShemaHealthAssessmentEntry]:
    """Every reading of one project's health, oldest first, or a refusal.

    ``scope`` is positional and has no default: a keyword with a permissive default is how a
    scope stops being applied, and there is no unscoped spelling of this call.
    """
    project = await get_project(db, scope, project_id, user=user, operation="list_assessments")
    await require_reads_assessments(db, user, app_key)

    stmt = (
        select(ShemaHealthAssessment)
        .where(ShemaHealthAssessment.project_id == project.id)
        .order_by(ShemaHealthAssessment.assessment_date, ShemaHealthAssessment.created_at)
    )
    return [
        ShemaHealthAssessmentEntry.model_validate(row) for row in (await db.execute(stmt)).scalars()
    ]
