from fastapi import APIRouter, Depends, File, Form, Response, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.internalization_room._deps import device_dep, room_key_dep
from app.core.config import get_settings
from app.core.database import get_db
from app.core.exceptions import UpstreamServiceError, ValidationError
from app.db.models.internalization_room import IRPromptKey, IRSessionStatus, IRTakeKind
from app.models.internalization_room import (
    BackTranslationChunkResponse,
    BackTranslationRestartResponse,
    BackTranslationVerdictResponse,
)
from app.services import internalization_room as room
from app.services.internalization_room.back_translation import Chunk
from app.services.internalization_room.hearing import heard
from app.services.internalization_room.prompts import get_prompt_text
from app.services.internalization_room.sessions import MAX_RETELLS
from app.services.internalization_room.takes import store_take
from app.services.internalization_room.voice_handles import clip_url

router = APIRouter()

MAX_AUDIO_BYTES = 25 * 1024 * 1024


@router.post(
    "/sessions/{session_id}/back-translation/chunks",
    response_model=BackTranslationChunkResponse,
    dependencies=[room_key_dep],
)
async def add_chunk(
    session_id: str,
    file: UploadFile = File(...),
    starts_ms: int | None = Form(default=None),
    ends_ms: int | None = Form(default=None),
    retelling: bool = Form(default=False),
    device_id: str = device_dep,
    db: AsyncSession = Depends(get_db),
) -> BackTranslationChunkResponse:
    """One piece told back in the bridge language, while the team's own recording plays.

    Nothing is voiced here: the clip resuming is the acknowledgement, so this returns no audio.

    The audio is kept. It already crosses the wire to be transcribed, and a back translation
    nobody can listen to is a claim about a recording rather than the recording itself.

    `retelling` says the team is telling one stretch back a second time after a finding.
    That is the one cycle they can repeat at will, so it is counted and capped here: past
    the budget the room asks for a person instead of buying another analyst round. The
    chunk is kept either way — their work is never the thing thrown away.

    `starts_ms`/`ends_ms` say which stretch of the team's recording this piece explains — where
    they let it play and where they stopped it. They are optional so an older app keeps working,
    but without them the piece is only an ordinal and nothing downstream can point at the audio.
    """
    session = await room.get_session(db, session_id)
    audio_bytes = await file.read()
    if len(audio_bytes) > MAX_AUDIO_BYTES:
        raise ValidationError("Audio payload exceeds 25 MB limit")

    text = await heard(audio_bytes, filename=file.filename, mime_type=file.content_type)
    state = room.back_translation_of(session)
    told_again = state.retells + 1 if retelling else state.retells
    pass_number = 2 if retelling else 1

    # Before deciding whether anything was said in it. An empty transcript is either a
    # silent recording or a transcription outage wearing the same shape — `heard` cannot
    # tell them apart — and this returned 200 above the store either way, so a stretch a
    # team had just told stopped existing anywhere. The docstring above promised the
    # opposite, and the app trusted it enough to keep no copy of its own.
    await store_take(
        db,
        session_id=session.id,
        device_id=device_id,
        pericope=session.pericope,
        kind=IRTakeKind.RETRO,
        scope=state.scope or session.pericope,
        audio=audio_bytes,
        pass_number=pass_number,
        chunk_index=len(state.chunks) + 1,
        content_type=file.content_type or "audio/mp4",
    )

    if not text.strip():
        return BackTranslationChunkResponse(
            session_id=session.id,
            chunks=len(state.chunks),
            captured=False,
            pass_number=state.retells + 1 if retelling else 1,
        )
    state.chunks.append(
        Chunk(
            index=len(state.chunks) + 1,
            text=text,
            pass_number=pass_number,
            starts_ms=starts_ms,
            ends_ms=ends_ms,
        )
    )
    state.scope = state.scope or session.pericope
    state.retells = told_again
    await room.save_back_translation(db, session, state)

    spent = retelling and told_again >= MAX_RETELLS
    if spent:
        await room.mark_needs_person(db, session)
    return BackTranslationChunkResponse(
        session_id=session.id,
        chunks=len(state.chunks),
        captured=True,
        pass_number=pass_number,
        needs_person=spent,
    )


@router.post(
    "/sessions/{session_id}/back-translation/finish",
    response_model=BackTranslationVerdictResponse,
    dependencies=[room_key_dep],
)
async def finish(
    session_id: str,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> BackTranslationVerdictResponse:
    """`terminei` — compare the telling-back to the map and voice one finding, or the badge."""
    session = await room.get_session(db, session_id)
    state = room.back_translation_of(session)

    if not state.already_analysed:
        read = await room.analyse_telling_back(
            chunks=state.chunks,
            scope=state.scope or session.pericope,
            pericope_num=session.pericope,
            analyst_prompt=await get_prompt_text(db, IRPromptKey.BT_ANALYST),
            settings=get_settings(),
        )
        if read is None:
            # Nothing is saved: `checked` stays as it was and `analysed_chunks` does not
            # advance, so pressing `terminei` again actually re-runs the analyst instead of
            # serving a verdict nobody ever reached.
            raise UpstreamServiceError("a análise do contado de volta não pôde ser feita agora")
        state.findings = read
        state.analysed_chunks = len(state.chunks)
    finding = state.current_finding
    state.checked = finding is None

    outcome = await room.run_verdict_turn(
        findings_text=room.findings_block(finding),
        scope=state.scope or session.pericope,
        pericope_num=session.pericope,
        messages=session.messages or [],
        speaker_prompt=await get_prompt_text(db, IRPromptKey.BT_VERDICT_SPEAKER),
        validator_prompt=await get_prompt_text(db, IRPromptKey.VALIDATOR),
        settings=get_settings(),
    )

    voiced = (
        None
        if outcome.fixed_line
        else (await room.synthesize_facilitator_speech(outcome.speech))[0]
    )
    session = await room.append_exchange(
        db, session, team_utterance="", guide_response=outcome.speech
    )
    await room.save_back_translation(db, session, state)

    return BackTranslationVerdictResponse(
        session_id=session.id,
        audio_url=clip_url(voiced.key) if voiced else "",
        fixed_line=outcome.fixed_line,
        checked=state.checked,
        finding_kind=finding.kind if finding else None,
        finding_chunk=finding.chunk if finding else None,
        findings_remaining=len(state.findings),
        used_fail_safe=outcome.used_fail_safe,
    )


@router.post(
    "/sessions/{session_id}/back-translation/restart",
    response_model=BackTranslationRestartResponse,
    dependencies=[room_key_dep],
)
async def restart(
    session_id: str,
    db: AsyncSession = Depends(get_db),
) -> BackTranslationRestartResponse:
    """The team threw the recording away and will rehearse again: the telling-back starts over.

    The chunks of the abandoned clip are cleared here. While this had no route, the app reset
    only its own list, so the next `finish` re-analysed the old clip together with the new one
    and the analyst never saw a smaller transcript than the round before.
    """
    session = await room.get_session(db, session_id)
    state = await room.begin_back_translation_again(db, session)
    return BackTranslationRestartResponse(
        session_id=session.id,
        chunks=len(state.chunks),
        needs_person=session.status is IRSessionStatus.NEEDS_PERSON,
    )
