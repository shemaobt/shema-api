"""The audio the room is not allowed to lose.

What the team says during the conversation is thrown away once it has been transcribed —
there the record is the text. A rehearsal take and the chunks of a back translation are the
opposite: the recording is the work, and a tablet that breaks with them still on it takes the
session with it.
"""

from functools import partial

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.facilitator._deps import ReaderUser
from app.api.internalization_room._deps import device_dep, device_project_dep, linked_tablet_dep
from app.core.database import get_db
from app.core.exceptions import ValidationError
from app.db.models.internalization_room import IRGrain, IRSession, IRTake, IRTakeKind
from app.models.internalization_room import (
    GrainSwitchRequest,
    MotherTongueTakesResponse,
    SentRecordingTime,
    TakeDownloadsResponse,
    TakeResponse,
    TakesResponse,
)
from app.services import internalization_room as room
from app.services.internalization_room.approved_draft import (
    refuse_a_keep_that_reopens_the_approved_draft,
)
from app.services.internalization_room.coverage import refuse_a_panorama
from app.services.internalization_room.nudge_channel import nudge
from app.services.internalization_room.scene_rehearsals import (
    refuse_an_origin_that_is_no_scene_rehearsal,
)
from app.services.internalization_room.session_takes import mother_tongue_takes_of
from app.services.internalization_room.take_downloads import take_downloads_of
from app.services.internalization_room.takes import (
    LONGEST_TAKE_MS,
    TakeStore,
    current_parts,
    grain_in_force,
    listen_url,
    of_the_grain_left_behind,
    set_aside_moment,
    store_take,
    take_for_reader,
    take_in_session,
    take_store,
    takes_of,
    the_take_this_keep_already_is,
)
from app.utils.stored_time import as_utc

router = APIRouter()


def _view(take: IRTake) -> TakeResponse:
    return TakeResponse(
        take_id=take.id,
        session_id=take.session_id,
        kind=take.kind.value,
        scope=take.scope,
        sha256=take.sha256,
        size_bytes=take.size_bytes,
        verified=take.verified_at is not None,
        ordinal=take.ordinal,
        pass_number=take.pass_number,
        origin=take.origin,
        pericope=take.pericope,
        recorded_at=as_utc(take.recorded_at).isoformat(),
        duration_ms=take.duration_ms,
        set_aside_at=set_aside_moment(take),
    )


async def _listing(db: AsyncSession, session: IRSession) -> TakesResponse:
    takes = await takes_of(db, session.id)
    grain = grain_in_force(session, current_parts(takes))
    return TakesResponse(
        session_id=session.id,
        takes=[_view(take) for take in takes],
        grain=None if grain is None else grain.value,
    )


def _kind(raw: str) -> IRTakeKind:
    try:
        return IRTakeKind(raw)
    except ValueError:
        raise ValidationError(f"Unknown take kind: {raw}") from None


@router.post(
    "/sessions/{session_id}/takes",
    response_model=TakeResponse,
    dependencies=[linked_tablet_dep],
    responses={
        409: {
            "description": "`DRAFT_APPROVED`: a joined or swapped part, or a whole take over a "
            "joined recording, over an approved draft the team did not arm the tap to re-open"
        }
    },
)
async def keep_take(
    session_id: str,
    kind: str = Form(...),
    scope: str = Form(...),
    pass_number: int | None = Form(default=None, ge=1),
    chunk_index: int | None = Form(default=None, ge=0),
    origin: str | None = Form(
        default=None,
        description=(
            "The id of the team's scene rehearsal of this passage the part was joined from, "
            "when the tablet laid one in as this part. A recording with any current part "
            "carrying one is joined: «terminei» refuses a part with no translated frase on "
            "it, and the listen may check it with no tap. Absent on a part recorded as itself."
        ),
    ),
    recorded_at: SentRecordingTime | None = Form(
        default=None,
        description=(
            "When the recording stopped, by the tablet's clock, with its offset. It is the "
            "take's recording time however late the upload lands; a joined part keeps the "
            "server's clock instead, and this only measures how far the tablet's is off."
        ),
    ),
    duration_ms: int | None = Form(
        default=None,
        ge=0,
        le=LONGEST_TAKE_MS,
        description=(
            "The length of the file sent, read from the file itself. Refused with "
            "TAKE_DURATION_DIFFERS when more than 100 ms from the length the server measures."
        ),
    ),
    sha256: str | None = Form(
        default=None,
        description=(
            "The sha256 of the bytes sent, in hex. Refused with TAKE_FINGERPRINT_DIFFERS when "
            "it is not theirs; nothing is stored."
        ),
    ),
    reopens_the_approved_draft: bool = Form(
        default=False,
        description=(
            "True when the team armed the tap that re-opens its approved draft (ADR 0081). "
            "Without it, over an approved draft, a joined or swapped part and a whole take over "
            "a joined recording are refused DRAFT_APPROVED; a part recorded on the recording "
            "screen never needs it."
        ),
    ),
    file: UploadFile = File(...),
    device_id: str = device_dep,
    project_id: str = device_project_dep,
    db: AsyncSession = Depends(get_db),
) -> TakeResponse:
    """Store one take and answer with where it landed.

    The app keeps its local copy until this answers, and re-sends the same bytes after a lost
    connection without checking anything first. That is safe because the key is the hash of
    the audio: a repeat lands on the same object and returns the row that already exists.

    A retro take kept here carries no ordinal, whatever the form says. The number the tablet
    sends is its own position in its own list, and the ordinal is the stretch's — written
    where a stretch is captured, which this route never does. A rehearsal take keeps the
    number it was sent with: that one is a part of the passage, not a telling of a stretch.

    **A rehearsal take under a number the session already has is that part recorded again**,
    and this call is the whole of that verb: the app says which part it is recording by the
    number it sends, so nothing else has to be asked of it. What follows from it — which
    stretches stop counting, which findings go with them, and that the check starts over — is
    one service, called once the bytes are safe. It does not live inside the storing: that
    primitive knows nothing of parts — the routes that keep a telling of a stretch store through
    it as well — and what follows from a part arriving is the room's question, not storage's.

    The tablet's fingerprint and length are checked against the bytes and refused when they
    disagree, never corrected. A joined part keeps the server's clock as its recording time,
    and a resend answers with the row already kept, its time unmoved.

    **Over an approved draft, a join, a swap and a whole take over a joined recording re-open
    it only with the team's armed tap** (`reopens_the_approved_draft`, ADR 0081), and without
    it are refused `DRAFT_APPROVED` (409) with nothing stored. A part recorded on the recording
    screen carries no origin and takes one tap, as hers does, and a take already kept brings
    nothing new, so neither is ever refused.

    A rehearsal take of the other grain than the one a **Grain switch** put in force is kept and
    set aside at once, and never refused over an approved draft: it never becomes a part, so it
    changes no draft. A take a switch set aside is never the answer to a keep at the grain in
    force: the same bytes kept again are a new take that stands (ADR 0096).
    """
    session = await room.session_for_room_caller(db, session_id, project_id)
    refuse_a_panorama(session.pericope)
    take_kind = _kind(kind)
    if origin is not None:
        await refuse_an_origin_that_is_no_scene_rehearsal(db, session, origin)
    audio = await file.read()
    ordinal = None if take_kind is IRTakeKind.RETRO else chunk_index
    left_behind = of_the_grain_left_behind(session, take_kind, ordinal)
    if not reopens_the_approved_draft and not left_behind:
        await refuse_a_keep_that_reopens_the_approved_draft(
            db,
            session,
            kind=take_kind,
            origin=origin,
            chunk_index=chunk_index,
            pass_number=pass_number,
            audio=audio,
        )
    take = await store_take(
        db,
        session_id=session.id,
        device_id=device_id,
        project_id=session.project_id,
        pericope=session.pericope,
        kind=take_kind,
        scope=scope,
        audio=audio,
        pass_number=pass_number,
        ordinal=ordinal,
        content_type=file.content_type or "audio/mp4",
        origin=origin,
        sent_sha256=sha256,
        sent_duration_ms=duration_ms,
        sent_recorded_at=recorded_at,
        past_the_set_aside=not left_behind,
        the_same=partial(
            the_take_this_keep_already_is,
            db,
            session.id,
            take_kind,
            ordinal=ordinal,
            pass_number=pass_number,
            origin=origin,
            past_the_set_aside=not left_behind,
        ),
    )
    await room.set_aside_by_the_grain_in_force(db, session, take)
    await room.retire_the_part_recorded_again(db, session, take)
    nudge(session.project_id, "takes")
    return _view(take)


@router.post(
    "/sessions/{session_id}/grain",
    response_model=TakesResponse,
    dependencies=[linked_tablet_dep],
    responses={
        409: {
            "description": "`DRAFT_APPROVED`: the draft stands approved and the request did not "
            "carry reopens_the_approved_draft (ADR 0081, ADR 0096)"
        }
    },
)
async def switch_grain(
    session_id: str,
    payload: GrainSwitchRequest,
    project_id: str = device_project_dep,
    db: AsyncSession = Depends(get_db),
) -> TakesResponse:
    """The team records the passage whole or scene by scene from now on.

    A switch sets every rehearsal take the session holds aside, stamped with its time and never
    deleted, and from then on the parts are only the new grain's takes recorded after it. The
    telling-back starts over, so the passage has no check. A switch to the grain in force
    changes nothing; over an approved draft it takes the team's armed tap
    (`reopens_the_approved_draft`) and is otherwise refused `DRAFT_APPROVED` (409, ADR 0096).

    It answers the takes listing, so the tablet sees at once what was set aside.
    """
    session = await room.session_for_room_caller(db, session_id, project_id)
    refuse_a_panorama(session.pericope)
    switched = await room.switch_the_grain(
        db,
        session,
        IRGrain(payload.grain),
        reopens_the_approved_draft=payload.reopens_the_approved_draft,
    )
    if switched:
        nudge(session.project_id, "takes")
        nudge(session.project_id, "stretches")
    return await _listing(db, session)


@router.get(
    "/sessions/{session_id}/takes",
    response_model=TakesResponse,
    dependencies=[linked_tablet_dep],
)
async def list_takes(
    session_id: str,
    project_id: str = device_project_dep,
    db: AsyncSession = Depends(get_db),
) -> TakesResponse:
    session = await room.session_for_room_caller(db, session_id, project_id)
    return await _listing(db, session)


@router.get(
    "/sessions/{session_id}/takes/{take_id}/audio",
    status_code=status.HTTP_307_TEMPORARY_REDIRECT,
    response_class=RedirectResponse,
    response_model=None,
    dependencies=[linked_tablet_dep],
)
async def room_listens_to_take(
    session_id: str,
    take_id: str,
    project_id: str = device_project_dep,
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    """Give the team back the telling it just recorded, by the same signed redirect.

    The back translation goes up and, until this, went nowhere the room could reach: the
    only route that handed out playable audio wanted a facilitator's login, and the team
    never signs in. The screen that asks where the error lives plays the mother tongue
    from the tablet's own files and this in the other button.

    The take is named inside its session rather than on its own, because the credential
    at this door is the same string on every tablet — `take_in_session` is where that
    argument is written out. The session is resolved through `session_for_room_caller`
    first, for the same reason every other room route now does: naming a take inside
    another project's session is still naming that project's session.
    """
    await room.session_for_room_caller(db, session_id, project_id)
    take = await take_in_session(db, session_id, take_id)
    await db.commit()
    return RedirectResponse(await listen_url(take), status_code=status.HTTP_307_TEMPORARY_REDIRECT)


@router.get("/facilitator/sessions/{session_id}/takes", response_model=TakesResponse)
async def facilitator_takes(
    session_id: str, user: ReaderUser, db: AsyncSession = Depends(get_db)
) -> TakesResponse:
    """What a session recorded, for the person who will listen to it.

    A facilitator signs in; the team never does. So this carries no device credential — the
    two audiences never share a route.
    """
    session = await room.get_session_for_reader(db, user, session_id)
    return await _listing(db, session)


@router.get(
    "/facilitator/sessions/{session_id}/mother-tongue-takes",
    response_model=MotherTongueTakesResponse,
)
async def read_the_mother_tongue_takes(
    session_id: str,
    user: ReaderUser,
    db: AsyncSession = Depends(get_db),
    store: TakeStore = Depends(take_store),
) -> MotherTongueTakesResponse:
    session = await room.get_session_for_reader(db, user, session_id)
    return await mother_tongue_takes_of(db, session, store)


@router.get(
    "/facilitator/sessions/{session_id}/takes/downloads",
    response_model=TakeDownloadsResponse,
)
async def read_the_take_downloads(
    session_id: str, user: ReaderUser, db: AsyncSession = Depends(get_db)
) -> TakeDownloadsResponse:
    """What the facilitator hands Refine: each take under her file name, links good for an hour.

    Read it again for fresh links. A name is the release the draft stands approved under at
    the moment of the read, or the name the next version will have; a session a Zerar archived
    keeps the name of the release its takes were approved as (ADR 0081).
    """
    session = await room.get_session_for_reader(db, user, session_id)
    return await take_downloads_of(db, session)


@router.get(
    "/facilitator/takes/{take_id}/audio",
    status_code=status.HTTP_307_TEMPORARY_REDIRECT,
    response_class=RedirectResponse,
    response_model=None,
)
async def listen_to_take(
    take_id: str, user: ReaderUser, db: AsyncSession = Depends(get_db)
) -> RedirectResponse:
    """Redirect to a short-lived signed URL: storage serves the bytes.

    The API never proxies a take. A rehearsal take is the whole passage, and streaming
    minutes of audio through the application server buys nothing over letting the bucket
    do it — the same reason the sound necklace redirects rather than proxies.
    """
    take = await take_for_reader(db, user, take_id)
    await db.commit()
    return RedirectResponse(await listen_url(take), status_code=status.HTTP_307_TEMPORARY_REDIRECT)
