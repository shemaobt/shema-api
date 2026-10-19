from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRSegment, IRSession, IRTake, IRTakeKind
from app.services.internalization_room.back_translation import LaidInSentence
from app.services.internalization_room.fail_safe import her_line
from app.services.internalization_room.languages import room_language
from app.services.internalization_room.segments import current_segments, final_segments, told_back
from app.services.internalization_room.sessions import back_translation_of, save_back_translation
from app.services.internalization_room.takes import (
    TakeStore,
    is_wav,
    storage_key,
    store_recording,
    take_by_id,
)
from app.services.internalization_room.wav import pcm16, splice_sentence, trim_silence

WAV = "audio/wav"
SENTENCE_LIMIT_BYTES = 4 * 1024 * 1024
SHORTEST_SENTENCE_MS = 500


@dataclass(frozen=True)
class AwaitingSentence:
    segment_id: str
    frase: int
    line: str


class SentenceRefused(Exception):
    def __init__(self, status_code: int, code: str, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.code = code
        self.detail = detail


def _not_wav(part: IRTake) -> SentenceRefused:
    return SentenceRefused(
        409, "PART_NOT_WAV", f"Part {part.id} was not recorded as WAV PCM16; record the part again"
    )


def refuse_a_sentence_too_long(audio: bytes) -> None:
    if len(audio) > SENTENCE_LIMIT_BYTES:
        raise SentenceRefused(
            413, "SENTENCE_TOO_LONG", f"A sentence weighs at most {SENTENCE_LIMIT_BYTES} bytes"
        )


async def lay_in_a_sentence(
    db: AsyncSession,
    session: IRSession,
    segment: IRSegment,
    *,
    sentence_id: str,
    audio: bytes,
    device_id: str,
    store: TakeStore,
) -> IRTake:
    await db.execute(select(IRSession.id).where(IRSession.id == session.id).with_for_update())
    await db.refresh(session)
    await db.refresh(segment)
    laid_before = next(
        (one for one in back_translation_of(session).sentences if one.sentence_id == sentence_id),
        None,
    )
    if laid_before is not None:
        if (laid_before.sha256, laid_before.segment_id) != (
            hashlib.sha256(audio).hexdigest(),
            segment.id,
        ):
            raise SentenceRefused(
                409,
                "SENTENCE_ID_REUSED",
                f"Sentence {sentence_id} was already laid in with another recording",
            )
        return await take_by_id(db, laid_before.take_id)
    part = await take_by_id(db, segment.take_id)
    if not is_wav(part.content_type):
        raise _not_wav(part)
    base = pcm16(await store.get(part.storage_key) or b"")
    if base is None:
        raise _not_wav(part)
    sentence = pcm16(audio)
    if sentence is None or (sentence.rate, sentence.channels) != (base.rate, base.channels):
        raise SentenceRefused(
            400,
            "SENTENCE_FORMAT_DIFFERS",
            f"A sentence is WAV PCM16 at {base.rate} Hz, {base.channels} channel(s), as its part",
        )
    laid = trim_silence(sentence)
    if sentence.ms(laid.frames) < SHORTEST_SENTENCE_MS:
        raise SentenceRefused(
            400, "SENTENCE_TOO_SHORT", f"A sentence lasts at least {SHORTEST_SENTENCE_MS} ms"
        )
    spliced = splice_sentence(base, segment.starts_ms, segment.ends_ms, laid)
    recorded = hashlib.sha256(audio).hexdigest()
    raw = await store_recording(
        audio,
        key=_sentence_key(session.id, recorded),
        sha256=recorded,
        content_type=WAV,
        store=store,
    )
    digest = hashlib.sha256(spliced.audio).hexdigest()
    stored = await store_recording(
        spliced.audio,
        key=storage_key(session.id, IRTakeKind.ENSAIO, digest, WAV),
        sha256=digest,
        content_type=WAV,
        store=store,
    )
    take = IRTake(
        id=str(uuid.uuid4()),
        project_id=part.project_id,
        session_id=session.id,
        device_id=device_id,
        pericope=part.pericope,
        kind=IRTakeKind.ENSAIO,
        scope=part.scope,
        pass_number=part.pass_number,
        ordinal=part.ordinal,
        storage_key=stored.storage_key,
        size_bytes=stored.size_bytes,
        sha256=stored.sha256,
        crc32c=stored.crc32c,
        content_type=WAV,
        verified_at=stored.verified_at,
        created_at=datetime.now(UTC),
    )
    db.add(take)
    old_end = segment.ends_ms
    shift = spliced.ends_ms - old_end
    for one in await current_segments(db, session.id):
        if one.take_id != part.id:
            continue
        if one.id == segment.id:
            one.ends_ms = spliced.ends_ms
        elif one.starts_ms >= old_end:
            one.starts_ms += shift
            one.ends_ms += shift
        one.take_id = take.id
    state = back_translation_of(session)
    state.sentences.append(
        LaidInSentence(
            sentence_id=sentence_id,
            segment_id=segment.id,
            previous_take_id=part.id,
            take_id=take.id,
            starts_ms=segment.starts_ms,
            ends_ms=spliced.ends_ms,
            sha256=raw.sha256,
            storage_key=raw.storage_key,
            at=take.created_at,
        )
    )
    await save_back_translation(db, session, state, commit=False)
    await db.commit()
    return take


def _sentence_key(session_id: str, sha256: str) -> str:
    return f"internalization-room/takes/{session_id}/sentence/{sha256}/frase.wav"


async def the_sentence_awaiting(db: AsyncSession, session: IRSession) -> AwaitingSentence | None:
    told = told_back(await final_segments(db, session.id))
    for entry in reversed(back_translation_of(session).sentences):
        for number, frase in enumerate(told, start=1):
            if (frase.id, frase.take_id) == (entry.segment_id, entry.take_id):
                return AwaitingSentence(
                    segment_id=frase.id,
                    frase=number,
                    line=her_line("N5", room_language(session.language)) or "",
                )
    return None
