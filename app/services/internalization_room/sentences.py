from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRSegment, IRSession, IRTake, IRTakeKind
from app.services.internalization_room.segments import current_segments
from app.services.internalization_room.takes import (
    TakeStore,
    storage_key,
    store_recording,
    take_by_id,
)
from app.services.internalization_room.wav import pcm16, splice_sentence, trim_silence

WAV = "audio/wav"


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
    base = pcm16(await store.get(part.storage_key) or b"")
    sentence = pcm16(audio)
    spliced = splice_sentence(base, segment.starts_ms, segment.ends_ms, trim_silence(sentence))
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
