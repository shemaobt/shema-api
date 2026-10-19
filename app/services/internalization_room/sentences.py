from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRSegment, IRSession, IRTake, IRTakeKind
from app.services.internalization_room.segments import current_segments
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
    audio: bytes,
    device_id: str,
    store: TakeStore,
) -> IRTake:
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
    await db.commit()
    return take
