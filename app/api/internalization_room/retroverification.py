from fastapi import APIRouter, Depends, HTTPException, Path, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.facilitator._deps import ReaderUser
from app.core.database import get_db
from app.models.internalization_room import (
    PassageRetroverificationFile,
    RetroverificationFile,
    SessionRetroResponse,
)
from app.services import internalization_room as room
from app.services.internalization_room.passage_retroverification import (
    RetroverificationUnreadable,
    passage_retroverification_file,
)
from app.services.internalization_room.retroverification import retroverification_file
from app.services.internalization_room.session_retro import retro_of

router = APIRouter()


@router.get(
    "/facilitator/sessions/{session_id}/retroverificacao",
    response_model=RetroverificationFile,
)
async def read_the_retroverification_file(
    session_id: str, user: ReaderUser, db: AsyncSession = Depends(get_db)
) -> RetroverificationFile:
    """Everything the check learned about one session, for the facilitator and the consultant.

    The last segment of the path is Marcia's name for the content and carries no extension:
    nothing on this server writes files, so the file is the JSON this answers with and there
    is no download header to send.

    Scoped with ``get_session_for_reader``, like the release read beside it and for a
    reason that is wider: this carries the analyst's own words, every telling the team
    replaced and a link to every recording. A facilitator of another team is told the session
    does not exist.
    """
    session = await room.get_session_for_reader(db, user, session_id)
    return await retroverification_file(db, session)


@router.get(
    "/facilitator/projects/{project_id}/passages/{pericope}/retroverificacao",
    response_model=PassageRetroverificationFile,
)
async def read_the_passages_retroverification_file(
    project_id: str,
    response: Response,
    user: ReaderUser,
    pericope: str = Path(max_length=120),
    db: AsyncSession = Depends(get_db),
) -> PassageRetroverificationFile:
    """The file of one passage, every session of it, named after its release.

    The live sessions. A team the caller does not read is refused as one that does not exist. A
    stored telling-back that cannot be read answers 503: a file without that session would read
    as a passage nobody told.
    """
    try:
        file = await passage_retroverification_file(
            db, user, project_id=project_id, pericope=pericope
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
