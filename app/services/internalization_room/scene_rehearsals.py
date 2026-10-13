"""The **Scene rehearsal**: a scene recorded whole in the mother tongue, and its frases.

The recording is stored as sent and never heard by the recognizer or the voice; only its
**Scene frases** are, in the session's bridge language. A **Restart** stamps the frases it sets
aside and keeps a copy of the record as it was. Nothing here is ever deleted (ADR 0059).
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    ConflictError,
    FraseOutOfPlace,
    NotFoundError,
    UnknownReferenceError,
    WordlessTelling,
)
from app.db.models.internalization_room import (
    IRSceneFrase,
    IRSceneRehearsal,
    IRSceneRestart,
    IRSceneSaid,
    IRSession,
)
from app.models.internalization_room import SceneRestartSnapshot, SceneSnapshotFrase
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


async def frases_of(
    db: AsyncSession, rehearsal_ids: Sequence[str], *, set_aside_by: str | None = None
) -> dict[str, list[IRSceneFrase]]:
    """Each rehearsal's frases since its last restart, or those `set_aside_by` one, replaced
    ones included, in place order."""
    found = await db.scalars(
        select(IRSceneFrase)
        .where(
            IRSceneFrase.rehearsal_id.in_(rehearsal_ids),
            IRSceneFrase.restart_id.is_(None)
            if set_aside_by is None
            else IRSceneFrase.restart_id == set_aside_by,
        )
        .order_by(IRSceneFrase.starts_ms, IRSceneFrase.created_at)
    )
    frases: dict[str, list[IRSceneFrase]] = {rehearsal_id: [] for rehearsal_id in rehearsal_ids}
    for frase in found:
        frases[frase.rehearsal_id].append(frase)
    return frases


def replaced_by(frases: Sequence[IRSceneFrase]) -> dict[str, str]:
    return {frase.replaces_id: frase.id for frase in frases if frase.replaces_id is not None}


async def restarts_of(
    db: AsyncSession, rehearsal_ids: Sequence[str]
) -> dict[str, list[IRSceneRestart]]:
    found = await db.scalars(
        select(IRSceneRestart)
        .where(IRSceneRestart.rehearsal_id.in_(rehearsal_ids))
        .order_by(IRSceneRestart.n)
    )
    restarts: dict[str, list[IRSceneRestart]] = {rehearsal_id: [] for rehearsal_id in rehearsal_ids}
    for restart in found:
        restarts[restart.rehearsal_id].append(restart)
    return restarts


def _closing(restarts: Sequence[IRSceneRestart], after_restart: str | None) -> str | None:
    """The restart that closed the attempt a frase was recorded in, or ``None`` while it is open.

    A frase names the restart its attempt follows. Sent after the next restart had landed, it
    belongs to the attempt that restart set aside, and is set aside with it.
    """
    attempt = 0
    if after_restart is not None:
        ids = [restart.id for restart in restarts]
        if after_restart not in ids:
            raise UnknownReferenceError(f"Restart {after_restart} is not one of this scene's")
        attempt = ids.index(after_restart) + 1
    return restarts[attempt].id if attempt < len(restarts) else None


def _refuse_a_sent(rehearsal: IRSceneRehearsal) -> None:
    if rehearsal.sent_at is not None:
        raise ConflictError(f"Scene rehearsal {rehearsal.id} was sent and is frozen")


def _refuse_a_place_outside(rehearsal: IRSceneRehearsal, starts_ms: int, ends_ms: int) -> None:
    beyond = rehearsal.duration_ms is not None and ends_ms > rehearsal.duration_ms
    if starts_ms < 0 or ends_ms <= starts_ms or beyond:
        raise FraseOutOfPlace(
            f"A frase from {starts_ms} ms to {ends_ms} ms has no place in a recording of "
            f"{rehearsal.duration_ms} ms"
        )


async def _current_of_the_chain(
    db: AsyncSession, rehearsal: IRSceneRehearsal, replaces: str, set_aside_by: str | None
) -> str:
    """The current frase of the chain `replaces` belongs to, whichever version it names.

    A team that records one frase again offline, and again, can only name the version it had.
    """
    frases = (await frases_of(db, [rehearsal.id], set_aside_by=set_aside_by))[rehearsal.id]
    if replaces not in {frase.id for frase in frases}:
        raise UnknownReferenceError(f"Scene frase {replaces} is not a frase of this attempt")
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
    after_restart: str | None,
    audio: bytes,
    content_type: str,
    filename: str | None,
    store: TakeStore | None = None,
) -> IRSceneFrase:
    """One frase of the scene, heard in the bridge language; the same bytes are the same frase.

    The bytes are stored before they are heard, so a frase with no words keeps its audio and
    is refused as `WordlessTelling`, becoming no frase. Hearing takes seconds, so what it lands
    on is read again under the rehearsal's lock, which a restart takes too: a rehearsal sent
    meanwhile refuses the frase, one archived meanwhile stamps it, one restarted meanwhile sets
    it aside, and a frase replaced meanwhile is replaced at its newest.
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
    set_aside_by = _closing((await restarts_of(db, [rehearsal.id]))[rehearsal.id], after_restart)
    if replaces is not None:
        await _current_of_the_chain(db, rehearsal, replaces, set_aside_by)
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
    set_aside_by = _closing((await restarts_of(db, [rehearsal.id]))[rehearsal.id], after_restart)
    chain_head = (
        None
        if replaces is None
        else await _current_of_the_chain(db, rehearsal, replaces, set_aside_by)
    )

    frase = IRSceneFrase(
        id=str(uuid.uuid4()),
        rehearsal_id=rehearsal.id,
        session_id=session.id,
        starts_ms=starts_ms,
        ends_ms=ends_ms,
        replaces_id=chain_head,
        transcript=text,
        restart_id=set_aside_by,
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


async def restart_the_scene_translation(
    db: AsyncSession, rehearsal: IRSceneRehearsal
) -> IRSceneRestart:
    """«recomeçar a tradução»: a numbered restart with the record as it was, its frases stamped.

    Taken under the rehearsal's lock, as a frase lands: a frase either lands before it and is
    set aside by it, or after it and reads it.
    """
    rehearsal = await _locked(db, rehearsal.id)
    _refuse_a_sent(rehearsal)
    frases = (await frases_of(db, [rehearsal.id]))[rehearsal.id]
    done = (await restarts_of(db, [rehearsal.id]))[rehearsal.id]
    restart = IRSceneRestart(
        id=str(uuid.uuid4()),
        rehearsal_id=rehearsal.id,
        session_id=rehearsal.session_id,
        n=len(done) + 1,
        snapshot=SceneRestartSnapshot(
            n=rehearsal.n,
            scene=rehearsal.scene,
            scene_said=rehearsal.scene_said,
            scene_guess=rehearsal.scene_guess,
            duration_ms=rehearsal.duration_ms,
            sha256=rehearsal.sha256,
            frases=[
                SceneSnapshotFrase(
                    frase_id=frase.id,
                    starts_ms=frase.starts_ms,
                    ends_ms=frase.ends_ms,
                    replaces=frase.replaces_id,
                    transcript=frase.transcript,
                )
                for frase in frases
            ],
        ).model_dump(),
    )
    db.add(restart)
    await db.execute(
        update(IRSceneFrase)
        .where(IRSceneFrase.id.in_([frase.id for frase in frases]))
        .values(restart_id=restart.id)
        .execution_options(synchronize_session=False)
    )
    await db.commit()
    return restart
