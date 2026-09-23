"""The two verbs the team has and could not reach: divide a stretch, and replace one.

`capture_segment` has taken `parent` and `replaces` since a stretch became a row, and the only
caller passed neither — the whole correction the product describes existed in the service and
had no door. These are the doors, and nothing else: choosing where to cut is the team's, the
rules about where a cut may land are the service's, and neither is decided here.
"""

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.internalization_room._deps import device_dep, device_project_dep, room_caller_dep
from app.core.database import get_db
from app.core.exceptions import ValidationError
from app.db.models.internalization_room import IRSegment, IRTakeKind
from app.models.internalization_room import DivideSegmentRequest, SegmentsResponse, SegmentView
from app.services import internalization_room as room
from app.services.internalization_room.background import read_ahead
from app.services.internalization_room.hearing import heard
from app.services.internalization_room.segments import (
    divide_segment,
    refuse_a_slice_the_stretch_does_not_sit_on,
    segment_for_session,
)
from app.services.internalization_room.takes import rehearsal_take_of, store_take

router = APIRouter()

MAX_AUDIO_BYTES = 25 * 1024 * 1024


def segment_view(segment: IRSegment) -> SegmentView:
    return SegmentView(
        segment_id=segment.id,
        take_id=segment.take_id,
        starts_ms=segment.starts_ms,
        ends_ms=segment.ends_ms,
        pass_number=segment.pass_number,
        told=segment.transcript is not None,
    )


async def _units(db: AsyncSession, session_id: str) -> list[SegmentView]:
    """Every stretch that counts, after the change — which is what the tablet redraws.

    Answering with the whole list rather than with what was just written: dividing renumbers
    nothing, but a client that patched its own list from a two-element answer would be keeping
    a second copy of a rule that lives in `final_segments`.
    """
    return [segment_view(one) for one in await room.final_segments(db, session_id)]


@router.post(
    "/sessions/{session_id}/segments/{segment_id}/divide",
    response_model=SegmentsResponse,
    dependencies=[room_caller_dep],
)
async def divide(
    session_id: str,
    segment_id: str,
    payload: DivideSegmentRequest,
    project_id: str | None = device_project_dep,
    db: AsyncSession = Depends(get_db),
) -> SegmentsResponse:
    """The team heard two ideas where they had told one, and cuts the stretch in two.

    No audio is cut and nothing crosses the wire: two rows are written against the recording
    that was already there. That is what lets the room do this with no connection, which
    matters because it is an action the team takes in the middle of the work.

    `at_ms` is counted from the start of the recording, the same as the stretch's own bounds.
    Where it may fall is `divide_segment`'s to say.
    """
    session = await room.session_for_room_caller(db, session_id, project_id)
    segment = await segment_for_session(db, session.id, segment_id)
    await divide_segment(db, session, segment, at_ms=payload.at_ms)
    return SegmentsResponse(session_id=session.id, segments=await _units(db, session.id))


@router.post(
    "/sessions/{session_id}/segments/{segment_id}/replace",
    response_model=SegmentsResponse,
    dependencies=[room_caller_dep],
)
async def replace(
    session_id: str,
    segment_id: str,
    background: BackgroundTasks,
    take_id: str = Form(...),
    starts_ms: int = Form(...),
    ends_ms: int = Form(...),
    file: UploadFile = File(...),
    device_id: str = device_dep,
    project_id: str | None = device_project_dep,
    db: AsyncSession = Depends(get_db),
) -> SegmentsResponse:
    """One **Correction**: the same stretch told again, over the recording it already sits in.

    It is the only correction the room has. A stretch is a listening pause and not a unit
    anybody rehearsed, so what a team does about a *recording* that is wrong is record the
    **Part** again — an upload under that part's number, which is a different route (ADR 0023,
    ADR 0025). This answer assembles nothing and names no take of the server's; an old composed
    row is history, and it travels as the part its number makes it, by the same rule as any
    take — `current_parts`, which the check and the **Packet** both read.

    The audio is therefore not optional: without it there is no correction to express, and a
    call that omits it is the app's own bug, refused by this signature before any service runs.

    The bytes are stored before anything is asked of them, as on the telling-back route: a
    transcriber that times out must not take the recording with it. And when nothing could be
    made out, **the stretch is not replaced at all** — swapping a good explanation for an empty
    one over a transcriber hiccup would lose the team's work to somebody else's outage. It is
    still one more telling of that stretch, counted on the row that is standing, because there is
    no new row to count on: an outage that came free would let a team correcting one stretch
    tell it forever without the room ever offering them a person.

    What is *not* stored first is a request that cannot succeed. A slice that is not this
    stretch's is refused by `capture_segment` either way, but only after the recording had been
    kept and the transcriber paid — and the orphan take then travelled to Refine among the
    telling-backs. It is knowable from the stretch and the form fields, so the same refusal is
    asked here first, which is the argument the telling-back route already makes for the slice
    that is not a slice.
    """
    session = await room.session_for_room_caller(db, session_id, project_id)
    segment = await segment_for_session(db, session.id, segment_id)
    rehearsal = await rehearsal_take_of(db, session.id, take_id)

    refuse_a_slice_the_stretch_does_not_sit_on(segment, rehearsal.id, starts_ms, ends_ms)

    audio_bytes = await file.read()
    if len(audio_bytes) > MAX_AUDIO_BYTES:
        raise ValidationError("Audio payload exceeds 25 MB limit")

    retro = await store_take(
        db,
        session_id=session.id,
        device_id=device_id,
        project_id=session.project_id,
        pericope=session.pericope,
        kind=IRTakeKind.RETRO,
        scope=session.pericope,
        audio=audio_bytes,
        pass_number=segment.pass_number,
        ordinal=segment.ordinal,
        content_type=file.content_type or "audio/mp4",
    )
    await db.commit()

    text = await heard(audio_bytes, filename=file.filename, mime_type=file.content_type)

    if not text.strip():
        crossed = await room.count_an_empty_telling(db, session, segment)
        return SegmentsResponse(
            session_id=session.id,
            segments=await _units(db, session.id),
            captured=False,
            needs_person=crossed,
        )

    crossed = await room.capture_and_note_a_hard_stretch(
        db,
        session,
        take_id=rehearsal.id,
        starts_ms=starts_ms,
        ends_ms=ends_ms,
        bridge_take_id=retro.id,
        transcript=text,
        pass_number=segment.pass_number,
        replaces=segment,
    )
    background.add_task(read_ahead, session_id=session.id)
    return SegmentsResponse(
        session_id=session.id,
        segments=await _units(db, session.id),
        needs_person=crossed,
    )
