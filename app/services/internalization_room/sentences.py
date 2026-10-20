from __future__ import annotations

import asyncio
import hashlib
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    ERROR_CODE_ANOTHER_SENTENCE_AWAITS,
    ERROR_CODE_PART_NOT_WAV,
    ERROR_CODE_SENTENCE_FORMAT_DIFFERS,
    ERROR_CODE_SENTENCE_ID_REUSED,
    ERROR_CODE_SENTENCE_TOO_LONG,
    ERROR_CODE_SENTENCE_TOO_SHORT,
    FraseAwaitsItsTranslation,
    SentenceRefused,
    StretchNoLongerCounts,
)
from app.db.models.internalization_room import IRSegment, IRSession, IRTake, IRTakeKind
from app.services.internalization_room.back_translation import (
    BackTranslationState,
    LaidInSentence,
    frase_numbers,
    unheard_parts,
)
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
from app.services.platform.audio_duration import measure_ms_bounded

WAV = "audio/wav"
SENTENCE_LIMIT_BYTES = 4 * 1024 * 1024
SHORTEST_SENTENCE_MS = 500


@dataclass(frozen=True)
class AwaitingSentence:
    segment_id: str
    frase: int
    line: str


def _not_wav(part: IRTake) -> SentenceRefused:
    return SentenceRefused(
        409,
        ERROR_CODE_PART_NOT_WAV,
        f"Part {part.id} was not recorded as WAV PCM16; record the part again",
    )


def refuse_a_sentence_too_long(audio: bytes) -> None:
    if len(audio) > SENTENCE_LIMIT_BYTES:
        raise SentenceRefused(
            413,
            ERROR_CODE_SENTENCE_TOO_LONG,
            f"A sentence weighs at most {SENTENCE_LIMIT_BYTES} bytes",
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
) -> None:
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
                ERROR_CODE_SENTENCE_ID_REUSED,
                f"Sentence {sentence_id} was already laid in with another recording",
            )
        return
    if segment.id not in {one.id for one in await final_segments(db, session.id)}:
        raise StretchNoLongerCounts("A frase that no longer counts takes no sentence")
    part = await take_by_id(db, segment.take_id)
    if not is_wav(part.content_type):
        raise _not_wav(part)
    base = await asyncio.to_thread(pcm16, await store.get(part.storage_key) or b"")
    if base is None:
        raise _not_wav(part)
    awaiting = await the_sentence_awaiting(db, session)
    if awaiting is not None and awaiting.segment_id != segment.id:
        raise SentenceRefused(
            409,
            ERROR_CODE_ANOTHER_SENTENCE_AWAITS,
            f"Frase {awaiting.frase} awaits its translation; one sentence at a time",
            frases=[awaiting.frase],
        )
    sentence = await asyncio.to_thread(pcm16, audio)
    if sentence is None or (sentence.rate, sentence.channels) != (base.rate, base.channels):
        raise SentenceRefused(
            400,
            ERROR_CODE_SENTENCE_FORMAT_DIFFERS,
            f"A sentence is WAV PCM16 at {base.rate} Hz, {base.channels} channel(s), as its part",
        )
    laid = await asyncio.to_thread(trim_silence, sentence)
    if sentence.ms(laid.frames) < SHORTEST_SENTENCE_MS:
        raise SentenceRefused(
            400,
            ERROR_CODE_SENTENCE_TOO_SHORT,
            f"A sentence lasts at least {SHORTEST_SENTENCE_MS} ms",
        )
    spliced = await asyncio.to_thread(
        splice_sentence, base, segment.starts_ms, segment.ends_ms, laid
    )
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
    now = datetime.now(UTC)
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
        origin=part.origin,
        created_at=now,
        recorded_at=now,
        duration_ms=await measure_ms_bounded(spliced.audio),
    )
    db.add(take)
    state = back_translation_of(session)
    heard_before = not unheard_parts(state, [part], await final_segments(db, session.id))
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
        elif one.ends_ms >= old_end:
            one.ends_ms += shift
        one.take_id = take.id
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
            heard_before=heard_before,
        )
    )
    await _unchecked(state)
    await save_back_translation(db, session, state, commit=False, rule=_unchecked)
    await db.commit()


async def _unchecked(standing: BackTranslationState) -> None:
    standing.checked = False
    standing.verdict = None


def _sentence_key(session_id: str, sha256: str) -> str:
    return f"internalization-room/takes/{session_id}/sentence/{sha256}/frase.wav"


async def the_sentence_awaiting(db: AsyncSession, session: IRSession) -> AwaitingSentence | None:
    laid = back_translation_of(session).sentences
    if not laid:
        return None
    told = told_back(await final_segments(db, session.id))
    numbers = frase_numbers(told)
    on_take = {frase.id: frase.take_id for frase in told}
    for entry in reversed(laid):
        if on_take.get(entry.segment_id) == entry.take_id:
            return AwaitingSentence(
                segment_id=entry.segment_id,
                frase=numbers[entry.segment_id],
                line="N5",
            )
    return None


async def refuse_another_span_for_the_awaiting_frase(
    db: AsyncSession, session: IRSession, segment: IRSegment, starts_ms: int, ends_ms: int
) -> None:
    awaiting = await the_sentence_awaiting(db, session)
    if (
        awaiting is not None
        and awaiting.segment_id == segment.id
        and (starts_ms, ends_ms) != (segment.starts_ms, segment.ends_ms)
    ):
        raise FraseAwaitsItsTranslation(
            f"Frase {awaiting.frase} awaits its translation at exactly "
            f"{segment.starts_ms} to {segment.ends_ms} ms, the span its new sentence took"
        )
