"""The coordination's queue — every sensitive project's request waiting for its release (OBT-575).

**Three owners, and this file is none of them**, as on the wall beside it: the caller's reach is
the regions it coordinates (``_prayer_review.refuse_unless_coordination``), which requests wait is
``_consent.awaiting_review_by_project``, and the language's name is ``_redaction``'s, read as the
coordination reads it. Derived on every call and stored nowhere, so a request the team stops
sharing, or one released by another coordinator, is absent from the next read.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.auth import User
from app.db.models.shema import ShemaProject
from app.models.shema_prayer import PrayerReviewEntry
from app.models.shema_privacy import ShemaReader
from app.services.shema._consent import awaiting_review_by_project
from app.services.shema._prayer_review import refuse_unless_coordination
from app.services.shema._redaction import language_name_for
from app.services.shema._scope import Readership, visible_projects


async def list_prayer_review(
    db: AsyncSession, readership: Readership, *, user: User
) -> list[PrayerReviewEntry]:
    """The requests waiting in the regions this caller coordinates, by project and then in order."""
    coordination = refuse_unless_coordination(readership, user=user, operation="list_prayer_review")
    projects = list(
        (await db.execute(visible_projects(coordination).order_by(ShemaProject.id))).scalars()
    )
    waiting = await awaiting_review_by_project(db, projects)
    return [
        PrayerReviewEntry(
            id=request.id,
            project_id=request.project_id,
            need_id=request.need_id,
            language=language_name_for(project, ShemaReader.COORDINATION),
            source=request.source,
            text=request.text,
        )
        for project in projects
        for request in waiting[project.id]
    ]
