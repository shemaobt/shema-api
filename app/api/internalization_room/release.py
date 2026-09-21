from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.facilitator._deps import FacilitatorUser
from app.api.internalization_room._deps import device_dep, device_project_dep, room_caller_dep
from app.core.database import get_db
from app.core.exceptions import NothingToForce, ReleaseWithoutProject
from app.db.models.internalization_room import IRSession
from app.models.internalization_room import (
    ForcedReleaseResponse,
    ForceReleaseRequest,
    TeamReleaseResponse,
)
from app.services import internalization_room as room
from app.services.internalization_room.release import (
    GROUNDED_BLOCKERS,
    InternalizationReleaseBlocked,
    approve_release,
    build_internalization_release,
    release_by_version,
)
from app.services.internalization_room.takes import current_parts, takes_of
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


@router.get("/facilitator/sessions/{session_id}/releases/{version}")
async def facilitator_release_by_version(
    session_id: str, version: int, user: FacilitatorUser, db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """One approved draft of this session's passage, exactly as it was approved.

    The stored packet is the contract (ADR 0014): what a **Version** means is that this
    content was approved under that number, so it is served verbatim and never rebuilt. A
    forced draft reads back here whole — its open findings listed and `checked` false — which
    is the one thing the route beside this cannot do. That one is a live rebuild under the
    whole list, and on a session a facilitator had to force it answers with the refusal
    rather than with the draft the Desk minted.

    A number nobody approved is 404, and so is a session this facilitator does not
    facilitate: the scoping is the same one the read beside it does, and a release carries
    the whole of what a team recorded.
    """
    session = await room.get_session_for_facilitator(db, user, session_id)
    release = await release_by_version(db, session, version)
    return release.packet


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

    Only the two codes of ``FORCEABLE_BLOCKERS`` are set aside; the rest refuse the force with
    the same 409 naming them the Desk's own routes always answer a refusal with. The team's own
    route answers those with a 200 now (ENG-954); this one is a person's, and stays a 409.
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


async def _team_release_blocked(
    db: AsyncSession, session: IRSession, blockers: list[str]
) -> TeamReleaseResponse:
    """The refused half of the team's answer, its ground derived the finish route's way.

    `untold_take_ids`, `unheard_take_ids` and `untold_segment_id` land only where their own
    blocker fired — but that is the gate's rule, not this function's:
    `compose_internalization_release` appends `untold_stretch` exactly when `first_untold`
    finds one, `untold_part` exactly when `untold_parts` is non-empty, and
    `playback_did_not_cover_the_clip` exactly when `unheard_parts` is non-empty over a
    rehearsed part. Asking the same service helpers `terminei` already reads its own answer
    from (`app/api/internalization_room/back_translation.py`), unconditionally once inside the
    one short-circuit below, answers exactly the body the gate's own append order already
    promises; the one guard left is there only to skip the `takes_of` query when nothing needs
    it. Asked fresh here rather than threaded through the gate: the gate owes codes (ADR 0026),
    and re-deriving the ground after the refusal keeps
    `compose_internalization_release`'s return type untouched.
    """
    untold_take_ids: list[str] = []
    unheard_take_ids: list[str] = []
    untold_segment_id: str | None = None
    if GROUNDED_BLOCKERS & set(blockers):
        final = await room.final_segments(db, session.id)
        untold = room.first_untold(final)
        untold_segment_id = untold.id if untold else None
        rehearsed = room.rehearsed_parts(final)
        if "untold_part" in blockers:
            takes = await takes_of(db, session.id)
            untold_take_ids = [
                part.id for part in room.untold_parts(current_parts(takes), rehearsed)
            ]
        state = room.back_translation_of(session)
        unheard_take_ids = room.unheard_parts(state, rehearsed)
    return TeamReleaseResponse(
        session_id=session.id,
        blockers=blockers,
        untold_take_ids=untold_take_ids,
        unheard_take_ids=unheard_take_ids,
        untold_segment_id=untold_segment_id,
    )


@router.post(
    "/sessions/{session_id}/release",
    response_model=TeamReleaseResponse,
    dependencies=[room_caller_dep],
)
async def approve_internalization_release(
    session_id: str,
    project_id: str | None = device_project_dep,
    device_id: str = device_dep,
    db: AsyncSession = Depends(get_db),
) -> TeamReleaseResponse:
    """The team says this passage is its final draft, and the draft gets a number — or refuses.

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

    Every refusal the gate raises is a 200 naming its blockers, not a 409 (ENG-954): the
    tablet is the client that reads it, and a client that throws on a 409 learns nothing about
    which door is shut. ``InternalizationReleaseBlocked`` answers with its codes as they
    stand; a session on the shared key answers ``["no_project"]``, a literal here because the
    fact is the route's own and the gate never sees a project-less session (``approve_release``
    refuses it first). The facilitator's own routes keep their 409: a person reads those, not
    the tablet.

    The version race is not a refusal and keeps the generic 409 `approve_release` already
    raises on a lost `IntegrityError`: it is not one of the two exceptions this route catches,
    and answering it as a blocker would tell the tablet to stop asking about a passage it is
    entitled to ask about again. That 409 is a retry signal, not a gate.
    """
    session = await room.get_session_for_room_caller(db, session_id, project_id)
    try:
        release = await approve_release(db, session, device_id=device_id)
    except ReleaseWithoutProject:
        return TeamReleaseResponse(session_id=session_id, blockers=["no_project"])
    except InternalizationReleaseBlocked as exc:
        return await _team_release_blocked(db, session, exc.blockers)
    return TeamReleaseResponse(
        session_id=session_id,
        release_id=release.id,
        version=release.version,
        package_sha256=release.package_sha256,
        approved_at=as_utc(release.approved_at).isoformat(),
        blockers=[],
    )
