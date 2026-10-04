from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.facilitator._deps import FacilitatorUser
from app.core.database import get_db
from app.models.internalization_room import RetroverificationFile
from app.services import internalization_room as room
from app.services.internalization_room.retroverification import retroverification_file

router = APIRouter()


@router.get(
    "/facilitator/sessions/{session_id}/retroverificacao",
    response_model=RetroverificationFile,
)
async def read_the_retroverification_file(
    session_id: str, user: FacilitatorUser, db: AsyncSession = Depends(get_db)
) -> RetroverificationFile:
    """Everything the check learned about one session, for the facilitator and the consultant.

    The last segment of the path is Marcia's name for the content and carries no extension:
    nothing on this server writes files, so the file is the JSON this answers with and there
    is no download header to send.

    Scoped with ``get_session_for_facilitator``, like the release read beside it and for a
    reason that is wider: this carries the analyst's own words, every telling the team
    replaced and a link to every recording. A facilitator of another team is told the session
    does not exist.
    """
    session = await room.get_session_for_facilitator(db, user, session_id)
    return await retroverification_file(db, session)
