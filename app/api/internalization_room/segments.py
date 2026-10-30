"""The two verbs the team has and could not reach: divide a stretch, and replace one.

`capture_segment` has taken `parent` and `replaces` since a stretch became a row, and the only
caller passed neither — the whole correction the product describes existed in the service and
had no door. These are the doors, and nothing else: choosing where to cut is the team's, the
rules about where a cut may land are the service's, and neither is decided here.
"""

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.internalization_room._deps import (
    device_dep,
    device_project_dep,
    include_stale_dep,
    linked_tablet_dep,
)
from app.api.internalization_room._idempotent import IdempotentRoute, idempotency_dep
from app.core.database import get_db
from app.core.exceptions import ValidationError, WordlessTelling
from app.db.models.internalization_room import IRSegment, IRTake, IRTakeKind
from app.models.internalization_room import (
    DivideSegmentRequest,
    SegmentsResponse,
    SegmentView,
    SentenceLaidInResponse,
)
from app.services import internalization_room as room
from app.services.internalization_room.coverage import refuse_a_panorama
from app.services.internalization_room.hard_stretches import pass_of_a_telling
from app.services.internalization_room.hearing import heard
from app.services.internalization_room.joined_parts import bring_back_the_rehearsals_frases
from app.services.internalization_room.languages import room_language
from app.services.internalization_room.nudge_channel import nudge, nudge_stretches
from app.services.internalization_room.segments import (
    divide_segment,
    refuse_a_replace_before_its_recording_is_kept,
    refuse_a_slice_a_version_cannot_take,
    segment_for_session,
)
from app.services.internalization_room.sentences import (
    SENTENCE_LIMIT_BYTES,
    lay_in_a_sentence,
    refuse_a_sentence_too_long,
    refuse_another_span_for_the_awaiting_frase,
)
from app.services.internalization_room.takes import (
    TakeStore,
    refuse_a_take_that_is_no_longer_a_part,
    rehearsal_take_of,
    store_take,
    take_store,
    takes_of,
)

router = APIRouter()

MAX_AUDIO_BYTES = 25 * 1024 * 1024


def segment_views(
    stretches: list[IRSegment],
    stale: list[IRSegment] | None = None,
    takes: list[IRTake] | None = None,
) -> list[SegmentView]:
    numbers = room.passage_numbers(
        room.told_back(stretches), room.told_back(stale or []), takes or []
    )
    asked = stale is not None
    return [
        SegmentView(
            segment_id=segment.id,
            take_id=segment.take_id,
            starts_ms=segment.starts_ms,
            ends_ms=segment.ends_ms,
            pass_number=segment.pass_number,
            told=segment.transcript is not None,
            bridge_take_id=segment.bridge_take_id,
            frase=numbers.get(segment.id),
            stale=segment.stale if asked else None,
        )
        for segment in [*stretches, *(stale or [])]
    ]


async def _units(
    db: AsyncSession, session_id: str, *, include_stale: bool = False
) -> list[SegmentView]:
    """Every stretch that counts, after the change — which is what the tablet redraws.

    Answering with the whole list rather than with what was just written: dividing renumbers
    nothing, but a client that patched its own list from a two-element answer would be keeping
    a second copy of a rule that lives in `final_segments`.
    """
    takes = await takes_of(db, session_id)
    return segment_views(
        await room.final_segments(db, session_id, takes),
        await room.stale_segments(db, session_id, takes) if include_stale else None,
        takes,
    )


@router.post(
    "/sessions/{session_id}/segments/{segment_id}/divide",
    response_model=SegmentsResponse,
    dependencies=[linked_tablet_dep],
)
async def divide(
    session_id: str,
    segment_id: str,
    payload: DivideSegmentRequest,
    asking_for_stale: bool = include_stale_dep,
    project_id: str = device_project_dep,
    db: AsyncSession = Depends(get_db),
) -> SegmentsResponse:
    """The team heard two ideas where they had told one, and cuts the stretch in two.

    No audio is cut and nothing crosses the wire: two rows are written against the recording
    that was already there. That is what lets the room do this with no connection, which
    matters because it is an action the team takes in the middle of the work.

    `at_ms` is counted from the start of the recording, the same as the stretch's own bounds.
    Where it may fall is `divide_segment`'s to say. A frase awaiting the translation of its
    re-recorded sentence is not divided: 400 `FRASE_AWAITS_ITS_TRANSLATION`.
    """
    session = await room.session_for_room_caller(db, session_id, project_id)
    refuse_a_panorama(session.pericope)
    segment = await segment_for_session(db, session.id, segment_id)
    await refuse_another_span_for_the_awaiting_frase(
        db, session, segment, segment.starts_ms, payload.at_ms
    )
    await divide_segment(db, session, segment, at_ms=payload.at_ms)
    nudge(session.project_id, "stretches")
    return SegmentsResponse(
        session_id=session.id,
        segments=await _units(db, session.id, include_stale=asking_for_stale),
    )


@router.post(
    "/sessions/{session_id}/back-translation/restart",
    response_model=SegmentsResponse,
    dependencies=[linked_tablet_dep],
)
async def restart(
    session_id: str,
    project_id: str = device_project_dep,
    db: AsyncSession = Depends(get_db),
) -> SegmentsResponse:
    """The team starts the translation over: every frase and check is archived, never deleted."""
    session = await room.session_for_room_caller(db, session_id, project_id)
    refuse_a_panorama(session.pericope)
    await room.start_the_translation_over(db, session)
    nudge(session.project_id, "stretches")
    return SegmentsResponse(session_id=session.id, segments=await _units(db, session.id))


@router.post(
    "/sessions/{session_id}/parts/{number}/bring-back",
    response_model=SegmentsResponse,
    dependencies=[linked_tablet_dep],
    responses={
        400: {"description": "`PANORAMA_RECORDS_NOTHING`: a panorama records nothing"},
        401: {"description": "`UNAUTHORIZED`: no linked tablet's credential"},
        404: {"description": "`NOT_FOUND`: no such session for this team, or no part `number`"},
        409: {
            "description": "`NOTHING_TO_BRING_BACK`: the part was not joined from a scene "
            "rehearsal of this session, a sentence was re-recorded in it, or the rehearsal "
            "has no frase; nothing is written"
        },
    },
)
async def bring_back(
    session_id: str,
    number: int,
    project_id: str = device_project_dep,
    db: AsyncSession = Depends(get_db),
) -> SegmentsResponse:
    """«trazer de volta as traduções do ensaio desta cena»: the rehearsal's frases laid again.

    Offered on a joined part none of whose rehearsal's frases stands, after «recomeçar a
    tradução» or when they never landed. The stretches told here on that part are abandoned,
    kept as history and never deleted, and the check starts over as after any telling. A part
    whose frases already stand answers as it is, so a second tap lays once.
    """
    session = await room.session_for_room_caller(db, session_id, project_id)
    refuse_a_panorama(session.pericope)
    await bring_back_the_rehearsals_frases(db, session, number)
    nudge(session.project_id, "stretches")
    return SegmentsResponse(session_id=session.id, segments=await _units(db, session.id))


async def replace(
    session_id: str,
    segment_id: str,
    take_id: str = Form(...),
    starts_ms: int = Form(...),
    ends_ms: int = Form(...),
    file: UploadFile = File(...),
    asking_for_stale: bool = include_stale_dep,
    device_id: str = device_dep,
    project_id: str = device_project_dep,
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
    transcriber that times out must not take the recording with it. The Correction is transcribed
    in the session's bridge language, within `TRANSCRIBER_BOUND_SECONDS`. And when nothing could
    be made out — no words, a failed transcriber or a late one — it answers 422
    `WORDLESS_TELLING` with no spoken line and **the stretch is not replaced at all**: swapping a
    good explanation for an empty one over a transcriber hiccup would lose the team's work to
    somebody else's outage. Nothing is counted either; the tablet shows its own line and the
    team tells it again.

    What is *not* stored first is a request that cannot succeed. A slice that is not this
    stretch's is refused by `capture_segment` either way, but only after the recording had been
    kept and the transcriber paid — and the orphan take then travelled to Refine among the
    telling-backs. It is knowable from the stretch and the form fields, so the same refusal is
    asked here first, which is the argument the telling-back route already makes for the slice
    that is not a slice.

    **The same recording sent again is a resend, not one more correction.** A freed idempotency
    key brings the same bytes back, and the room reads the frase standing at the slice sent, not
    the id in the path: when that frase already holds the recording, nothing is transcribed,
    replaced or counted and the answer is the frases as they stand. That is also the answer at
    the id the first attempt already replaced — 200 with the standing frase, not 400
    `STRETCH_NO_LONGER_COUNTS`, which a different recording sent there still gets.
    `needs_person` is true when the stretch carries its mark, so a lost answer that asked for a
    person asks again.

    A frase awaiting the translation of its re-recorded sentence is told again only at exactly
    the span the new sentence took; any other slice answers 400 `FRASE_AWAITS_ITS_TRANSLATION`.
    """
    session = await room.session_for_room_caller(db, session_id, project_id)
    refuse_a_panorama(session.pericope)
    segment = await segment_for_session(db, session.id, segment_id)
    rehearsal = await rehearsal_take_of(db, session.id, take_id)

    await refuse_another_span_for_the_awaiting_frase(db, session, segment, starts_ms, ends_ms)
    await refuse_a_slice_a_version_cannot_take(
        db, session, segment, rehearsal.id, starts_ms, ends_ms
    )
    await refuse_a_take_that_is_no_longer_a_part(db, session.id, rehearsal)

    audio_bytes = await file.read()
    if len(audio_bytes) > MAX_AUDIO_BYTES:
        raise ValidationError("Audio payload exceeds 25 MB limit")
    await refuse_a_replace_before_its_recording_is_kept(db, session.id, segment, audio_bytes)

    retold = await room.current_stretch_at(
        db, session.id, take_id=rehearsal.id, starts_ms=starts_ms, ends_ms=ends_ms
    )
    retro = await store_take(
        db,
        session_id=session.id,
        device_id=device_id,
        project_id=session.project_id,
        pericope=session.pericope,
        kind=IRTakeKind.RETRO,
        scope=session.pericope,
        audio=audio_bytes,
        pass_number=pass_of_a_telling(room.back_translation_of(session)),
        ordinal=segment.ordinal,
        content_type=file.content_type or "audio/mp4",
    )
    await db.commit()

    if room.is_a_resend(retold, retro):
        crossed = await room.a_hard_stretch_stands(db, retold)
    else:
        text = await heard(
            audio_bytes,
            language=room_language(session.language),
            filename=file.filename,
            mime_type=file.content_type,
        )
        if not text.strip():
            raise WordlessTelling()

        _, crossed = await room.capture_and_note_a_hard_stretch(
            db,
            session,
            take_id=rehearsal.id,
            starts_ms=starts_ms,
            ends_ms=ends_ms,
            bridge_take_id=retro.id,
            transcript=text,
            replaces=segment,
        )
    nudge_stretches(session.project_id, warned=crossed)
    return SegmentsResponse(
        session_id=session.id,
        segments=await _units(db, session.id, include_stale=asking_for_stale),
        needs_person=crossed,
    )


router.add_api_route(
    "/sessions/{session_id}/segments/{segment_id}/replace",
    replace,
    methods=["POST"],
    response_model=SegmentsResponse,
    dependencies=[linked_tablet_dep, idempotency_dep],
    route_class_override=IdempotentRoute,
)


@router.post(
    "/sessions/{session_id}/segments/{segment_id}/sentence",
    response_model=SentenceLaidInResponse,
    dependencies=[linked_tablet_dep],
    responses={
        400: {
            "description": "`SENTENCE_TOO_SHORT`: under 0.5 s once its silence is trimmed; "
            "`SENTENCE_FORMAT_DIFFERS`: not WAV PCM16 at the part's own rate and channels"
        },
        409: {
            "description": "`PART_NOT_WAV`: the part was not recorded as WAV PCM16; "
            "`SENTENCE_ID_REUSED`: the id already names another recording; "
            "`ANOTHER_SENTENCE_AWAITS` (with `frases`): another frase awaits its translation; "
            "`PART_CHANGED`: the frase's part changed while the sentence was laid in; nothing "
            "was written, send it again; `DRAFT_APPROVED`: the draft is approved and the team "
            "did not arm the tap that re-opens it"
        },
        413: {"description": "`SENTENCE_TOO_LONG`: the recording weighs over 4 MB"},
    },
)
async def re_record_the_sentence(
    session_id: str,
    segment_id: str,
    sentence_id: str = Form(..., pattern=r"^[A-Za-z0-9_-]{8,64}$"),
    file: UploadFile = File(...),
    reopens_the_approved_draft: bool = Form(
        default=False,
        description=(
            "True when the team armed the tap that re-opens its approved draft (ADR 0081). "
            "Without it, over an approved draft, the sentence is refused DRAFT_APPROVED."
        ),
    ),
    asking_for_stale: bool = include_stale_dep,
    device_id: str = device_dep,
    project_id: str = device_project_dep,
    store: TakeStore = Depends(take_store),
    db: AsyncSession = Depends(get_db),
) -> SentenceLaidInResponse:
    """One whole sentence recorded again, laid into its part in the frase's place.

    `segment_id` is the frase whose sentence the team recorded again; it is always a whole
    sentence, never a piece of one (Marcia, 21 September), and a frase that still counts: one
    told again, retired with its part or divided answers `STRETCH_NO_LONGER_COUNTS` (400).
    `sentence_id` is minted by the tablet for this one recording and sent again with every retry
    of it. `file` is the raw recording, WAV PCM16 at the part's own rate and channels.

    The new sentence keeps 0.2 s of its silence on each side and replaces the old one inside the
    part; the audio before and after it is the same bytes, and the frases after it move by the
    difference in length. The part becomes a new rehearsal take, and the take it replaces is
    kept.

    Refused with a named `code` the tablet turns into her lines: `SENTENCE_TOO_LONG` (413) for
    a recording over 4 MB, before anything else is read; `SENTENCE_TOO_SHORT` (400) for one
    under half a second once its silence is trimmed; `PART_NOT_WAV` (409) when the part was not
    recorded as WAV PCM16, where the team records the part again instead;
    `SENTENCE_FORMAT_DIFFERS` (400) for a recording that is not WAV PCM16 at the part's own rate
    and channels, which is never resampled; `SENTENCE_ID_REUSED` (409) for a `sentence_id`
    already laid in with another recording or another frase. The same recording sent again
    under its id is answered as it stands and laid in once; `ANOTHER_SENTENCE_AWAITS` (409, with
    `frases: [n]`) while another frase awaits its translation, one sentence at a time — the
    awaiting frase itself may be recorded again; `PART_CHANGED` (409) when the frase's part or
    its span changed while the sentence was spliced and stored, where nothing is written and the
    tablet offers to send the same sentence again; `DRAFT_APPROVED` (409) over an approved draft
    when the team did not arm the tap that re-opens it (`reopens_the_approved_draft`), asked
    after the format and before the awaiting frase, as hers is (splice.ts:157). A sentence
    already laid in is answered before it, so a resend after a landing is never refused.
    """
    audio = await file.read(SENTENCE_LIMIT_BYTES + 1)
    refuse_a_sentence_too_long(audio)
    session = await room.session_for_room_caller(db, session_id, project_id)
    refuse_a_panorama(session.pericope)
    segment = await segment_for_session(db, session.id, segment_id)
    await lay_in_a_sentence(
        db,
        session,
        segment,
        sentence_id=sentence_id,
        audio=audio,
        device_id=device_id,
        store=store,
        reopens_the_approved_draft=reopens_the_approved_draft,
    )
    return SentenceLaidInResponse(
        session_id=session.id,
        segments=await _units(db, session.id, include_stale=asking_for_stale),
    )
