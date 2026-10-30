import logging

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.internalization_room._deps import device_dep, device_project_dep, linked_tablet_dep
from app.api.internalization_room._idempotent import IdempotentRoute, idempotency_dep
from app.core.config import get_settings
from app.core.database import get_db
from app.core.exceptions import UpstreamServiceError, ValidationError, WordlessTelling
from app.core.stage_clock import stage, stopwatch
from app.db.models.internalization_room import IRSession, IRTake, IRTakeKind
from app.models.internalization_room import (
    BackTranslationChunkResponse,
    BackTranslationVerdictResponse,
    CheckRefusal,
    FindingView,
    FinishBackTranslationRequest,
    ListenedWholeResponse,
    VerdictHeardRequest,
    VerdictHeardResponse,
)
from app.services import internalization_room as room
from app.services.internalization_room.back_translation import (
    Finding,
    is_joined,
    untranslated_parts,
)
from app.services.internalization_room.canon.kept import reading_the_canon_of
from app.services.internalization_room.coverage import refuse_a_panorama
from app.services.internalization_room.fail_safe import process_line
from app.services.internalization_room.hard_stretches import pass_of_a_telling
from app.services.internalization_room.hearing import heard
from app.services.internalization_room.languages import room_language
from app.services.internalization_room.nudge_channel import nudge, nudge_stretches
from app.services.internalization_room.segments import (
    refuse_a_frase_under_the_floor,
    refuse_a_slice_that_is_not_one,
    refuse_a_telling_over_part_of_a_frase,
)
from app.services.internalization_room.sentences import the_sentence_awaiting
from app.services.internalization_room.takes import (
    current_parts,
    refuse_a_take_that_is_no_longer_a_part,
    rehearsal_take_of,
    store_take,
    takes_of,
)
from app.services.internalization_room.voice_handles import clip_url

logger = logging.getLogger(__name__)

router = APIRouter()

CHECKING_LINE = "N1"
UNTRANSLATED_LINE = "N2"

MAX_AUDIO_BYTES = 25 * 1024 * 1024


def finding_views(
    findings: list[Finding], analysed_segment_ids: list[str] | None, numbers: dict[str, int]
) -> list[FindingView]:
    return [
        FindingView(
            kind=one.kind.value,
            frase=room.finding_frase(one, analysed_segment_ids, numbers),
            segment_id=one.segment_id,
        )
        for one in findings
    ]


def named_nuance_view(
    state: room.BackTranslationState, numbers: dict[str, int]
) -> FindingView | None:
    named = next(
        (one for one in (state.checks[-1].nuances if state.checks else []) if one.voiced == "now"),
        None,
    )
    if named is None or named.segment_id not in numbers:
        return None
    return FindingView(kind="nuance", frase=numbers[named.segment_id], segment_id=named.segment_id)


async def add_chunk(
    session_id: str,
    file: UploadFile = File(...),
    take_id: str = Form(...),
    starts_ms: int = Form(...),
    ends_ms: int = Form(...),
    device_id: str = device_dep,
    project_id: str = device_project_dep,
    db: AsyncSession = Depends(get_db),
) -> BackTranslationChunkResponse:
    """One piece told back in the bridge language, while the team's own recording plays.

    Nothing is voiced here: the clip resuming is the acknowledgement, so this returns no audio.

    The audio is kept, and kept before anything is asked of it. It already crosses the wire to
    be transcribed, and a back translation nobody can listen to is a claim about a recording
    rather than the recording itself. Storing after the hearing would lose it in the two
    moments the team re-records: a transcriber that times out raises past the store, and a
    chunk nobody could make out is refused after it.

    A telling at the exact slice of a stretch that counts is a **new version of that stretch**,
    not a stretch of its own at the next position: the row it replaces stops counting, keeps its
    place and its number, and hands the new one the count of tellings that stretch has had. The
    tablet sends the stretch's own address back both when the team tells it again after a finding
    and when a lost answer made it say «não entendi» and tell it under a new key, and the
    room reads the address, not a flag. At `RETELLS_BEFORE_A_WARNING` the stretch is a hard
    stretch and the room asks for a person to come and watch, once. A warning, not a cap —
    nothing is refused past it, and the chunk is kept either way. Their work is never the thing
    thrown away.

    A telling at a slice no stretch currently covers is a first telling.

    The telling is transcribed in the session's bridge language, within `TRANSCRIBER_BOUND_SECONDS`.

    **A telling with no words is refused, not counted.** A transcript that is empty or only what
    the transcriber wrote about the audio, a transcriber that fails and one that does not answer
    in time all answer 422 `WORDLESS_TELLING` with no spoken line: no stretch, no count toward
    the warning, and the recording stays kept. The tablet shows its own line and the team tells
    it again.

    `take_id` names the rehearsal recording this piece explains, and `starts_ms`/`ends_ms` the
    slice inside **that file** — where the team let it play and where they stopped it. All
    three are required. The times used to be optional and counted over the whole passage as if
    it were one recording, which is what made re-recording one stretch move every stretch after
    it; a slice with no file to be a slice of would be the same defect under another name.
    """
    session = await room.session_for_room_caller(db, session_id, project_id)
    refuse_a_panorama(session.pericope)
    rehearsal = await rehearsal_take_of(db, session.id, take_id)
    await refuse_a_take_that_is_no_longer_a_part(db, session.id, rehearsal)
    refuse_a_slice_that_is_not_one(starts_ms, ends_ms)
    audio_bytes = await file.read()
    if len(audio_bytes) > MAX_AUDIO_BYTES:
        raise ValidationError("Audio payload exceeds 25 MB limit")

    state = room.back_translation_of(session)
    told = await room.final_segments(db, session.id)
    refuse_a_telling_over_part_of_a_frase(told, rehearsal.id, starts_ms, ends_ms)
    retold = await room.current_stretch_at(
        db, session.id, take_id=rehearsal.id, starts_ms=starts_ms, ends_ms=ends_ms
    )
    if retold is None:
        refuse_a_frase_under_the_floor(starts_ms, ends_ms)
    pass_number = pass_of_a_telling(state)

    # The bytes are kept before anything is asked of them. Transcribing first put the one
    # irreplaceable thing behind a network call to another company: `heard` only catches
    # `ValidationError`, so a read timeout or a dropped connection to the transcriber
    # raised straight past this line, and the stretch was never stored. On a weak link the
    # tablet also gives up first, and a cancelled request dies at the same place.
    retro = await store_take(
        db,
        session_id=session.id,
        device_id=device_id,
        project_id=session.project_id,
        pericope=session.pericope,
        kind=IRTakeKind.RETRO,
        scope=state.scope or session.pericope,
        audio=audio_bytes,
        pass_number=pass_number,
        ordinal=None,
        content_type=file.content_type or "audio/mp4",
    )
    await db.commit()

    if room.is_a_resend(retold, retro):
        captured, warned = retold, await room.a_hard_stretch_stands(db, retold)
    else:
        text = await heard(
            audio_bytes,
            language=room_language(session.language),
            filename=file.filename,
            mime_type=file.content_type,
        )
        if not text.strip():
            raise WordlessTelling()
        captured, warned = await room.capture_and_note_a_hard_stretch(
            db,
            session,
            take_id=rehearsal.id,
            starts_ms=starts_ms,
            ends_ms=ends_ms,
            bridge_take_id=retro.id,
            transcript=text,
            replaces=retold,
            state=state,
        )
    nudge_stretches(session.project_id, warned=warned)
    standing = await room.final_segments(db, session.id)
    numbers = room.frase_numbers(room.told_back(standing))
    return BackTranslationChunkResponse(
        session_id=session.id,
        segment_id=captured.id,
        captured=True,
        pass_number=pass_number,
        needs_person=warned,
        frase=numbers.get(captured.id),
    )


router.add_api_route(
    "/sessions/{session_id}/back-translation/chunks",
    add_chunk,
    methods=["POST"],
    response_model=BackTranslationChunkResponse,
    dependencies=[linked_tablet_dep, idempotency_dep],
    route_class_override=IdempotentRoute,
)


@router.post(
    "/sessions/{session_id}/back-translation/finish",
    response_model=BackTranslationVerdictResponse,
    dependencies=[linked_tablet_dep],
)
async def finish(
    session_id: str,
    payload: FinishBackTranslationRequest | None = None,
    project_id: str = device_project_dep,
    db: AsyncSession = Depends(get_db),
) -> BackTranslationVerdictResponse:
    """`terminei` — compare the telling-back to the map and voice one finding, or the badge.

    With nothing told back, the analyst is not asked. Given no stretches it answers with no
    findings, and no findings is precisely what `checked` is made of — so `terminei` over an
    empty back translation came back clean, the app closed the necklace and struck the passage
    off the wheel for good, on a telling-back that never happened. A finished passage never
    returns to the wheel, by design, so there is no undo for that.

    The answer is never the badge, then: it is the refusal `NOTHING_TRANSLATED`, and the room
    says nothing over it. Her screen shows «ainda não tem frase traduzida» and voices no line;
    the D family stood here and told the team the room could not hear them, when nothing had
    been said for it to fail to hear. It is the last refusal asked, as hers is
    (`bt/check/route.ts:78`).

    Only the stretches the team actually explained are read. A stretch whose mother-tongue
    recording was replaced is waiting to be told again and carries nothing they said, so it
    is not evidence — and the same list numbers the analyst's reading and resolves its answer,
    so a finding cannot land on one either.

    And while any stretch is still waiting, nothing is read at all. The analyst's prompt calls
    an element missing when it appears in *no* stretch and forbids joining one stretch to
    another, so a subset contradicts the definition it works by: everything living in the
    stretch left out comes back as a finding about a hole the team is on their way to filling.
    Worse, a subset that reads clean is indistinguishable from a whole one that reads clean,
    and `checked` is what strikes the passage off the wheel for good.

    That refusal is `FRASE_AWAITING`, asked first as hers is (`bt/check/route.ts:68`), and it
    names the stretch on `untold_segment_id` so the tablet opens it. The room says nothing over
    it: the H family it used to speak here is ours, not hers, and no line of hers says it.

    A **Part** no stretch is a slice of refuses nothing. Her check runs with it, and her analyst
    names what the passage is missing; the room used to send the team back to it with the H
    family first, which no line of hers says.

    Told back is not the same as heard, and the listening is asked after the stretch.
    While any current part of the rehearsal is unheard, the analyst is not asked either: what it
    would answer is a list of what is missing from the passage, and over a part nobody played
    that sentence is about audio the team never listened to — the room would voice it as if
    the work were done, on a reading of a passage they were still walking through. So the
    refusal names the parts, says her P-unheard line, and spends nothing: no reading and no line
    in the conversation.
    Nothing is saved either, because nothing changed: the report above is already stored.

    Pressed again over the same stretches, the room serves the verdict it already reached and
    consults nothing. The press is the same question, and answering it afresh cost a validator
    and a spoken synthesis every time and wrote the room into the conversation as having spoken
    twice — a false record of the room in front of the team, which outlives the bill. The reply
    is byte-for-byte the first one: the app is not told which press it made, because a second
    shape would be a contract change to say something no caller asked about. The one exception
    is a verdict voiced in a voice the room no longer has: its words are voiced again in the
    room's voice, so the clip's address changes and the rest of the reply does not. A verdict
    that fell to the fail-safe is not served at all: it conferred nothing, so the press is a
    check of its own on the reading already made, as every press of hers is.

    Nor is a verdict whose nuance the team has since heard to its end. Served, it would name
    that nuance again, which a nuance once said must never be (acceptance 5 of ENG-1198). The
    press is a new round on the same reading instead: it names the next nuance not yet said,
    or speaks the clean verdict when none is left. Falling through only while an unsaid nuance
    remains would replay the heard one in exactly the case where nothing is left to name.

    What counts as the same question is `already_analysed`, the record the analyst was already
    guarded by — one signal, so the four steps of a press can never disagree about whether the
    team told back anything new. A press that reached the analyst and then failed saves no
    verdict, so the press after it does the whole turn rather than serving one the team never
    heard.

    That failure — the analyst, the Speaker or the verdict's voice unavailable — answers the
    refusal `CHECK_UNAVAILABLE`, never a 502 the tablet reads as a lost connection. Her check
    saves nothing on it either (`bt/check/route.ts:90-97`), her screen says «não deu para
    conferir agora — tentem de novo», and `terminei` again is the retry.
    """
    with stopwatch("[bt-timing]", session_id):
        session = await room.session_for_room_caller(db, session_id, project_id)
        refuse_a_panorama(session.pericope)
        verdict = await _finished(session, payload, db)
    nudge(session.project_id, "verdict")
    return verdict


@router.post(
    "/sessions/{session_id}/back-translation/heard",
    response_model=VerdictHeardResponse,
    dependencies=[linked_tablet_dep],
)
async def verdict_heard(
    session_id: str,
    payload: VerdictHeardRequest,
    project_id: str = device_project_dep,
    db: AsyncSession = Depends(get_db),
) -> VerdictHeardResponse:
    session = await room.session_for_room_caller(db, session_id, project_id)
    return VerdictHeardResponse(marked=await room.mark_the_verdict_heard(db, session, payload.at))


@router.post(
    "/sessions/{session_id}/back-translation/listened-whole",
    response_model=ListenedWholeResponse,
    dependencies=[linked_tablet_dep],
)
async def listened_whole(
    session_id: str,
    payload: FinishBackTranslationRequest | None = None,
    project_id: str = device_project_dep,
    db: AsyncSession = Depends(get_db),
) -> ListenedWholeResponse:
    """What the team listened to: which parts are still unheard, and whether the room checks.

    Her joined recording is checked once with no tap after its first full listen
    (`ensaioFinal.ts:431-455` at her freeze), and the voice says so first — her N-2, «Ouvimos
    tudo. Agora vou conferir as traduções que vocês já me fizeram. Um momento.» — while
    «terminei» reads «conferindo…». So this door decides and says, and checks nothing: the
    check is the finish's, which the tablet calls next as «terminei» would. Run here, the
    check would hand back the line that announces it only after the half minute it announces.

    The body is the same report of what the tablet played as the finish's, stored the same
    way, so the listen it describes is the one the finish then finds. It is also where the
    tablet reports as each part ends, and every answer names the parts still unheard, so the
    tablet never counts by itself (ADR 0074).
    """
    session = await room.session_for_room_caller(db, session_id, project_id)
    refuse_a_panorama(session.pericope)
    state = room.back_translation_of(session)
    if payload is not None and payload.played_by_take:
        state = await room.report_playback(
            db,
            session,
            state,
            played_by_take=payload.played_by_take,
            played_ranges=payload.played_ranges,
            clip_duration_ms=payload.clip_duration_ms,
        )
    final = await room.final_segments(db, session.id)
    told = room.told_back(final)
    parts = current_parts(await takes_of(db, session.id))
    unheard = room.unheard_parts(state, parts, final)
    if (
        await the_sentence_awaiting(db, session) is not None
        or room.first_untold(final) is not None
        or unheard
        or not is_joined(parts)
        or not told
    ):
        return ListenedWholeResponse(session_id=session.id, unheard_take_ids=unheard)
    untranslated = untranslated_parts(parts, told, state.played_by_take)
    if untranslated:
        return ListenedWholeResponse(
            session_id=session.id,
            fixed_line=UNTRANSLATED_LINE,
            refusal=CheckRefusal.STRETCH_UNTRANSLATED,
            untranslated=untranslated,
        )
    if state.checks:
        return ListenedWholeResponse(session_id=session.id)
    return ListenedWholeResponse(
        session_id=session.id, automatic_check=True, fixed_line=CHECKING_LINE
    )


async def _without_the_whole_set_aside(
    db: AsyncSession, session: IRSession, state: room.BackTranslationState, takes: list[IRTake]
) -> room.BackTranslationState:
    """The state as the team is told of it: findings on a set-aside whole are only stored."""
    aside = await room.set_aside_segment_ids(db, session.id, takes)
    return state.model_copy(
        update={"findings": [f for f in state.findings if f.segment_id not in aside]}
    )


async def _finished(
    session: IRSession,
    payload: FinishBackTranslationRequest | None,
    db: AsyncSession,
) -> BackTranslationVerdictResponse:
    state = room.back_translation_of(session)
    takes = await takes_of(db, session.id)
    final = await room.final_segments(db, session.id, takes)
    told = room.told_back(final)
    if payload is not None and (
        payload.played_by_take or payload.played_ranges or payload.clip_duration_ms
    ):
        state = await room.report_playback(
            db,
            session,
            state,
            played_by_take=payload.played_by_take,
            played_ranges=payload.played_ranges,
            clip_duration_ms=payload.clip_duration_ms,
        )

    awaiting = await the_sentence_awaiting(db, session)
    if awaiting is not None:
        return BackTranslationVerdictResponse(
            session_id=session.id,
            fixed_line=awaiting.line,
            checked=False,
            untold_segment_id=awaiting.segment_id,
            refusal=CheckRefusal.FRASE_AWAITING,
        )

    untold = room.first_untold(final)
    if untold is not None:
        return BackTranslationVerdictResponse(
            session_id=session.id,
            checked=False,
            untold_segment_id=untold.id,
            refusal=CheckRefusal.FRASE_AWAITING,
        )

    unheard = room.unheard_parts(state, current_parts(takes), final)
    if unheard:
        _, line = process_line("P", "unheard", session.language)
        return BackTranslationVerdictResponse(
            session_id=session.id,
            fixed_line=line,
            checked=False,
            unheard_take_ids=unheard,
            findings_remaining=0,
            refusal=CheckRefusal.PART_UNHEARD,
        )

    parts = current_parts(takes)
    if is_joined(parts):
        untranslated = untranslated_parts(parts, told)
        if untranslated:
            return BackTranslationVerdictResponse(
                session_id=session.id,
                fixed_line=UNTRANSLATED_LINE,
                checked=False,
                untranslated=untranslated,
                refusal=CheckRefusal.STRETCH_UNTRANSLATED,
            )

    if not told:
        return BackTranslationVerdictResponse(
            session_id=session.id,
            checked=False,
            refusal=CheckRefusal.NOTHING_TRANSLATED,
        )

    stale = await room.stale_segments(db, session.id, takes)
    stored = state.the_verdict_to_serve(told)
    if stored is not None:
        state = await _without_the_whole_set_aside(db, session, state, takes)
        finding = room.the_finding_that_leads(state)
        with stage("db_let_go"):
            await db.commit()
        clip = await room.the_stored_verdicts_clip(session, stored)
        numbers = room.passage_numbers(told, room.told_back(stale), takes)
        return BackTranslationVerdictResponse(
            session_id=session.id,
            audio_url=clip_url(clip) if clip else "",
            fixed_line=stored.fixed_line,
            checked=state.checked,
            finding_kind=finding.kind if finding else None,
            finding_segment_id=finding.segment_id if finding else None,
            findings=finding_views(state.findings, state.analysed_segment_ids, numbers),
            findings_remaining=room.findings_remaining(state.findings),
            used_fail_safe=stored.used_fail_safe,
            check_at=state.checks[-1].at if state.checks else None,
            named_nuance=named_nuance_view(state, numbers),
        )

    with stage("db_let_go"):
        await db.commit()
    try:
        with reading_the_canon_of(session.canon_pin):
            verdict = await room.check_the_telling_back(
                session,
                state=state,
                told=told,
                stale=stale,
                takes=takes,
                settings=get_settings(),
            )
        with stage("voice"):
            voiced = (
                None
                if verdict.outcome.fixed_line
                else (
                    await room.synthesize_facilitator_speech(
                        verdict.said, language=session.language
                    )
                )[0]
            )
    except UpstreamServiceError as failure:
        logger.warning("Upstream service failure: %s", failure)
        return BackTranslationVerdictResponse(
            session_id=session.id,
            checked=False,
            refusal=CheckRefusal.CHECK_UNAVAILABLE,
        )
    with stage("db_write"):
        session = await room.save_the_spoken_verdict(
            db,
            session,
            state,
            said=verdict.said,
            clip_key=voiced.key if voiced else "",
            outcome=verdict.outcome,
            told_back=verdict.told_back,
        )

    shown = await _without_the_whole_set_aside(db, session, state, takes)
    standing = await room.final_segments(db, session.id)
    numbers = room.passage_numbers(room.told_back(standing), room.told_back(stale), takes)
    return BackTranslationVerdictResponse(
        session_id=session.id,
        audio_url=clip_url(voiced.key) if voiced else "",
        fixed_line=verdict.outcome.fixed_line,
        checked=verdict.checked and state.checked,
        finding_kind=verdict.finding.kind if verdict.finding else None,
        finding_segment_id=verdict.finding.segment_id if verdict.finding else None,
        findings=finding_views(shown.findings, shown.analysed_segment_ids, numbers),
        findings_remaining=verdict.findings_remaining,
        used_fail_safe=verdict.outcome.used_fail_safe,
        check_at=state.checks[-1].at if state.checks else None,
        named_nuance=named_nuance_view(state, numbers),
    )
