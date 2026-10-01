from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.project import Project
from app.services.project.get_project_or_404 import get_project_or_404

_UNSET: object = object()


async def update_project_location(
    db: AsyncSession,
    project_id: str,
    *,
    latitude: float | None | object = _UNSET,
    longitude: float | None | object = _UNSET,
    location_display_name: str | None | object = _UNSET,
) -> Project:
    """Write every location field it is handed, ``None`` included; leave out the rest.

    ``None`` used to mean *leave as is*, so the console's *Clear location* answered 200 and
    the old point came back on the next load (shemaobt/shema-api#566). Clearing is a real
    operation now that a location may be only a name, so *not handed* is the sentinel and
    ``None`` is a value. Whether the coordinates arrive as a whole pair on the globe is the
    request model's to refuse, before anything reaches here.
    """
    project = await get_project_or_404(db, project_id)
    if latitude is not _UNSET:
        project.latitude = latitude  # type: ignore[assignment]
    if longitude is not _UNSET:
        project.longitude = longitude  # type: ignore[assignment]
    if location_display_name is not _UNSET:
        project.location_display_name = location_display_name  # type: ignore[assignment]
    await db.commit()
    await db.refresh(project)
    return project
