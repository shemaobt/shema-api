"""The **Scene rehearsal**: a scene recorded whole in the mother tongue, and its frases.

The recording is stored as sent and never heard by the recognizer or the voice; only its
**Scene frases** are, in the session's bridge language. Nothing here is ever deleted
(ADR 0059).
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    ConflictError,
    FraseOutOfPlace,
    NotFoundError,
    SceneRehearsalSent,
    UnknownReferenceError,
    WordlessTelling,
)
from app.db.models.internalization_room import (
    IRSceneFrase,
    IRSceneRehearsal,
    IRSceneSaid,
    IRSession,
)
from app.services.internalization_room.canon.scene_ids import scene_ids_for
from app.services.internalization_room.hearing import heard
from app.services.internalization_room.languages import room_language
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


async def frases_of(
    db: AsyncSession, rehearsal_ids: Sequence[str]
) -> dict[str, list[IRSceneFrase]]:
    """Each rehearsal's frases, replaced ones included, in place order."""
    found = await db.scalars(
        select(IRSceneFrase)
        .where(IRSceneFrase.rehearsal_id.in_(rehearsal_ids))
        .order_by(IRSceneFrase.starts_ms, IRSceneFrase.created_at)
    )
    frases: dict[str, list[IRSceneFrase]] = {rehearsal_id: [] for rehearsal_id in rehearsal_ids}
    for frase in found:
        frases[frase.rehearsal_id].append(frase)
    return frases


def replaced_by(frases: Sequence[IRSceneFrase]) -> dict[str, str]:
    return {frase.replaces_id: frase.id for frase in frases if frase.replaces_id is not None}


def _refuse_a_sent(rehearsal: IRSceneRehearsal) -> None:
    if rehearsal.sent_at is not None:
        raise SceneRehearsalSent(f"Scene rehearsal {rehearsal.id} was sent and is frozen")


def _refuse_a_place_outside(rehearsal: IRSceneRehearsal, starts_ms: int, ends_ms: int) -> None:
    beyond = rehearsal.duration_ms is not None and ends_ms > rehearsal.duration_ms
    if starts_ms < 0 or ends_ms <= starts_ms or beyond:
        raise FraseOutOfPlace(
            f"A frase from {starts_ms} ms to {ends_ms} ms has no place in a recording of "
            f"{rehearsal.duration_ms} ms"
        )


async def _current_of_the_chain(
    db: AsyncSession, rehearsal: IRSceneRehearsal, replaces: str
) -> str:
    """The current frase of the chain `replaces` belongs to, whichever version it names.

    A team that records one frase again offline, and again, can only name the version it had.
    """
    frases = (await frases_of(db, [rehearsal.id]))[rehearsal.id]
    if replaces not in {frase.id for frase in frases}:
        raise UnknownReferenceError(f"Scene frase {replaces} is not a frase of this scene")
    replacing = replaced_by(frases)
    current = replaces
    while current in replacing:
        current = replacing[current]
    return current


async def _locked(db: AsyncSession, rehearsal_id: str) -> IRSceneRehearsal:
    """The rehearsal read again under a row lock, so what lands on it lands one at a time."""
    found = await db.scalars(
        select(IRSceneRehearsal)
        .where(IRSceneRehearsal.id == rehearsal_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return found.one()


async def keep_a_frase(
    db: AsyncSession,
    session: IRSession,
    rehearsal: IRSceneRehearsal,
    *,
    starts_ms: int,
    ends_ms: int,
    replaces: str | None,
    audio: bytes,
    content_type: str,
    filename: str | None,
    store: TakeStore | None = None,
) -> IRSceneFrase:
    """One frase of the scene, heard in the bridge language; the same bytes are the same frase.

    The bytes are stored before they are heard, so a frase with no words keeps its audio and
    is refused as `WordlessTelling`, becoming no frase. Hearing takes seconds, so what it lands
    on is read again under the rehearsal's lock: a rehearsal sent meanwhile refuses the frase,
    one archived meanwhile stamps it, and a frase replaced meanwhile is replaced at its newest.
    """
    sha256 = recording_digest(audio)
    already = await db.scalar(
        select(IRSceneFrase).where(
            IRSceneFrase.rehearsal_id == rehearsal.id, IRSceneFrase.sha256 == sha256
        )
    )
    if already is not None:
        return already
    _refuse_a_sent(rehearsal)
    _refuse_a_place_outside(rehearsal, starts_ms, ends_ms)
    if replaces is not None:
        await _current_of_the_chain(db, rehearsal, replaces)
    await db.commit()

    folder = f"{_prefix(session.id, rehearsal.sha256)}/frases/{sha256}"
    stored = await store_recording(
        audio,
        key=f"{folder}/frase.{extension(content_type)}",
        sha256=sha256,
        content_type=content_type,
        store=store,
    )
    text = await heard(
        audio, language=room_language(session.language), filename=filename, mime_type=content_type
    )
    if not text.strip():
        raise WordlessTelling()
    rehearsal = await _locked(db, rehearsal.id)
    _refuse_a_sent(rehearsal)

    frase = IRSceneFrase(
        id=str(uuid.uuid4()),
        rehearsal_id=rehearsal.id,
        session_id=session.id,
        starts_ms=starts_ms,
        ends_ms=ends_ms,
        replaces_id=None
        if replaces is None
        else await _current_of_the_chain(db, rehearsal, replaces),
        transcript=text,
        storage_key=stored.storage_key,
        size_bytes=stored.size_bytes,
        sha256=stored.sha256,
        crc32c=stored.crc32c,
        content_type=stored.content_type,
        verified_at=stored.verified_at,
        archive_id=rehearsal.archive_id,
    )
    db.add(frase)
    await db.commit()
    return frase
