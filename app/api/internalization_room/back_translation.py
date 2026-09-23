from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.internalization_room._deps import device_dep, device_project_dep, room_caller_dep
from app.core.config import get_settings
from app.core.database import get_db
from app.core.exceptions import ValidationError
from app.core.stage_clock import stage, stopwatch
from app.db.models.internalization_room import IRSession, IRTakeKind
from app.models.internalization_room import (
    BackTranslationChunkResponse,
    BackTranslationVerdictResponse,
    FinishBackTranslationRequest,
)
from app.services import internalization_room as room
from app.services.internalization_room.fail_safe import FailSafe, choose, process_line
from app.services.internalization_room.hearing import heard
from app.services.internalization_room.segments import refuse_a_slice_that_is_not_one
from app.services.internalization_room.takes import (
    current_parts,
    rehearsal_take_of,
    store_take,
    takes_of,
)
from app.services.internalization_room.voice_handles import clip_url

router = APIRouter()

MAX_AUDIO_BYTES = 25 * 1024 * 1024


@router.post(
    "/sessions/{session_id}/back-translation/chunks",
    response_model=BackTranslationChunkResponse,
    dependencies=[room_caller_dep],
)
async def add_chunk(
    session_id: str,
    file: UploadFile = File(...),
    take_id: str = Form(...),
    starts_ms: int = Form(...),
    ends_ms: int = Form(...),
    retelling: bool = Form(default=False),
    device_id: str = device_dep,
    project_id: str | None = device_project_dep,
    db: AsyncSession = Depends(get_db),
) -> BackTranslationChunkResponse:
    """One piece told back in the bridge language, while the team's own recording plays.

    Nothing is voiced here: the clip resuming is the acknowledgement, so this returns no audio.

    The audio is kept, and kept before anything is asked of it. It already crosses the wire to
    be transcribed, and a back translation nobody can listen to is a claim about a recording
    rather than the recording itself. Storing after the hearing would lose it in the two
    moments the team re-records: a transcriber that times out raises past the store, and a
    chunk nobody could make out returns before it.

    `retelling` says the team is telling one stretch back a second time after a finding, and
    the address they send is that stretch's own. So a retelling is a **new version of the
    stretch it retells**, not a stretch of its own at the next position: the row it replaces
    stops counting and hands it the count of tellings that stretch has had. At
    `RETELLS_BEFORE_A_WARNING` the stretch is a hard stretch and the room asks for a person to
    come and watch, once. A warning, not a cap — nothing is refused past it, and the chunk is
    kept either way. Their work is never the thing thrown away.

    A retelling of a slice no stretch currently covers is a first telling: the untold stretch
    the room leads the team to arrives with the flag on and nothing to replace.

    **The attempt is counted, not the transcript.** A telling nobody could make out captures no
    stretch, so it is counted on the row that is standing. Leaving it free meant that during a
    transcriber outage — when every attempt comes back empty — the team could tell one stretch
    forever without ever reaching three, and the room's only route to a person was unreachable
    exactly when the room was broken.

    That ask is a `WARNING` and not a hard stop (ENG-706): the room wants somebody to come and
    watch, and refuses nothing — the team may go on telling. Naming the kind is what lets the
    Desk tell this walk from the one where the room has actually stopped.

    `take_id` names the rehearsal recording this piece explains, and `starts_ms`/`ends_ms` the
    slice inside **that file** — where the team let it play and where they stopped it. All
    three are required. The times used to be optional and counted over the whole passage as if
    it were one recording, which is what made re-recording one stretch move every stretch after
    it; a slice with no file to be a slice of would be the same defect under another name.
    """
    session = (
        await room.get_session_for_room_caller(db, session_id, project_id)
        if project_id is not None
        else await room.get_session(db, session_id)
    )
    rehearsal = await rehearsal_take_of(db, session.id, take_id)
    refuse_a_slice_that_is_not_one(starts_ms, ends_ms)
    audio_bytes = await file.read()
    if len(audio_bytes) > MAX_AUDIO_BYTES:
        raise ValidationError("Audio payload exceeds 25 MB limit")

    state = room.back_translation_of(session)
    told = await room.final_segments(db, session.id)
    retold = (
        await room.current_stretch_at(
            db, session.id, take_id=rehearsal.id, starts_ms=starts_ms, ends_ms=ends_ms
        )
        if retelling
        else None
    )
    pass_number = 2 if retelling else 1

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

    text = await heard(audio_bytes, filename=file.filename, mime_type=file.content_type)
    if not text.strip():
        warned = retold is not None and await room.count_an_empty_telling(db, session, retold)
        return BackTranslationChunkResponse(
            session_id=session.id,
            chunks=len(told),
            captured=False,
            pass_number=pass_number,
            needs_person=warned,
        )
    warned = await room.capture_and_note_a_hard_stretch(
        db,
        session,
        take_id=rehearsal.id,
        starts_ms=starts_ms,
        ends_ms=ends_ms,
        bridge_take_id=retro.id,
        transcript=text,
        pass_number=pass_number,
        replaces=retold,
        state=state,
    )
    return BackTranslationChunkResponse(
        session_id=session.id,
        chunks=len(told) if retold is not None else len(told) + 1,
        captured=True,
        pass_number=pass_number,
        needs_person=warned,
    )


async def _the_untold_errand(
    db: AsyncSession,
    session: IRSession,
    state: room.BackTranslationState,
    *,
    segment_id: str | None = None,
    take_ids: list[str] | None = None,
) -> BackTranslationVerdictResponse:
    """Say the H family over ground nobody has told back, and step the waiting ladder.

    One errand over two grounds: a stretch standing with nothing said on it, and a current
    **Part** no standing stretch is a slice of. The room says the same thing over both — the
    family names no frase, so it is true of either — and the ladder belongs to the errand and
    not to the ground, which is why a press spent on one advances the line the next press
    speaks over the other.

    The answer names its ground on its own field and leaves the other empty, so the app decides
    by the field and never by what is missing from the body.
    """
    waiting, _ = choose(FailSafe.UNTOLD_STRETCH, session.language, turn=state.waited)
    spoken = (await room.synthesize_facilitator_speech(waiting, language=session.language))[0]
    state.waited += 1
    await room.save_back_translation(db, session, state)
    return BackTranslationVerdictResponse(
        session_id=session.id,
        audio_url=clip_url(spoken.key),
        fixed_line="",
        checked=False,
        untold_segment_id=segment_id,
        untold_take_ids=take_ids or [],
        findings_remaining=0,
    )


@router.post(
    "/sessions/{session_id}/back-translation/finish",
    response_model=BackTranslationVerdictResponse,
    dependencies=[room_caller_dep],
)
async def finish(
    session_id: str,
    payload: FinishBackTranslationRequest | None = None,
    project_id: str | None = device_project_dep,
    db: AsyncSession = Depends(get_db),
) -> BackTranslationVerdictResponse:
    """`terminei` — compare the telling-back to the map and voice one finding, or the badge.

    With nothing told back, the analyst is not asked. Given no stretches it answers with no
    findings, and no findings is precisely what `checked` is made of — so `terminei` over an
    empty back translation came back clean, the app closed the necklace and struck the passage
    off the wheel for good, on a telling-back that never happened. A finished passage never
    returns to the wheel, by design, so there is no undo for that.

    The answer is never the badge, then. The D family stood here — *"I could not make anything
    out, can you tell me again?"* — and a team that has recorded and told nothing back no longer
    reaches it: their recording is a current part with nothing over it, which the untold errand
    below answers first and answers truly, because nothing was said for the room to fail to hear
    (ADR 0027). What is left for D is a session carrying no rehearsal take at all, which is the
    one shape where there is no part to send them to.

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

    The H family says so out loud rather than leaving the team with silence. Deliberately not
    the D family below: that one says the room could not hear, which is false here — it heard
    everything — and it asks the team to repeat what they already told instead of telling what
    they have not.

    It is the one line of that file the room speaks rather than the app plays. The fail-safes
    are shipped as audio because they have to work when nothing else does — no network, no
    model — and this is not that: the gate fires with the server answering normally, before
    the analyst is called, and the verdict a few lines below is already synthesized. Shipping
    it would have meant a new app release before the team could hear anything at all.

    The same errand is owed over a **Part** no stretch is a slice of, and it is asked second.
    A part recorded again arrives carrying nobody's words — its predecessor's stretches went
    with the recording they explained (ADR 0023) — so the reading above finds nothing waiting
    and the passage could be conferred with a scene nobody had told back in it. The question
    is the takes' to answer and not the stretches': which recording is current is the number
    the tablet sent, which is why this is asked of `current_parts` and not of `first_untold`.
    It sits between the stretch and the listening, the order the release gate lists the three
    blockers in, because a part nobody told is owed a telling before it is owed a playing, and
    it spends what the stretch spends — the same family of lines, the same turn of the waiting
    ladder — because in the room it is the same errand said over different ground.

    Told back is not the same as heard, and the third errand is asked after the other two.
    While any current part of the rehearsal is unheard, the analyst is not asked either: what it
    would answer is a list of what is missing from the passage, and over a part nobody played
    that sentence is about audio the team never listened to — the room would voice it as if
    the work were done, on a reading of a passage they were still walking through. So the
    refusal names the parts, says her P-unheard line, and spends nothing: no reading, no turn
    on the waiting ladder, which belongs to the untold errand, and no line in the conversation.
    Nothing is saved either, because nothing changed: the report above is already stored.

    Pressed again over the same stretches, the room serves the verdict it already reached and
    consults nothing. The press is the same question, and answering it afresh cost a validator
    and a spoken synthesis every time and wrote the room into the conversation as having spoken
    twice — a false record of the room in front of the team, which outlives the bill. The reply
    is byte-for-byte the first one: the app is not told which press it made, because a second
    shape would be a contract change to say something no caller asked about.

    What counts as the same question is `already_analysed`, the record the analyst was already
    guarded by — one signal, so the four steps of a press can never disagree about whether the
    team told back anything new. A press that reached the analyst and then failed saves nothing
    at all, so the press after it does the whole turn rather than serving a verdict the team
    never heard.
    """
    with stopwatch("[bt-timing]", session_id):
        return await _finished(session_id, payload, project_id, db)


async def _finished(
    session_id: str,
    payload: FinishBackTranslationRequest | None,
    project_id: str | None,
    db: AsyncSession,
) -> BackTranslationVerdictResponse:
    session = (
        await room.get_session_for_room_caller(db, session_id, project_id)
        if project_id is not None
        else await room.get_session(db, session_id)
    )
    state = room.back_translation_of(session)
    final = await room.final_segments(db, session.id)
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

    untold = room.first_untold(final)
    if untold is not None:
        return await _the_untold_errand(db, session, state, segment_id=untold.id)

    rehearsed = room.rehearsed_parts(final)
    takes = await takes_of(db, session.id)
    untold_ground = room.untold_parts(current_parts(takes), rehearsed)
    if untold_ground:
        return await _the_untold_errand(
            db, session, state, take_ids=[part.id for part in untold_ground]
        )

    unheard = room.unheard_parts(state, rehearsed)
    if unheard:
        line, _ = process_line("P", "unheard", session.language)
        spoken = (await room.synthesize_facilitator_speech(line, language=session.language))[0]
        return BackTranslationVerdictResponse(
            session_id=session.id,
            audio_url=clip_url(spoken.key),
            fixed_line="",
            checked=False,
            unheard_take_ids=unheard,
            findings_remaining=0,
        )

    if not told:
        # An analyst asked to compare nothing against the map answers with no findings,
        # and no findings is what `checked` is made of — so pressing `terminei` over an
        # empty back translation blessed the passage and the app struck it off the wheel
        # for good, on a telling-back that never happened. The room says it did not hear
        # anything, which is the line family written for exactly this.
        _, line = choose(
            FailSafe.INAUDIBLE,
            session.language,
            turn=len(session.messages or []),
        )
        return BackTranslationVerdictResponse(
            session_id=session.id,
            audio_url="",
            fixed_line=line,
            checked=False,
            findings_remaining=0,
        )

    if state.already_analysed(told) and state.verdict is not None:
        finding = room.the_finding_that_leads(state)
        return BackTranslationVerdictResponse(
            session_id=session.id,
            audio_url=clip_url(state.verdict.clip_key) if state.verdict.clip_key else "",
            fixed_line=state.verdict.fixed_line,
            checked=state.checked,
            finding_kind=finding.kind if finding else None,
            finding_segment_id=finding.segment_id if finding else None,
            findings_remaining=room.findings_remaining(state.findings),
            used_fail_safe=state.verdict.used_fail_safe,
        )

    verdict = await room.check_the_telling_back(
        session,
        state=state,
        told=told,
        retired=await room.retired_segments(db, session.id),
        takes=takes,
        settings=get_settings(),
    )
    with stage("voice"):
        voiced = (
            None
            if verdict.outcome.fixed_line
            else (
                await room.synthesize_facilitator_speech(verdict.said, language=session.language)
            )[0]
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

    return BackTranslationVerdictResponse(
        session_id=session.id,
        audio_url=clip_url(voiced.key) if voiced else "",
        fixed_line=verdict.outcome.fixed_line,
        checked=verdict.checked,
        finding_kind=verdict.finding.kind if verdict.finding else None,
        finding_segment_id=verdict.finding.segment_id if verdict.finding else None,
        findings_remaining=verdict.findings_remaining,
        used_fail_safe=verdict.outcome.used_fail_safe,
    )
