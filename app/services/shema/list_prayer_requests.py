"""The prayer wall — every authorized request in the caller's reach, ready to leave.

**Derived on every call and stored nowhere**, which is what makes a withdrawal free
(``docs/shema.md`` §5.6): a request moved back to ``coordenacao``, or a need unshared, is absent
from the next read with no cleanup step, because there is no copy to clean. The Prayer Pulse is
this list rendered (``generate_prayer_pulse.py``), so the same property holds for every Pulse
generated after the withdrawal — and cannot reach one already sent, which the file says.

**Three owners, and this file is none of them.** The projects are ``_scope.py``'s
``visible_projects``; what may leave is ``_consent.authorized_requests_by_project``; the place is
reduced by :class:`~app.models.shema_prayer.PrayerRequestEntry`, a leaving shape validated off the
row and built for nobody, which is ``outside`` — the wall is an output path, so the console's
coordinator reads the region of a sensitive project here as everybody else does, exactly as the
console's own ``buildPrayerRequests`` reads ``getLeavingLocation``.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.shema import ShemaProject
from app.models.shema_prayer import PrayerRequestEntry
from app.services.shema._consent import authorized_requests_by_project
from app.services.shema._scope import RegionScope, visible_projects


def _newest_first(entry: PrayerRequestEntry) -> date:
    return entry.date or date.min


async def list_prayer_requests(db: AsyncSession, scope: RegionScope) -> list[PrayerRequestEntry]:
    """The wall inside ``scope``, newest first — FE-44 §9.6's ``GET /prayer/requests``.

    ``scope`` is positional with no default, for ``list_projects``' reason. Each project's row is
    validated into the shape once and each request copied onto it, so the flag is read by the
    boundary once per project. The order is FE-44's — by the entry's day, descending, and stable
    among equals — and an undated entry sorts last.
    """
    projects = list((await db.execute(visible_projects(scope).order_by(ShemaProject.id))).scalars())
    authorized = await authorized_requests_by_project(db, projects)

    entries: list[PrayerRequestEntry] = []
    for project in projects:
        requests = authorized[project.id]
        if not requests:
            continue
        place = PrayerRequestEntry.model_validate(project)
        entries.extend(
            place.model_copy(
                update={
                    "id": request.id,
                    "project_id": request.project_id,
                    "text": request.text,
                    "prayer_source": request.source,
                    "answered": request.answered,
                    "date": request.day,
                }
            )
            for request in requests
        )
    return sorted(entries, key=_newest_first, reverse=True)
