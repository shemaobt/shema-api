"""The two verbs the team has and could not reach: divide a stretch, and replace one.

`capture_segment` has taken `parent` and `replaces` since a stretch became a row, and the only
caller passed neither — the whole correction the product describes existed in the service and
had no door. These are the doors, and nothing else: choosing where to cut is the team's, the
rules about where a cut may land are the service's, and neither is decided here.
"""

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.internalization_room._deps import device_dep, room_caller_dep
from app.core.database import get_db
from app.core.exceptions import ValidationError
from app.core.room_enums import HaltKind
from app.db.models.internalization_room import IRSegment, IRTakeKind
from app.models.internalization_room import DivideSegmentRequest, SegmentsResponse, SegmentView
from app.services import internalization_room as room
from app.services.internalization_room.hearing import heard
from app.services.internalization_room.segments import (
    divide_segment,
    segment_for_session,
    slice_moved,
)
from app.services.internalization_room.sessions import MAX_RETELLS
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
    db: AsyncSession = Depends(get_db),
) -> SegmentsResponse:
    """The team heard two ideas where they had told one, and cuts the stretch in two.

    No audio is cut and nothing crosses the wire: two rows are written against the recording
    that was already there. That is what lets the room do this with no connection, which
    matters because it is an action the team takes in the middle of the work.

    `at_ms` is counted from the start of the recording, the same as the stretch's own bounds.
    Where it may fall is `divide_segment`'s to say.
    """
    session = await room.get_session(db, session_id)
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
    take_id: str = Form(...),
    starts_ms: int = Form(...),
    ends_ms: int = Form(...),
    file: UploadFile | None = File(default=None),
    device_id: str = device_dep,
    db: AsyncSession = Depends(get_db),
) -> SegmentsResponse:
    """A new version of one stretch: a new explanation, or a new recording under it.

    Both of the product's corrections come through here, and which one it is falls out of what
    the caller sends rather than out of a flag it could get wrong:

    - the same slice with audio is the explanation redone over a recording that did not move;
    - a different slice is the mother tongue re-recorded, and it arrives with no explanation —
      the one belonging to audio nobody will hear again does not carry over. Sending both is
      refused by `capture_segment`, which is where that rule lives.

    A stretch left waiting this way is told again by calling this route a second time with its
    own slice and the new audio. That is the same correction as the first case, which is why
    there is no third verb.

    The bytes are stored before anything is asked of them, as on the telling-back route: a
    transcriber that times out must not take the recording with it. And when nothing could be
    made out, **the stretch is not replaced at all** — swapping a good explanation for an empty
    one over a transcriber hiccup would lose the team's work to somebody else's outage.

    What is *not* stored first is a request that cannot succeed. A different slice arriving with
    an explanation is refused by `capture_segment` either way, but only after the recording had
    been kept and the transcriber paid — and the orphan take then travelled to Refine among the
    telling-backs. It is knowable from the stretch and the form fields, so it is answered before
    anything is spent, which is the argument the telling-back route already makes for the slice
    that is not a slice.
    """
    session = await room.get_session(db, session_id)
    segment = await segment_for_session(db, session.id, segment_id)
    rehearsal = await rehearsal_take_of(db, session.id, take_id)

    if file is None:
        await room.capture_segment(
            db,
            session,
            take_id=rehearsal.id,
            starts_ms=starts_ms,
            ends_ms=ends_ms,
            pass_number=segment.pass_number,
            replaces=segment,
        )
        return SegmentsResponse(session_id=session.id, segments=await _units(db, session.id))

    if slice_moved(segment, rehearsal.id, starts_ms, ends_ms):
        raise ValidationError(
            "A stretch re-recorded in the mother tongue starts with no telling-back: send the "
            "new recording on its own, and tell it back afterwards"
        )

    audio_bytes = await file.read()
    if len(audio_bytes) > MAX_AUDIO_BYTES:
        raise ValidationError("Audio payload exceeds 25 MB limit")

    state = room.back_translation_of(session)
    told_again = state.retells + 1

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
        chunk_index=segment.ordinal,
        content_type=file.content_type or "audio/mp4",
    )

    text = await heard(audio_bytes, filename=file.filename, mime_type=file.content_type)

    state.retells = told_again
    await room.save_back_translation(db, session, state)
    spent = told_again >= MAX_RETELLS
    if spent:
        await room.mark_needs_person(db, session, kind=HaltKind.WARNING)

    if not text.strip():
        return SegmentsResponse(
            session_id=session.id,
            segments=await _units(db, session.id),
            captured=False,
            needs_person=spent,
        )

    await room.capture_segment(
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
    return SegmentsResponse(
        session_id=session.id, segments=await _units(db, session.id), needs_person=spent
    )
