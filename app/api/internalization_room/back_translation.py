from fastapi import APIRouter, Depends, File, Response, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.internalization_room._deps import device_dep, room_key_dep
from app.core.config import get_settings
from app.core.database import get_db
from app.core.exceptions import ValidationError
from app.db.models.internalization_room import IRPromptKey, IRTakeKind
from app.models.internalization_room import (
    BackTranslationChunkResponse,
    BackTranslationVerdictResponse,
)
from app.services import internalization_room as room
from app.services.internalization_room.back_translation import Chunk
from app.services.internalization_room.hearing import heard
from app.services.internalization_room.prompts import get_prompt_text
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
    device_id: str = device_dep,
    db: AsyncSession = Depends(get_db),
) -> BackTranslationChunkResponse:
    """One piece told back in the bridge language, while the team's own recording plays.

    Nothing is voiced here: the clip resuming is the acknowledgement, so this returns no audio.

    The audio is kept. It already crosses the wire to be transcribed, and a back translation
    nobody can listen to is a claim about a recording rather than the recording itself.
    """
    session = await room.get_session(db, session_id)
    audio_bytes = await file.read()
    if len(audio_bytes) > MAX_AUDIO_BYTES:
        raise ValidationError("Audio payload exceeds 25 MB limit")

    text = await heard(audio_bytes, filename=file.filename, mime_type=file.content_type)
    state = room.back_translation_of(session)
    if not text.strip():
        return BackTranslationChunkResponse(
            session_id=session.id, chunks=len(state.chunks), captured=False
        )

    await store_take(
        db,
        session_id=session.id,
        device_id=device_id,
        pericope=session.pericope,
        kind=IRTakeKind.RETRO,
        scope=state.scope or session.pericope,
        audio=audio_bytes,
        pass_number=state.pass_number,
        chunk_index=len(state.chunks) + 1,
        content_type=file.content_type or "audio/mp4",
    )
    state.chunks.append(
        Chunk(index=len(state.chunks) + 1, text=text, pass_number=state.pass_number)
    )
    state.scope = state.scope or session.pericope
    await room.save_back_translation(db, session, state)
    return BackTranslationChunkResponse(
        session_id=session.id, chunks=len(state.chunks), captured=True
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

    state.findings = await room.analyse_telling_back(
        chunks=state.chunks,
        scope=state.scope or session.pericope,
        pericope_num=session.pericope,
        analyst_prompt=await get_prompt_text(db, IRPromptKey.BT_ANALYST),
        settings=get_settings(),
    )
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
        findings_remaining=len(state.findings),
        used_fail_safe=outcome.used_fail_safe,
    )
