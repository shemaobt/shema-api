from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.auth import User
from app.db.models.resource_request import RRRequest, RRRequestType
from app.models.resource_request import RequestDraftIn
from app.services.resource_request.create_draft import create_draft


async def start_request(
    db: AsyncSession,
    request_type: RRRequestType,
    user: User,
    app_key: str,
    project_id: str | None = None,
) -> RRRequest:
    """*Iniciar* — open the project's instance, empty, with the caller holding the pen.

    GATE-04 D6 (OBT-519): a member presses *Iniciar* and from then on only they write the
    instance until it is submitted or cancelled (BE-25, OBT-534). It is ``create_draft`` with
    an empty document, and deliberately nothing more: the project check (a member names one of
    their projects, the Admin names any), ``started_by`` and the one-open-per-project refusal
    all live there, so the two doors cannot disagree about any of them.

    The project arrives as a parameter and not from the session: the server keeps no context in
    a session (``create_draft._project_for`` says why), so the pass code's project (OBT-527) is
    checked against the caller's live memberships every time it is named.
    """
    return await create_draft(
        db, RequestDraftIn(request_type=request_type), user, app_key, project_id
    )
