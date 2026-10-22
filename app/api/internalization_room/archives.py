"""The facilitator's Zerar of one team's pericope (ADR 0047)."""

from fastapi import APIRouter, Depends, Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.facilitator._deps import FacilitatorUser
from app.core.database import get_db
from app.models.internalization_room_archive import (
    ArchivedSession,
    ArchiveResponse,
    ArchiveView,
)
from app.services.internalization_room.archives import archive_pericope
from app.services.internalization_room.nudge_channel import nudge
from app.utils.stored_time import as_utc

router = APIRouter()


@router.post(
    "/facilitator/projects/{project_id}/passages/{pericope}/archive",
    response_model=ArchiveResponse,
)
async def zerar(
    project_id: str,
    user: FacilitatorUser,
    pericope: str = Path(max_length=120),
    db: AsyncSession = Depends(get_db),
) -> ArchiveResponse:
    """Archive the team's live work on this pericope, every language at once.

    Gated on the facilitator's bearer, so a tablet's credential is refused before anything is
    read. A team the caller does not facilitate is refused as one that does not exist.
    """
    archive = await archive_pericope(db, user, project_id=project_id, pericope=pericope)
    if archive is None:
        return ArchiveResponse(archived=False)
    nudge(project_id, "sessions")
    return ArchiveResponse(
        archived=True,
        archive=ArchiveView(
            id=archive.id,
            project_id=archive.project_id,
            pericope=archive.pericope,
            archived_at=as_utc(archive.archived_at).isoformat(),
            archived_by=archive.archived_by,
            sessions=[ArchivedSession(**entry) for entry in archive.snapshot],
        ),
    )
