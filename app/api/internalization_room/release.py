from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.facilitator._deps import FacilitatorUser, ReaderUser
from app.api.internalization_room._deps import device_dep, device_project_dep, linked_tablet_dep
from app.core.database import get_db
from app.core.exceptions import NothingToForce
from app.db.models.internalization_room import IRRelease, IRSession
from app.models.internalization_room import (
    ApprovedDraftView,
    ForcedReleaseResponse,
    ForceReleaseRequest,
    TeamReleaseResponse,
)
from app.services import internalization_room as room
from app.services.internalization_room.manifest import refine_manifest
from app.services.internalization_room.nudge_channel import nudge
from app.services.internalization_room.passage_force import force_passage
from app.services.internalization_room.release import (
    GROUNDED_BLOCKERS,
    InternalizationReleaseBlocked,
    approve_release,
    packet_as_read,
    release_by_version,
    was_forced,
)
from app.services.internalization_room.release_check import check_release
from app.services.internalization_room.takes import current_parts, takes_of
from app.utils.stored_time import as_utc

router = APIRouter()


def forced_answer(release: IRRelease) -> ForcedReleaseResponse:
    return ForcedReleaseResponse(
        release_id=release.packet["release_id"],
        session_id=release.session_id,
        version=release.version,
        package_sha256=release.package_sha256,
        approved_at=as_utc(release.approved_at).isoformat(),
        forced_at=(
            as_utc(release.forced_at).isoformat()
            if release.forced_at and was_forced(release.forced_by, release.forced_blockers)
            else None
        ),
    )


def check_later(background: BackgroundTasks, release: IRRelease) -> None:
    if release.release_check is None:
        background.add_task(check_release, release.id)


def approval_of(release: IRRelease) -> ApprovedDraftView:
    forced = was_forced(release.forced_by, release.forced_blockers)
    return ApprovedDraftView(
        version=release.version,
        release_id=release.packet["release_id"],
        approved_at=as_utc(release.approved_at).isoformat(),
        forced=forced,
        forced_blockers=(release.forced_blockers or []) if forced else [],
    )


@router.get("/facilitator/sessions/{session_id}/release")
async def internalization_release(
    session_id: str, user: ReaderUser, db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """The Refine **Manifest** of this session's approved draft (ADR 0086).

    A facilitator route on purpose: the manifest is the seam between apps, read by the
    person carrying the work into Refine, never by the tablet in front of the team. A draft
    that is not approved as it stands answers 409 ``DRAFT_NOT_APPROVED``: there is no
    manifest of a passage nobody approved, and the stored packet is read back by version.

    Gated on ``ReaderUser`` and not on the app-wide gate it arrived with. It was
    written against a ``CurrentUser`` that ENG-438 had already retired — the route is
    newer than that slice, so the slice never saw it — and there was no leaving it as it
    was: the name is gone, so this either tightens or re-introduces the loose gate for
    one route. Tightening is what the rest of ``/facilitator`` already does, and since ENG-1213
    every read there admits a consultant too (ADR 0058).

    Scoped with ``get_session_for_reader`` and not ``get_session``, which is what it
    arrived with. That is a defect this composition created rather than inherited: on
    ``main`` there was no per-team scoping to violate, and on this branch the route did not
    exist, so neither side was wrong and their intersection had no reviewer. Resolving the
    session by id alone handed a facilitator of one team what another team recorded.
    """
    session = await room.get_session_for_reader(db, user, session_id)
    return await refine_manifest(db, session)


@router.get("/facilitator/sessions/{session_id}/releases/{version}")
async def facilitator_release_by_version(
    session_id: str, version: int, user: ReaderUser, db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """One approved draft of this session's passage, exactly as it was approved.

    The stored packet is the contract (ADR 0014): what a **Version** means is that this
    content was approved under that number, so it is served as stored and never rebuilt, its
    check block's force derived from what it waived (ADR 0080). A forced draft reads back here
    whole — its open findings listed and `checked` false. The route beside this serves Refine
    the manifest of the approved draft, which carries none of the team's words; this is the
    record that keeps them.

    A number nobody approved is 404, and so is a session this facilitator does not
    facilitate: the scoping is the same one the read beside it does, and a release carries
    the whole of what a team recorded.
    """
    session = await room.get_session_for_reader(db, user, session_id)
    release = await release_by_version(db, session, version)
    return packet_as_read(release)


@router.post(
    "/facilitator/sessions/{session_id}/release",
    response_model=ForcedReleaseResponse,
)
async def force_internalization_release(
    session_id: str,
    payload: ForceReleaseRequest,
    user: FacilitatorUser,
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> ForcedReleaseResponse:
    """A facilitator mints this release past every blocker but a missing recording.

    The road for a team that disagrees with a finding is the raised hand, and it ends here:
    a person answered it, agreed with the team, and this is that person's code. So it is a
    route of the Desk's and not a body the team route learns to read — the tablet has no
    facilitator on it, and a flag is not a gate.

    A body that does not ask for a force is refused before the session is looked up. A route
    whose only purpose is to overrule the gate has nothing to say to a caller who did not ask
    it to, and answering about the session would mean deciding what that caller meant.

    Every blocker but ``no_rehearsal_audio`` is set aside (ADR 0075); that one refuses the
    force with the same 409 naming it the Desk's own routes always answer a refusal with. The
    team's own route answers its refusals with a 200 now (ENG-954); this one is a person's, and
    stays a 409.
    """
    if not payload.force:
        raise NothingToForce(
            "this route only mints a release past the gate, and nothing asked it to"
        )
    session = await room.get_session_for_facilitator(db, user, session_id)
    release = await approve_release(db, session, forced_by=user.id)
    check_later(background, release)
    nudge(session.project_id, "release")
    return forced_answer(release)


@router.post(
    "/facilitator/projects/{project_id}/passages/{pericope}/release",
    response_model=ForcedReleaseResponse,
)
async def force_passage_release(
    project_id: str,
    payload: ForceReleaseRequest,
    user: FacilitatorUser,
    background: BackgroundTasks,
    pericope: str = Path(max_length=120),
    db: AsyncSession = Depends(get_db),
) -> ForcedReleaseResponse:
    """«Aprovar mesmo assim (forçar)», addressed to the passage like the Zerar (ADR 0075).

    The room picks the passage's live session that holds rehearsal takes, so the Desk names
    the team and the pericope and never a session. A team the caller does not facilitate is
    refused as one that does not exist; a body that does not ask for a force is refused as on
    the route above.
    """
    if not payload.force:
        raise NothingToForce(
            "this route only mints a release past the gate, and nothing asked it to"
        )
    release = await force_passage(db, user, project_id=project_id, pericope=pericope)
    check_later(background, release)
    nudge(project_id, "release")
    return forced_answer(release)


async def _team_release_blocked(
    db: AsyncSession, session: IRSession, blockers: list[str]
) -> TeamReleaseResponse:
    """The refused half of the team's answer, its ground derived the finish route's way.

    `unheard_take_ids` and `untold_segment_id` land only where their own blocker fired — but
    that is the gate's rule, not this function's: `compose_internalization_release` appends
    `untold_stretch` exactly when `first_untold` finds one, and
    `playback_did_not_cover_the_clip` exactly when `unheard_parts` is non-empty over the current
    parts of a rehearsed session. Asking the same service helpers `terminei` already reads its
    own answer from (`app/api/internalization_room/back_translation.py`), unconditionally once
    inside the one short-circuit below, answers exactly the body the gate's own append order
    already promises; the one guard left is there only to skip the reads when nothing needs
    them. Asked fresh here rather than threaded through the gate: the gate owes codes (ADR 0026),
    and re-deriving the ground after the refusal keeps
    `compose_internalization_release`'s return type untouched.
    """
    unheard_take_ids: list[str] = []
    untold_segment_id: str | None = None
    if GROUNDED_BLOCKERS & set(blockers):
        final = await room.final_segments(db, session.id)
        untold = room.first_untold(final)
        untold_segment_id = untold.id if untold else None
        takes = await takes_of(db, session.id)
        state = room.back_translation_of(session)
        unheard_take_ids = room.unheard_parts(state, current_parts(takes), final)
    return TeamReleaseResponse(
        session_id=session.id,
        blockers=blockers,
        unheard_take_ids=unheard_take_ids,
        untold_segment_id=untold_segment_id,
    )


@router.post(
    "/sessions/{session_id}/release",
    response_model=TeamReleaseResponse,
    dependencies=[linked_tablet_dep],
)
async def approve_internalization_release(
    session_id: str,
    background: BackgroundTasks,
    project_id: str = device_project_dep,
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

    Scoped to the tablet's team like every team door: what this one writes is named by the
    team, and resolving the session by id alone would let one tablet mint a release on
    another team's passage.

    Every refusal the gate raises is a 200 naming its blockers, not a 409 (ENG-954): the
    tablet is the client that reads it, and a client that throws on a 409 learns nothing about
    which door is shut. ``InternalizationReleaseBlocked`` answers with its codes as they
    stand. The facilitator's own routes keep their 409: a person reads those, not the tablet.

    The version race is not a refusal and keeps the generic 409 `approve_release` already
    raises on a lost `IntegrityError`: it is not the exception this route catches,
    and answering it as a blocker would tell the tablet to stop asking about a passage it is
    entitled to ask about again. That 409 is a retry signal, not a gate.
    """
    session = await room.session_for_room_caller(db, session_id, project_id)
    try:
        release = await approve_release(db, session, device_id=device_id)
    except InternalizationReleaseBlocked as exc:
        return await _team_release_blocked(db, session, exc.blockers)
    check_later(background, release)
    nudge(session.project_id, "release")
    approval = approval_of(release)
    return TeamReleaseResponse(
        session_id=session_id,
        release_id=approval.release_id,
        version=approval.version,
        package_sha256=release.package_sha256,
        approved_at=approval.approved_at,
        blockers=[],
        forced=approval.forced,
        forced_blockers=approval.forced_blockers,
    )
