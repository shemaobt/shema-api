from fastapi import APIRouter, Depends, File, Form, Response, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.internalization_room._deps import device_dep, room_caller_dep
from app.core.config import get_settings
from app.core.database import get_db
from app.core.exceptions import UnreadableReply, UpstreamServiceError, ValidationError
from app.db.models.internalization_room import IRPromptKey, IRSessionStatus, IRTakeKind
from app.models.internalization_room import (
    BackTranslationChunkResponse,
    BackTranslationRestartResponse,
    BackTranslationVerdictResponse,
    FinishBackTranslationRequest,
)
from app.services import internalization_room as room
from app.services.internalization_room.back_translation import VoicedVerdict
from app.services.internalization_room.fail_safe import FailSafe, choose
from app.services.internalization_room.hearing import heard
from app.services.internalization_room.languages import LANGUAGE_NAMES
from app.services.internalization_room.prompts import get_prompt_text
from app.services.internalization_room.segments import refuse_a_slice_that_is_not_one
from app.services.internalization_room.sessions import MAX_RETELLS
from app.services.internalization_room.takes import rehearsal_take_of, store_take
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
    db: AsyncSession = Depends(get_db),
) -> BackTranslationChunkResponse:
    """One piece told back in the bridge language, while the team's own recording plays.

    Nothing is voiced here: the clip resuming is the acknowledgement, so this returns no audio.

    The audio is kept, and kept before anything is asked of it. It already crosses the wire to
    be transcribed, and a back translation nobody can listen to is a claim about a recording
    rather than the recording itself. Storing after the hearing would lose it in the two
    moments the team re-records: a transcriber that times out raises past the store, and a
    chunk nobody could make out returns before it.

    `retelling` says the team is telling one stretch back a second time after a finding.
    That is the one cycle they can repeat at will, so it is counted and capped here: past
    the budget the room asks for a person instead of buying another analyst round. The
    chunk is kept either way — their work is never the thing thrown away.

    `take_id` names the rehearsal recording this piece explains, and `starts_ms`/`ends_ms` the
    slice inside **that file** — where the team let it play and where they stopped it. All
    three are required. The times used to be optional and counted over the whole passage as if
    it were one recording, which is what made re-recording one stretch move every stretch after
    it; a slice with no file to be a slice of would be the same defect under another name.
    """
    session = await room.get_session(db, session_id)
    rehearsal = await rehearsal_take_of(db, session.id, take_id)
    refuse_a_slice_that_is_not_one(starts_ms, ends_ms)
    audio_bytes = await file.read()
    if len(audio_bytes) > MAX_AUDIO_BYTES:
        raise ValidationError("Audio payload exceeds 25 MB limit")

    state = room.back_translation_of(session)
    told = await room.final_segments(db, session.id)
    told_again = state.retells + 1 if retelling else state.retells
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
        chunk_index=len(told) + 1,
        content_type=file.content_type or "audio/mp4",
    )

    text = await heard(audio_bytes, filename=file.filename, mime_type=file.content_type)
    if not text.strip():
        # The budget is spent on the attempt, not on the transcript. Returning above this
        # meant that during a transcriber outage — when every attempt comes back empty —
        # the team could retell forever, `MAX_RETELLS` was never reached, and the room's
        # only route to a person was unreachable exactly when the room was broken.
        state.retells = told_again
        await room.save_back_translation(db, session, state)
        spent = retelling and told_again >= MAX_RETELLS
        if spent:
            await room.mark_needs_person(db, session)
        return BackTranslationChunkResponse(
            session_id=session.id,
            chunks=len(told),
            captured=False,
            pass_number=pass_number,
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
        pass_number=pass_number,
    )
    state.scope = state.scope or session.pericope
    state.retells = told_again
    await room.save_back_translation(db, session, state)

    spent = retelling and told_again >= MAX_RETELLS
    if spent:
        await room.mark_needs_person(db, session)
    return BackTranslationChunkResponse(
        session_id=session.id,
        chunks=len(told) + 1,
        captured=True,
        pass_number=pass_number,
        needs_person=spent,
    )


@router.post(
    "/sessions/{session_id}/back-translation/finish",
    response_model=BackTranslationVerdictResponse,
    dependencies=[room_caller_dep],
)
async def finish(
    session_id: str,
    response: Response,
    payload: FinishBackTranslationRequest | None = None,
    db: AsyncSession = Depends(get_db),
) -> BackTranslationVerdictResponse:
    """`terminei` — compare the telling-back to the map and voice one finding, or the badge.

    With nothing told back, the analyst is not asked. Given no stretches it answers with no
    findings, and no findings is precisely what `checked` is made of — so `terminei` over an
    empty back translation came back clean, the app closed the necklace and struck the passage
    off the wheel for good, on a telling-back that never happened. A finished passage never
    returns to the wheel, by design, so there is no undo for that.

    The answer is the D family instead — *"I could not make anything out, can you tell me
    again?"* — which is what the situation actually is, and is already on the tablet as audio.

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
    the D family eight lines below: that one says the room could not hear, which is false here
    — it heard everything — and it asks the team to repeat what they already told instead of
    telling what they have not.

    It is the one line of that file the room speaks rather than the app plays. The fail-safes
    are shipped as audio because they have to work when nothing else does — no network, no
    model — and this is not that: the gate fires with the server answering normally, before
    the analyst is called, and the verdict a few lines below is already synthesized. Shipping
    it would have meant a new app release before the team could hear anything at all.

    **No passage is checked on stretch-by-stretch verifications alone.** A verification answers
    the finding it was shown and nothing else, so a list it emptied has never been measured
    against the set — and two things live only in the set: a correction can answer, by
    accident, a finding raised on another stretch, and whether the telling-back is too thin to
    judge at all. So when nothing is outstanding and only verifications have looked since the
    last whole reading, one whole reading runs, and it is the one that decides. The fast test
    while working; the whole suite before closing.

    It is not paid for twice. The reading turns the flag off and takes the signature with it,
    so pressing `terminei` again with nothing changed reaches neither branch — and a team that
    got it right the first time never turns the flag on at all, so it is checked on one reading
    and not two.

    A closing reading that could not be made saves nothing, exactly as the reading above it
    does: a passage checked because the analyst was unreachable would be struck off the wheel
    on an outage, and a finished passage never comes back.

    A verdict that lands on one stretch carries the I family after it, on the same clip: the
    screen is about to offer a microphone on that stretch — two for most findings, one for a
    missing element — and tapping it replaces everything the team had told there.
    `with_the_whole_stretch_asked_for` is where that is decided.

    A verdict that degraded to a fail-safe carries nothing after it, which the same function
    decides: those are played from inside the app by name, so a sentence appended to one would
    reach the transcript and never the room.

    The request and the verification are two halves of the same correction. This is what asks
    the team for the whole stretch; `verify_correction` a few lines above is what reads what
    they told, against the finding that sent them back. A team that re-recorded only the
    amendment would hand that verification a fragment to judge the finding by.

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
    session = await room.get_session(db, session_id)
    state = room.back_translation_of(session)
    final = await room.final_segments(db, session.id)
    told = room.told_back(final)
    if payload is not None and (payload.played_ranges or payload.clip_duration_ms):
        state = await room.report_playback(
            db,
            session,
            state,
            played_ranges=payload.played_ranges,
            clip_duration_ms=payload.clip_duration_ms,
        )

    untold = room.first_untold(final)
    if untold is not None:
        waiting, _ = choose(
            FailSafe.UNTOLD_STRETCH,
            session.language,
            turn=state.waited,
        )
        spoken = (await room.synthesize_facilitator_speech(waiting, language=session.language))[0]
        state.waited += 1
        await room.save_back_translation(db, session, state)
        return BackTranslationVerdictResponse(
            session_id=session.id,
            audio_url=clip_url(spoken.key),
            fixed_line="",
            checked=False,
            untold_segment_id=untold.id,
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
        finding = state.current_finding
        return BackTranslationVerdictResponse(
            session_id=session.id,
            audio_url=clip_url(state.verdict.clip_key) if state.verdict.clip_key else "",
            fixed_line=state.verdict.fixed_line,
            checked=state.checked,
            finding_kind=finding.kind if finding else None,
            finding_segment_id=finding.segment_id if finding else None,
            findings_remaining=len(state.findings),
            used_fail_safe=state.verdict.used_fail_safe,
        )

    correction = room.correction_to_verify(state, told, await room.retired_segments(db, session.id))
    if correction is not None:
        answered, earlier, corrected = correction
        verified = await room.verify_correction(
            finding=answered,
            earlier=earlier,
            corrected=corrected,
            scope=state.scope or session.pericope,
            pericope_num=session.pericope,
            correction_prompt=get_prompt_text(IRPromptKey.BT_CORRECTION),
            session_language=LANGUAGE_NAMES[session.language],
            settings=get_settings(),
            session_id=session.id,
        )
        if verified is None:
            # Nothing is saved, exactly as on the reading below: a verification that never
            # happened must not read as one that passed. Dropping the finding here would take
            # it off the list for good, and the team would never be asked about it again.
            raise UpstreamServiceError("a verificação da correção não pôde ser feita agora")
        state.findings = room.findings_after_correction(state.findings, verified, corrected)
        state.analysed_segment_ids = [segment.id for segment in told]
        state.verified_since_whole_reading = True
    elif not state.already_analysed(told):
        read = await room.analyse_telling_back(
            segments=told,
            scope=state.scope or session.pericope,
            pericope_num=session.pericope,
            analyst_prompt=get_prompt_text(IRPromptKey.BT_ANALYST),
            session_language=LANGUAGE_NAMES[session.language],
            settings=get_settings(),
            session_id=session.id,
        )
        if read is None:
            # Nothing is saved: `checked` stays as it was and `analysed_segment_ids` does not
            # advance, so pressing `terminei` again actually re-runs the analyst instead of
            # serving a verdict nobody ever reached. An outage never reaches this line: the
            # service raises it as the upstream failure it is.
            raise UnreadableReply("a resposta do analista não pôde ser lida")
        state.findings = read.findings
        state.evidence_sufficient = read.evidence_sufficient
        state.analysed_segment_ids = [segment.id for segment in told]
        state.verified_since_whole_reading = False

    if state.current_finding is None and state.verified_since_whole_reading:
        closing = await room.analyse_telling_back(
            segments=told,
            scope=state.scope or session.pericope,
            pericope_num=session.pericope,
            analyst_prompt=get_prompt_text(IRPromptKey.BT_ANALYST),
            session_language=LANGUAGE_NAMES[session.language],
            settings=get_settings(),
            session_id=session.id,
        )
        if closing is None:
            raise UpstreamServiceError(
                "a leitura final do contado de volta não pôde ser feita agora"
            )
        state.findings = closing.findings
        state.evidence_sufficient = closing.evidence_sufficient
        state.analysed_segment_ids = [segment.id for segment in told]
        state.verified_since_whole_reading = False

    finding = state.current_finding
    state.checked = finding is None and state.evidence_sufficient

    outcome = await room.run_verdict_turn(
        findings_text=room.findings_block(finding),
        closing=room.closing_block(finding, checked=state.checked),
        scope=state.scope or session.pericope,
        pericope_num=session.pericope,
        messages=session.messages or [],
        telling_back=room.segments_block(told),
        speaker_prompt=get_prompt_text(IRPromptKey.BT_VERDICT_SPEAKER),
        validator_prompt=get_prompt_text(IRPromptKey.VALIDATOR),
        session_language=LANGUAGE_NAMES[session.language],
        language_code=session.language,
        settings=get_settings(),
    )

    said = room.with_the_whole_stretch_asked_for(
        outcome.speech,
        finding,
        session.language,
        used_fail_safe=outcome.used_fail_safe,
    )
    voiced = (
        None
        if outcome.fixed_line
        else (await room.synthesize_facilitator_speech(said, language=session.language))[0]
    )
    session = await room.append_exchange(db, session, team_utterance="", guide_response=said)
    state.verdict = VoicedVerdict(
        clip_key=voiced.key if voiced else "",
        fixed_line=outcome.fixed_line,
        used_fail_safe=outcome.used_fail_safe,
    )
    await room.save_back_translation(db, session, state)

    return BackTranslationVerdictResponse(
        session_id=session.id,
        audio_url=clip_url(voiced.key) if voiced else "",
        fixed_line=outcome.fixed_line,
        checked=state.checked,
        finding_kind=finding.kind if finding else None,
        finding_segment_id=finding.segment_id if finding else None,
        findings_remaining=len(state.findings),
        used_fail_safe=outcome.used_fail_safe,
    )


@router.post(
    "/sessions/{session_id}/back-translation/restart",
    response_model=BackTranslationRestartResponse,
    dependencies=[room_caller_dep],
)
async def restart(
    session_id: str,
    db: AsyncSession = Depends(get_db),
) -> BackTranslationRestartResponse:
    """The team threw the recording away and will rehearse again: the telling-back starts over.

    The stretches of the abandoned clip stop counting here. While this had no route, the app
    reset only its own list, so the next `finish` re-analysed the old clip together with the
    new one and the analyst never saw a smaller transcript than the round before.
    """
    session = await room.get_session(db, session_id)
    await room.begin_back_translation_again(db, session)
    return BackTranslationRestartResponse(
        session_id=session.id,
        chunks=len(await room.final_segments(db, session.id)),
        needs_person=session.status is IRSessionStatus.NEEDS_PERSON,
    )
