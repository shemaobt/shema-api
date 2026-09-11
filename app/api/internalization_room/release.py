from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.facilitator._deps import FacilitatorUser
from app.api.internalization_room._deps import device_dep, device_project_dep, room_caller_dep
from app.core.database import get_db
from app.core.exceptions import NothingToForce
from app.models.internalization_room import (
    ForcedReleaseResponse,
    ForceReleaseRequest,
    ReleaseResponse,
)
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
    "/facilitator/sessions/{session_id}/release",
    response_model=ForcedReleaseResponse,
)
async def force_internalization_release(
    session_id: str,
    payload: ForceReleaseRequest,
    user: FacilitatorUser,
    db: AsyncSession = Depends(get_db),
) -> ForcedReleaseResponse:
    """A facilitator mints this release past an open finding or an unheard part.

    The road for a team that disagrees with a finding is the raised hand, and it ends here:
    a person answered it, agreed with the team, and this is that person's code. So it is a
    route of the Desk's and not a body the team route learns to read — the tablet has no
    facilitator on it, and a flag is not a gate.

    A body that does not ask for a force is refused before the session is looked up. A route
    whose only purpose is to overrule the gate has nothing to say to a caller who did not ask
    it to, and answering about the session would mean deciding what that caller meant.

    Only the two codes of ``FORCEABLE_BLOCKERS`` are set aside; the rest refuse the force the
    way they refuse the team, and the answer is the same 409 naming them.
    """
    if not payload.force:
        raise NothingToForce(
            "this route only mints a release past the gate, and nothing asked it to"
        )
    session = await room.get_session_for_facilitator(db, user, session_id)
    release = await approve_release(db, session, forced_by=user.id)
    return ForcedReleaseResponse(
        release_id=release.id,
        session_id=release.session_id,
        version=release.version,
        package_sha256=release.package_sha256,
        approved_at=as_utc(release.approved_at).isoformat(),
        forced_at=as_utc(release.forced_at).isoformat() if release.forced_at else None,
    )


@router.post(
    "/sessions/{session_id}/release",
    response_model=ReleaseResponse,
    dependencies=[room_caller_dep],
)
async def approve_internalization_release(
    session_id: str,
    project_id: str | None = device_project_dep,
    device_id: str = device_dep,
    db: AsyncSession = Depends(get_db),
) -> ReleaseResponse:
    """The team says this passage is its final draft, and the draft gets a number.

    A team route because the team is who approves; the facilitator routes beside it read the
    packet and force one. It carries no body: the version is the room's to allocate and never
    the caller's to send, and a number arriving from a tablet that has been offline for a day
    is a collision waiting for the index to catch it. Nor does it read ``force`` — a body
    carrying it changes nothing here, because the tablet has no facilitator on it.

    The device is stamped the way every other team write stamps it. This was the one that did
    not, which left the act that numbers a draft for the external check as the only thing a
    team does with nothing saying which tablet did it.

    Scoped with `get_session_for_room_caller`, which the other team routes do not use: what
    this one writes is named by the team, and resolving the session by id alone would let
    one tablet mint a release on another team's passage.
    """
    session = await room.get_session_for_room_caller(db, session_id, project_id)
    release = await approve_release(db, session, device_id=device_id)
    return ReleaseResponse(
        release_id=release.id,
        session_id=release.session_id,
        version=release.version,
        package_sha256=release.package_sha256,
        approved_at=as_utc(release.approved_at).isoformat(),
    )
