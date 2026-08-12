from __future__ import annotations

import base64
import hashlib
import uuid

from google_crc32c import Checksum
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.exceptions import ValidationError
from app.db.models.internalization_room import IRTake, IRTakeKind
from app.services.platform.storage import GcsPlatformStore
from app.services.platform.tts import SpeechStore

AUDIO_MIME = "audio/mp4"
MAX_TAKE_BYTES = 25 * 1024 * 1024

FILENAMES = {IRTakeKind.ENSAIO: "tomada.m4a", IRTakeKind.RETRO: "trecho.m4a"}


def _store(settings: Settings | None = None) -> SpeechStore:
    return GcsPlatformStore(settings or get_settings())


def storage_key(session_id: str, kind: IRTakeKind, sha256: str) -> str:
    """Content-addressed, so a failed upload can only ever leave an orphan.

    A stable key would overwrite in place: a second attempt that dies halfway would leave the
    bucket holding half of the new take under the name of the old one, and nothing would say
    so. Addressed by its own hash, a broken upload is an object nothing points at.

    It also makes the whole path idempotent — the same bytes sent twice land on the same
    object and, by the unique constraint, the same row.
    """
    return f"internalization-room/takes/{session_id}/{kind.value}/{sha256}/{FILENAMES[kind]}"


def _crc32c(audio: bytes) -> str:
    checksum = Checksum()
    checksum.update(audio)
    return base64.b64encode(checksum.digest()).decode("ascii")


async def store_take(
    db: AsyncSession,
    *,
    session_id: str,
    device_id: str,
    pericope: str,
    kind: IRTakeKind,
    scope: str,
    audio: bytes,
    pass_number: int | None = None,
    chunk_index: int | None = None,
    content_type: str = AUDIO_MIME,
    store: SpeechStore | None = None,
) -> IRTake:
    """Put the bytes in the bucket, then record where they are.

    That order is deliberate and matches the hand's questions: a row pointing at an object
    that was never written is a take the app believes is safe and nobody can play. The
    reverse — an object with no row — costs storage and nothing else.

    The checksums describe the bytes that were stored, not the bytes that were promised, so
    they are computed here rather than trusted from the request.
    """
    if not audio:
        raise ValidationError("A take with no audio is not a take")
    if len(audio) > MAX_TAKE_BYTES:
        raise ValidationError("Audio payload exceeds 25 MB limit")

    digest = hashlib.sha256(audio).hexdigest()
    key = storage_key(session_id, kind, digest)

    existing = await db.execute(
        select(IRTake).where(IRTake.session_id == session_id, IRTake.storage_key == key)
    )
    already = existing.scalar_one_or_none()
    if already is not None:
        return already

    await (store or _store()).put(key, audio, content_type)
    take = IRTake(
        id=str(uuid.uuid4()),
        session_id=session_id,
        device_id=device_id,
        pericope=pericope,
        kind=kind,
        scope=scope,
        pass_number=pass_number,
        chunk_index=chunk_index,
        storage_key=key,
        size_bytes=len(audio),
        sha256=digest,
        crc32c=_crc32c(audio),
        content_type=content_type,
    )
    db.add(take)
    await db.commit()
    await db.refresh(take)
    return take


async def takes_of(db: AsyncSession, session_id: str) -> list[IRTake]:
    result = await db.execute(
        select(IRTake).where(IRTake.session_id == session_id).order_by(IRTake.created_at)
    )
    return list(result.scalars().all())


async def fetch_take(key: str, *, store: SpeechStore | None = None) -> bytes | None:
    return await (store or _store()).get(key)
