"""The **Scene rehearsal**: a scene recorded whole in the mother tongue, and its frases.

The recording is stored as sent and never heard by the recognizer or the voice. Nothing
here is ever deleted (ADR 0059).
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
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

NUMBERING_TRIES = 50


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
    Two keeps at once can read the same last number: the unique index refuses the second,
    which walks to the next number, the house loop ``speaker_service`` uses. A loser that
    carried the same bytes answers with the winner instead.
    """
    session_id, project_id, pericope = session.id, session.project_id, session.pericope
    sha256 = recording_digest(audio)
    already = await _the_same_scene(db, session_id, sha256)
    if already is not None:
        return already
    await db.commit()

    stored = await store_recording(
        audio,
        key=f"{_prefix(session_id, sha256)}/cena.{extension(content_type)}",
        sha256=sha256,
        content_type=content_type,
        store=store,
    )
    duration_ms = await measure_ms(audio)
    label = scene if scene in scene_ids_for(pericope) else None
    last = await db.scalar(
        select(func.max(IRSceneRehearsal.n)).where(IRSceneRehearsal.session_id == session_id)
    )
    for n in range((last or 0) + 1, (last or 0) + 1 + NUMBERING_TRIES):
        rehearsal = IRSceneRehearsal(
            id=str(uuid.uuid4()),
            session_id=session_id,
            project_id=project_id,
            pericope=pericope,
            n=n,
            device_id=device_id,
            duration_ms=duration_ms,
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
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            winner = await _the_same_scene(db, session_id, sha256)
            if winner is not None:
                return winner
            continue
        return rehearsal
    raise ConflictError(f"Could not number a scene rehearsal in session {session_id}")


async def _the_same_scene(
    db: AsyncSession, session_id: str, sha256: str
) -> IRSceneRehearsal | None:
    found: IRSceneRehearsal | None = await db.scalar(
        select(IRSceneRehearsal).where(
            IRSceneRehearsal.session_id == session_id, IRSceneRehearsal.sha256 == sha256
        )
    )
    return found


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
