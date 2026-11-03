"""The facilitator's Zerar of one team's pericope (ADR 0047)."""

from fastapi import APIRouter, Depends, Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.facilitator._deps import FacilitatorUser, ReaderUser
from app.core.database import get_db
from app.db.models.internalization_room import IRArchive
from app.models.internalization_room_archive import (
    ArchivedSession,
    ArchiveList,
    ArchiveResponse,
    ArchiveView,
)
from app.services.internalization_room.archives import archive_pericope, archives_of
from app.services.internalization_room.nudge_channel import nudge
from app.utils.stored_time import as_utc

router = APIRouter()


def _view(archive: IRArchive) -> ArchiveView:
    return ArchiveView(
        id=archive.id,
        project_id=archive.project_id,
        pericope=archive.pericope,
        archived_at=as_utc(archive.archived_at).isoformat(),
        archived_by=archive.archived_by,
        sessions=[ArchivedSession(**entry) for entry in archive.snapshot],
    )


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
        archive=_view(archive),
    )


@router.get(
    "/facilitator/projects/{project_id}/passages/{pericope}/archives",
    response_model=ArchiveList,
)
async def archives(
    project_id: str,
    user: ReaderUser,
    pericope: str = Path(max_length=120),
    db: AsyncSession = Depends(get_db),
) -> ArchiveList:
    """The team's archives of this pericope, newest first, as each Zerar answered.

    A consultant reads any team; a facilitator reads their own, and another team is refused as
    one that does not exist.
    """
    found = await archives_of(db, user, project_id=project_id, pericope=pericope)
    return ArchiveList(archives=[_view(archive) for archive in found])
