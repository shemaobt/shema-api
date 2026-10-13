"""The **Scene rehearsal**: a scene recorded whole in the mother tongue, and its frases.

The recording is stored as sent and never heard by the recognizer or the voice. Nothing
here is ever deleted (ADR 0059).
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.db.models.internalization_room import IRSceneRehearsal, IRSceneSaid, IRSession
from app.services.internalization_room.canon.scene_ids import scene_ids_for
from app.services.internalization_room.live import live
from app.services.internalization_room.takes import (
    TakeStore,
    extension,
    recording_digest,
    store_recording,
)
from app.services.platform.audio_duration import measure_ms


def _prefix(session_id: str, sha256: str) -> str:
    return f"internalization-room/scene-rehearsals/{session_id}/{sha256}"


async def keep_scene_rehearsal(
    db: AsyncSession,
    session: IRSession,
    *,
    device_id: str,
    audio: bytes,
    content_type: str,
    scene: str | None,
    store: TakeStore | None = None,
) -> IRSceneRehearsal:
    """Store the scene as sent and number it in its session; the same bytes are the same one.

    A scene that is not one of the passage's is kept as no label, never as the team's word.
    """
    sha256 = recording_digest(audio)
    already = await db.scalar(
        select(IRSceneRehearsal).where(
            IRSceneRehearsal.session_id == session.id, IRSceneRehearsal.sha256 == sha256
        )
    )
    if already is not None:
        return already
    await db.commit()

    stored = await store_recording(
        audio,
        key=f"{_prefix(session.id, sha256)}/cena.{extension(content_type)}",
        sha256=sha256,
        content_type=content_type,
        store=store,
    )
    last = await db.scalar(
        select(func.max(IRSceneRehearsal.n)).where(IRSceneRehearsal.session_id == session.id)
    )
    label = scene if scene in scene_ids_for(session.pericope) else None
    rehearsal = IRSceneRehearsal(
        id=str(uuid.uuid4()),
        session_id=session.id,
        project_id=session.project_id,
        pericope=session.pericope,
        n=(last or 0) + 1,
        device_id=device_id,
        duration_ms=await measure_ms(audio),
        scene=label,
        scene_said=IRSceneSaid.RECORDING if label else None,
        storage_key=stored.storage_key,
        size_bytes=stored.size_bytes,
        sha256=stored.sha256,
        crc32c=stored.crc32c,
        content_type=stored.content_type,
        verified_at=stored.verified_at,
    )
    db.add(rehearsal)
    await db.commit()
    return rehearsal


async def scene_rehearsals_of_the_passage(
    db: AsyncSession, session: IRSession
) -> list[IRSceneRehearsal]:
    """The team's live scene rehearsals of this passage, from every live session of it.

    Asked of the session too: a rehearsal that landed after its session's Zerar is not stamped.
    """
    found = await db.scalars(
        select(IRSceneRehearsal)
        .join(IRSession, IRSession.id == IRSceneRehearsal.session_id)
        .where(
            IRSceneRehearsal.project_id == session.project_id,
            IRSceneRehearsal.pericope == session.pericope,
            live(IRSceneRehearsal),
            live(IRSession),
        )
        .order_by(IRSceneRehearsal.created_at, IRSceneRehearsal.n)
    )
    return list(found)


async def scene_rehearsal_in_session(
    db: AsyncSession, session_id: str, rehearsal_id: str
) -> IRSceneRehearsal:
    rehearsal = await db.scalar(
        select(IRSceneRehearsal).where(
            IRSceneRehearsal.id == rehearsal_id, IRSceneRehearsal.session_id == session_id
        )
    )
    if rehearsal is None:
        raise NotFoundError(f"Internalization room scene rehearsal {rehearsal_id} not found")
    return rehearsal
