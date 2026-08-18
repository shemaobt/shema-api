from __future__ import annotations

import base64
import hashlib
import uuid
from datetime import UTC, datetime
from typing import Protocol

from google_crc32c import Checksum
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.exceptions import NotFoundError, ValidationError
from app.db.models.internalization_room import IRTake, IRTakeKind
from app.services.oral_collector.gcs_utils import generate_signed_download_url
from app.services.platform.storage import GcsPlatformStore, StoredObject

AUDIO_MIME = "audio/mp4"
MAX_TAKE_BYTES = 25 * 1024 * 1024
LISTEN_MINUTES = 15

FILENAMES = {IRTakeKind.ENSAIO: "tomada.m4a", IRTakeKind.RETRO: "trecho.m4a"}


class TakeStore(Protocol):
    """What a take needs from storage: write it, read it, and ask about it.

    `stat` is the one the platform store did not have. It is what separates "the API
    stored what it received" from "the bucket holds it".
    """

    async def get(self, key: str) -> bytes | None: ...

    async def put(self, key: str, data: bytes, content_type: str) -> None: ...

    async def stat(self, key: str) -> StoredObject | None: ...


def _store(settings: Settings | None = None) -> TakeStore:
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
    store: TakeStore | None = None,
) -> IRTake:
    """Put the bytes in the bucket, read it back, then record where it is.

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

    speech_store = store or _store()
    await speech_store.put(key, audio, content_type)
    crc32c = _crc32c(audio)
    landed = await speech_store.stat(key)
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
        crc32c=crc32c,
        content_type=content_type,
        verified_at=_verified(landed, size=len(audio), crc32c=crc32c),
    )
    db.add(take)
    await db.commit()
    await db.refresh(take)
    return take


def _verified(landed: StoredObject | None, *, size: int, crc32c: str) -> datetime | None:
    """A timestamp only when the bucket's own accounting matches what was sent.

    Not raising is deliberate. The object is there either way, and refusing the request
    would tell the app to keep trying — which re-sends the same bytes to the same
    content-addressed key and reproduces the same mismatch. An unverified row is a row
    somebody can go and look at; a lost take is not.
    """
    if landed is None or landed.size != size or landed.crc32c != crc32c:
        return None
    return datetime.now(UTC)


async def take_by_id(db: AsyncSession, take_id: str) -> IRTake:
    result = await db.execute(select(IRTake).where(IRTake.id == take_id))
    take = result.scalar_one_or_none()
    if take is None:
        raise NotFoundError(f"Internalization room take {take_id} not found")
    return take


async def listen_url(take: IRTake, *, settings: Settings | None = None) -> str:
    """A short-lived signed URL, so the bytes never pass through the API.

    A rehearsal take is the whole passage; proxying minutes of audio through the
    application server buys nothing over letting storage serve it.
    """
    cfg = settings or get_settings()
    if not cfg.gcs_platform_bucket:
        raise ValidationError("GCS_PLATFORM_BUCKET is not configured")
    return await generate_signed_download_url(
        cfg.gcs_platform_bucket,
        take.storage_key,
        expiry_minutes=LISTEN_MINUTES,
        response_content_type=take.content_type,
    )


async def takes_of(db: AsyncSession, session_id: str) -> list[IRTake]:
    # Ordered by where each take belongs, not only by when it arrived: a retry lands
    # after a later stretch and the created-at order alone puts them in the wrong reading
    # sequence for whoever reviews the session.
    result = await db.execute(
        select(IRTake)
        .where(IRTake.session_id == session_id)
        .order_by(IRTake.chunk_index, IRTake.pass_number, IRTake.created_at)
    )
    return list(result.scalars().all())
