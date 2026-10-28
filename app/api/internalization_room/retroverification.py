from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.facilitator._deps import ReaderUser
from app.core.database import get_db
from app.models.internalization_room import (
    PassageRetroverificationFile,
    SessionRetroResponse,
)
from app.services import internalization_room as room
from app.services.internalization_room.check_block import passage_retro_url
from app.services.internalization_room.passage_retroverification import (
    RetroverificationUnreadable,
    passage_retroverification_file,
)
from app.services.internalization_room.session_retro import retro_of

router = APIRouter()


@router.get("/facilitator/sessions/{session_id}/retroverificacao", status_code=307)
async def redirect_to_the_passages_retroverification_file(
    session_id: str, user: ReaderUser, db: AsyncSession = Depends(get_db)
) -> RedirectResponse:
    """Where old links to a session's file land: the file of its passage, no file built here.

    Scoped with ``get_session_for_reader``, so a facilitator of another team is told the
    session does not exist. An archived session lands on its archive's file.
    """
    session = await room.get_session_for_reader(db, user, session_id)
    return RedirectResponse(passage_retro_url(session), status_code=307)


@router.get(
    "/facilitator/projects/{project_id}/passages/{pericope}/retroverificacao",
    response_model=PassageRetroverificationFile,
)
async def read_the_passages_retroverification_file(
    project_id: str,
    response: Response,
    user: ReaderUser,
    pericope: str = Path(max_length=120),
    archive: str | None = Query(default=None, min_length=1),
    db: AsyncSession = Depends(get_db),
) -> PassageRetroverificationFile:
    """The file of one passage, every session of it, named after its release.

    The live sessions, or those of the Archive named in ``archive``. A team the caller does not
    read is refused as one that does not exist. A stored telling-back that cannot be read
    answers 503: a file without that session would read as a passage nobody told.
    """
    try:
        file = await passage_retroverification_file(
            db, user, project_id=project_id, pericope=pericope, archive_id=archive
        )
    except RetroverificationUnreadable as unreadable:
        raise HTTPException(
            status_code=503, detail="The retroverification file cannot be read now; try again"
        ) from unreadable
    response.headers["content-disposition"] = (
        f'attachment; filename="{file.release_id}-retroverificacao.json"'
    )
    return file


@router.get(
    "/facilitator/sessions/{session_id}/retro",
    response_model=SessionRetroResponse,
)
async def read_the_retro(
    session_id: str, user: ReaderUser, db: AsyncSession = Depends(get_db)
) -> SessionRetroResponse:
    session = await room.get_session_for_reader(db, user, session_id)
    return await retro_of(db, session)
