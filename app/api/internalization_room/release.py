from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.facilitator._deps import FacilitatorUser
from app.api.internalization_room._deps import device_project_dep, room_caller_dep
from app.core.database import get_db
from app.models.internalization_room import ReleaseResponse
from app.services import internalization_room as room
from app.services.internalization_room.release import (
    approve_release,
    build_internalization_release,
)
from app.utils.stored_time import as_utc

router = APIRouter()


@router.get("/facilitator/sessions/{session_id}/release")
async def internalization_release(
    session_id: str, user: FacilitatorUser, db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """The Refine handoff artifact for one finished session, built fail-closed.

    A facilitator route on purpose: the release is the seam between apps, read by the
    person carrying the work into Refine, never by the tablet in front of the team. A
    session that is not ready answers 409 with the blockers named — a partial artifact
    would look downstream exactly like a finished one.

    Gated on ``FacilitatorUser`` and not on the app-wide gate it arrived with. It was
    written against a ``CurrentUser`` that ENG-438 had already retired — the route is
    newer than that slice, so the slice never saw it — and there was no leaving it as it
    was: the name is gone, so this either tightens or re-introduces the loose gate for
    one route. Tightening is what the rest of ``/facilitator`` already does, and what the
    docstring above says this route is.

    Scoped with ``get_session_for_facilitator`` and not ``get_session``, which is what it
    arrived with. That is a defect this composition created rather than inherited: on
    ``main`` there was no per-team scoping to violate, and on this branch the route did not
    exist, so neither side was wrong and their intersection had no reviewer. Resolving the
    session by id alone handed a facilitator of one team the handoff artifact of another —
    every finding, every quote, the whole of what that team recorded.
    """
    session = await room.get_session_for_facilitator(db, user, session_id)
    return await build_internalization_release(db, session)


@router.post(
    "/sessions/{session_id}/release",
    response_model=ReleaseResponse,
    dependencies=[room_caller_dep],
)
async def approve_internalization_release(
    session_id: str,
    project_id: str | None = device_project_dep,
    db: AsyncSession = Depends(get_db),
) -> ReleaseResponse:
    """The team says this passage is its final draft, and the draft gets a number.

    A team route because the team is who approves; the facilitator route beside it stays a
    read. It carries no body: the version is the room's to allocate and never the caller's
    to send, and a number arriving from a tablet that has been offline for a day is a
    collision waiting for the index to catch it.

    Scoped with `get_session_for_room_caller`, which the other team routes do not use: what
    this one writes is named by the team, and resolving the session by id alone would let
    one tablet mint a release on another team's passage.
    """
    session = await room.get_session_for_room_caller(db, session_id, project_id)
    release = await approve_release(db, session)
    return ReleaseResponse(
        release_id=release.id,
        session_id=release.session_id,
        version=release.version,
        package_sha256=release.package_sha256,
        finalized_at=as_utc(release.finalized_at).isoformat(),
    )
