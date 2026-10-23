from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.internalization_room._deps import device_dep, device_project_dep, linked_tablet_dep
from app.core.database import get_db
from app.db.models.internalization_room import IRExternalCheck
from app.models.internalization_room import (
    ExternalCheckFrase,
    ExternalCheckPart,
    ExternalCheckView,
)
from app.services import internalization_room as room
from app.services.internalization_room.external_check import open_the_external_check
from app.utils.stored_time import as_utc

router = APIRouter()


def external_check_view(check: IRExternalCheck) -> ExternalCheckView:
    return ExternalCheckView(
        check_id=check.id,
        version=check.version,
        opened_at=as_utc(check.opened_at).isoformat(),
        takes=[ExternalCheckPart(**take) for take in check.takes],
        frases=[ExternalCheckFrase(**frase) for frase in check.frases],
    )


@router.post(
    "/sessions/{session_id}/external-check/open",
    response_model=ExternalCheckView,
    dependencies=[linked_tablet_dep],
    responses={
        409: {"description": "DRAFT_NOT_APPROVED: the session's draft does not stand approved"}
    },
)
async def open_the_external_check_route(
    session_id: str,
    project_id: str = device_project_dep,
    device_id: str = device_dep,
    db: AsyncSession = Depends(get_db),
) -> ExternalCheckView:
    """The team opens the **Checagem externa** of the version its draft stands approved under.

    A team door with no code: the facilitator has no control over the check. Every open of one
    version answers the same record, from any tablet of the team, so a second tap is a read and
    the answer carries no flag telling the two apart. Nothing gates, locks or closes it, because
    the version does that work (ADR 0082): a draft that re-opens stops answering here until it
    is approved again, and that version opens a record of its own.

    409 ``DRAFT_NOT_APPROVED`` only for a draft that does not stand approved (ADR 0071). The
    server log line of the first open is the only notice; the Desk learns of it on its own read.
    """
    session = await room.session_for_room_caller(db, session_id, project_id)
    return external_check_view(await open_the_external_check(db, session, device_id=device_id))
