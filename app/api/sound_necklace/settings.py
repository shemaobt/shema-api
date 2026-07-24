"""The project's bead granularity — one decision, one grid.

``beadSec`` defines the bead grid and is mixed into ``manifest_id``, so it is the
coordinate system the downstream pipeline and the training data are built on. It used to
be picked per session on the SPA's setup screen, which let two audios of one project land
on two incompatible grids. It is a property of the project, so it is decided here, once.

Reading is any sound-necklace role with access to the project — every screen that cuts
needs to know the grid. Deciding is ``project_admin``: it is a choice about the whole
corpus, not about the session in front of you.
"""

from typing import Any

from fastapi import APIRouter, status

from app.api.projects._deps import assert_project_access
from app.api.sound_necklace._deps import CurrentUser, Db, ProjectAdmin
from app.db.models.sound_necklace import SnProjectSettings
from app.models.sound_necklace import (
    ProjectGranularityLockedResponse,
    ProjectSettingsResponse,
    ProjectSettingsUpdate,
)
from app.services import sound_necklace_service as sn_service
from app.services.sound_necklace.get_lock_status import as_utc

router = APIRouter()

LOCKED_RESPONSE: dict[int | str, dict[str, Any]] = {
    status.HTTP_409_CONFLICT: {
        "model": ProjectGranularityLockedResponse,
        "description": (
            "The project has already been cut at its granularity, so the level cannot "
            "move. Nothing to retry: re-cutting re-derives every manifest_id already "
            "exported, which is a migration."
        ),
    }
}


def _response(
    project_id: str, row: SnProjectSettings | None, locked: bool
) -> ProjectSettingsResponse:
    if row is None:
        return ProjectSettingsResponse(project_id=project_id, locked=locked)
    return ProjectSettingsResponse(
        project_id=project_id,
        granularity_level=row.granularity_level,
        bead_sec=row.bead_sec,
        locked=locked,
        updated_at=as_utc(row.updated_at).isoformat(),
    )


@router.get("/projects/{project_id}/settings", response_model=ProjectSettingsResponse)
async def get_project_settings(
    project_id: str, db: Db, user: CurrentUser
) -> ProjectSettingsResponse:
    """The granularity this project cuts at, and whether it can still change."""
    await assert_project_access(db, user, project_id)
    row, locked = await sn_service.get_project_settings(db, project_id)
    return _response(project_id, row, locked)


@router.put(
    "/projects/{project_id}/settings",
    response_model=ProjectSettingsResponse,
    responses=LOCKED_RESPONSE,
)
async def set_project_settings(
    project_id: str, payload: ProjectSettingsUpdate, db: Db, user: ProjectAdmin
) -> ProjectSettingsResponse:
    """Decide the project's bead granularity, while it is still decidable.

    ``ProjectAdmin`` gates the role; ``assert_project_access`` still runs on top, or an
    admin of one project could set another's grid.

    The payload carries a LEVEL and nothing else. The resolved duration comes from each
    audio's acousteme (``granularity_frames[level] * hop_sec``), so it is not knowable
    until an audio is cut — the project's first session stamps it.
    """
    await assert_project_access(db, user, project_id)
    row, locked = await sn_service.set_project_granularity(
        db, project_id, payload.granularity_level, user.id
    )
    return _response(project_id, row, locked)
