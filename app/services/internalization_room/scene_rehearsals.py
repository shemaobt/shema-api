"""The **Scene rehearsal**: a scene recorded whole in the mother tongue, and its frases.

The recording is stored as sent and never heard by the recognizer or the voice; only its
**Scene frases** are, in the session's bridge language. A **Restart** stamps the frases it sets
aside and keeps a copy of the record as it was. Nothing here is ever deleted (ADR 0059).
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Exists, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.core.exceptions import (
    ConflictError,
    FraseOutOfPlace,
    NotFoundError,
    RestartOutOfOrder,
    SceneRehearsalSending,
    SceneRehearsalSent,
    SceneRehearsalUntranslated,
    UnknownReferenceError,
    WordlessTelling,
)
from app.db.models.internalization_room import (
    IRSceneFrase,
    IRSceneRehearsal,
    IRSceneRestart,
    IRSceneSaid,
    IRSession,
    IRTurn,
)
from app.models.internalization_room import (
    SceneRestartSnapshot,
    SceneSnapshotFrase,
    TurnResponse,
)
from app.services.internalization_room.canon.scene_ids import scene_ids_for
from app.services.internalization_room.hearing import HeardSpeech, SentSceneRehearsal, heard
from app.services.internalization_room.languages import room_language
from app.services.internalization_room.live import live
from app.services.internalization_room.opening_claim import (
    Draft,
    answer_around_the_opening,
    oldest_live_claim,
)
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


async def scene_rehearsals_of_the_session(
    db: AsyncSession, session_id: str
) -> list[IRSceneRehearsal]:
    """Every scene rehearsal recorded in this session, archived or not, for the reader."""
    found = await db.scalars(
        select(IRSceneRehearsal)
        .where(IRSceneRehearsal.session_id == session_id)
        .order_by(IRSceneRehearsal.n)
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


def current_attempt(restarts: Sequence[IRSceneRestart]) -> str | None:
    """The attempt the rehearsal's translation is on: the id of its last restart, or none."""
    return restarts[-1].id if restarts else None


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


async def frases_of(
    db: AsyncSession, restarts: dict[str, list[IRSceneRestart]]
) -> dict[str, list[IRSceneFrase]]:
    """Each rehearsal's frases of its current attempt, replaced ones included, in place order.

    Handed the restarts the caller already read, so the attempt it answers with and the
    frases it filters by come from one read. A frase naming an attempt whose restart has not
    landed yet is held: it is in no list until that restart lands and makes it current.
    """
    rehearsal_ids = list(restarts)
    attempts = {rehearsal_id: current_attempt(done) for rehearsal_id, done in restarts.items()}
    found = await db.scalars(
        select(IRSceneFrase)
        .where(IRSceneFrase.rehearsal_id.in_(rehearsal_ids), IRSceneFrase.restart_id.is_(None))
        .order_by(IRSceneFrase.starts_ms, IRSceneFrase.created_at)
    )
    frases: dict[str, list[IRSceneFrase]] = {rehearsal_id: [] for rehearsal_id in rehearsal_ids}
    for frase in found:
        if frase.attempt == attempts[frase.rehearsal_id]:
            frases[frase.rehearsal_id].append(frase)
    return frases


async def set_aside_frases(
    db: AsyncSession, rehearsal_ids: Sequence[str]
) -> dict[str, list[IRSceneFrase]]:
    """The frases each restart set aside, by restart, those that arrived after it included."""
    found = await db.scalars(
        select(IRSceneFrase)
        .where(IRSceneFrase.rehearsal_id.in_(rehearsal_ids), IRSceneFrase.restart_id.is_not(None))
        .order_by(IRSceneFrase.starts_ms, IRSceneFrase.created_at)
    )
    set_aside: dict[str, list[IRSceneFrase]] = {}
    for frase in found:
        set_aside.setdefault(str(frase.restart_id), []).append(frase)
    return set_aside


async def held_frases(
    db: AsyncSession, restarts: dict[str, list[IRSceneRestart]]
) -> dict[str, dict[str, list[IRSceneFrase]]]:
    """By rehearsal and by attempt, the frases naming an attempt whose restart never landed,
    measured against the restarts the caller already read."""
    rehearsal_ids = list(restarts)
    landed = {
        rehearsal_id: {restart.id for restart in done} for rehearsal_id, done in restarts.items()
    }
    found = await db.scalars(
        select(IRSceneFrase)
        .where(
            IRSceneFrase.rehearsal_id.in_(rehearsal_ids),
            IRSceneFrase.restart_id.is_(None),
            IRSceneFrase.attempt.is_not(None),
        )
        .order_by(IRSceneFrase.starts_ms, IRSceneFrase.created_at)
    )
    held: dict[str, dict[str, list[IRSceneFrase]]] = {
        rehearsal_id: {} for rehearsal_id in rehearsal_ids
    }
    for frase in found:
        if frase.attempt is not None and frase.attempt not in landed[frase.rehearsal_id]:
            held[frase.rehearsal_id].setdefault(frase.attempt, []).append(frase)
    return held


def replaced_by(frases: Sequence[IRSceneFrase]) -> dict[str, str]:
    return {frase.replaces_id: frase.id for frase in frases if frase.replaces_id is not None}


def _closing(restarts: Sequence[IRSceneRestart], attempt: str | None) -> str | None:
    """The restart that closed `attempt`, or ``None`` while it is open or not landed yet.

    A frase names the attempt it was recorded in, the restart it follows. Sent after the next
    restart had landed, it is set aside with the rest of its attempt.
    """
    ids = [None, *(restart.id for restart in restarts)]
    if attempt not in ids:
        return None
    following = ids.index(attempt)
    return restarts[following].id if following < len(restarts) else None


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
    db: AsyncSession, rehearsal: IRSceneRehearsal, replaces: str, attempt: str | None
) -> str:
    """The current frase of the chain `replaces` belongs to, whichever version it names.

    A team that records one frase again offline, and again, can only name the version it had.
    """
    found = await db.scalars(
        select(IRSceneFrase).where(
            IRSceneFrase.rehearsal_id == rehearsal.id,
            IRSceneFrase.attempt.is_not_distinct_from(attempt),
        )
    )
    frases = list(found)
    if replaces not in {frase.id for frase in frases}:
        raise UnknownReferenceError(f"Scene frase {replaces} is not a frase of this attempt")
    replacing = replaced_by(frases)
    current = replaces
    while current in replacing:
        current = replacing[current]
    return current


async def _refuse_another_rehearsals_attempt(
    db: AsyncSession, rehearsal: IRSceneRehearsal, attempt: str
) -> None:
    named = await db.get(IRSceneRestart, attempt)
    if named is not None and named.rehearsal_id != rehearsal.id:
        raise UnknownReferenceError(f"Restart {attempt} belongs to another scene rehearsal")


async def _the_same_frase(db: AsyncSession, rehearsal_id: str, sha256: str) -> IRSceneFrase | None:
    found: IRSceneFrase | None = await db.scalar(
        select(IRSceneFrase).where(
            IRSceneFrase.rehearsal_id == rehearsal_id, IRSceneFrase.sha256 == sha256
        )
    )
    return found


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
    on is read again under the rehearsal's lock, which a restart takes too: the same frase
    resent meanwhile is answered with the first, a rehearsal sent meanwhile refuses the frase,
    one archived meanwhile stamps it, one restarted meanwhile sets it aside, and a frase replaced
    meanwhile is replaced at its newest.
    """
    sha256 = recording_digest(audio)
    already = await _the_same_frase(db, rehearsal.id, sha256)
    if already is not None:
        return already
    _refuse_a_sent(rehearsal)
    _refuse_a_place_outside(rehearsal, starts_ms, ends_ms)
    if after_restart is not None:
        await _refuse_another_rehearsals_attempt(db, rehearsal, after_restart)
    if replaces is not None:
        await _current_of_the_chain(db, rehearsal, replaces, after_restart)
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
    already = await _the_same_frase(db, rehearsal.id, sha256)
    if already is not None:
        return already
    _refuse_a_sent(rehearsal)
    chain_head = (
        None
        if replaces is None
        else await _current_of_the_chain(db, rehearsal, replaces, after_restart)
    )

    frase = IRSceneFrase(
        id=str(uuid.uuid4()),
        rehearsal_id=rehearsal.id,
        session_id=session.id,
        starts_ms=starts_ms,
        ends_ms=ends_ms,
        replaces_id=chain_head,
        transcript=text,
        attempt=after_restart,
        restart_id=_closing((await restarts_of(db, [rehearsal.id]))[rehearsal.id], after_restart),
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
    db: AsyncSession, rehearsal: IRSceneRehearsal, *, attempt: str, closes: str | None
) -> IRSceneRestart:
    """«recomeçar a tradução» into the attempt the tablet minted: a numbered restart with the
    record as it was, the current attempt's frases stamped with it.

    The attempt is the restart's id, so the same restart sent again is the first one. Its
    frases sent before it landed were held, and now count. It names the attempt it closes and
    is refused while that is not the current one, so restarts that arrive out of order wait for
    their predecessor instead of becoming current in arrival order. Taken under the rehearsal's
    lock, as a frase lands, and stamped with the rehearsal's archive when a Zerar got there
    first.
    """
    rehearsal = await _locked(db, rehearsal.id)
    already = await db.get(IRSceneRestart, attempt)
    if already is not None:
        if already.rehearsal_id != rehearsal.id:
            raise UnknownReferenceError(f"Restart {attempt} belongs to another scene rehearsal")
        return already
    _refuse_a_sent(rehearsal)
    done = (await restarts_of(db, [rehearsal.id]))[rehearsal.id]
    if closes != current_attempt(done):
        raise RestartOutOfOrder(
            f"Restart {attempt} closes {closes}, which is not the current attempt"
        )
    frases = (await frases_of(db, {rehearsal.id: done}))[rehearsal.id]
    restart = IRSceneRestart(
        id=attempt,
        rehearsal_id=rehearsal.id,
        session_id=rehearsal.session_id,
        n=len(done) + 1,
        archive_id=rehearsal.archive_id,
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


async def send_the_scene_rehearsal(
    db: AsyncSession,
    session: IRSession,
    rehearsal: IRSceneRehearsal,
    *,
    turn_id: str,
    closes: str | None,
    project_id: str,
    bound_s: float,
    draft: Draft,
) -> TurnResponse:
    """«terminei»: the rehearsal claimed as sent under `turn_id`, then answered as a team turn.

    The claim is committed before the voice is asked, and released when the turn never lands
    (ADR 0063).
    """
    speech, claimed_at = await _claim_the_send(
        db, session, rehearsal, turn_id=turn_id, closes=closes, bound_s=bound_s
    )
    try:
        return await answer_around_the_opening(
            db,
            session,
            opening=False,
            turn_id=turn_id,
            project_id=project_id,
            hearing=None,
            heard=speech,
            deadline=asyncio.get_running_loop().time() + bound_s,
            bound_s=bound_s,
            draft=draft,
        )
    except BaseException:
        await db.rollback()
        await _release_the_send(rehearsal.id, turn_id, claimed_at)
        raise


def _landed(session_id: Any, turn_id: Any) -> Exists:
    return (
        select(IRTurn.turn_id)
        .where(IRTurn.session_id == session_id, IRTurn.turn_id == turn_id)
        .exists()
    )


async def _refuse_a_standing_claim(
    db: AsyncSession, rehearsal: IRSceneRehearsal, bound_s: float
) -> None:
    """Another turn's claim stands: sent once its turn landed, being sent while it is live.

    A claim older than an opening claim may live, with no turn landed, is no claim (ADR 0053).
    """
    if await db.scalar(select(_landed(rehearsal.session_id, rehearsal.sent_turn_id))):
        raise SceneRehearsalSent(f"Scene rehearsal {rehearsal.id} was sent and is frozen")
    if rehearsal.sent_at is not None and rehearsal.sent_at >= oldest_live_claim(bound_s):
        raise SceneRehearsalSending(f"Scene rehearsal {rehearsal.id} is being sent")


async def _claim_the_send(
    db: AsyncSession,
    session: IRSession,
    rehearsal: IRSceneRehearsal,
    *,
    turn_id: str,
    closes: str | None,
    bound_s: float,
) -> tuple[HeardSpeech, datetime]:
    """The rehearsal stamped sent under `turn_id`, the turn it makes, and when it was claimed.

    Claimed under the rehearsal's lock, which a frase and a restart take too. The send names the
    attempt it closes, and is refused while that is not the current one or a frase waits on a
    restart still on its way. One with no live frase is refused and stays unsent. The same turn
    id renews its own claim and makes the turn again. The turn's words are the live frases' in
    recording order, in the session's language, and the recording's length stands as the time
    the team held the microphone.
    """
    rehearsal = await _locked(db, rehearsal.id)
    standing = rehearsal.sent_at
    if standing is not None and rehearsal.sent_turn_id != turn_id:
        await _refuse_a_standing_claim(db, rehearsal, bound_s)
    restarts = await restarts_of(db, [rehearsal.id])
    held = (await held_frases(db, restarts))[rehearsal.id]
    if closes != current_attempt(restarts[rehearsal.id]) or held:
        raise RestartOutOfOrder(
            f"The send of scene rehearsal {rehearsal.id} closes {closes}, which is not its "
            "current attempt, or a frase waits on a restart still on its way"
        )
    frases = (await frases_of(db, restarts))[rehearsal.id]
    replacing = replaced_by(frases)
    live_frases = [frase for frase in frases if frase.id not in replacing]
    if not live_frases:
        raise SceneRehearsalUntranslated(f"Scene rehearsal {rehearsal.id} has no translated frase")
    claimed_at = datetime.now(UTC)
    claimed = await db.execute(
        update(IRSceneRehearsal)
        .where(
            IRSceneRehearsal.id == rehearsal.id,
            IRSceneRehearsal.sent_at.is_(None)
            if standing is None
            else IRSceneRehearsal.sent_at == standing,
        )
        .values(sent_at=claimed_at, sent_turn_id=turn_id)
        .execution_options(synchronize_session=False)
    )
    if claimed.rowcount != 1:
        raise SceneRehearsalSending(f"Scene rehearsal {rehearsal.id} is being sent")
    language = room_language(session.language)
    speech = HeardSpeech(
        text=" ".join(frase.transcript.strip() for frase in live_frases),
        bridge_language=language,
        language_code=language,
        take_ms=rehearsal.duration_ms,
        scene_rehearsal=SentSceneRehearsal(
            rehearsal_id=rehearsal.id,
            n=rehearsal.n,
            frases=len(live_frases),
            scene=rehearsal.scene,
        ),
    )
    await db.commit()
    return speech, claimed_at


async def _release_the_send(rehearsal_id: str, turn_id: str, claimed_at: datetime) -> None:
    """Unsend a rehearsal whose turn under `turn_id` never landed, so it can be sent again.

    On a session of its own, as an opening claim is released (ADR 0053), and only the claim this
    request made: a resend that renewed it holds it now. A turn stored under that id landed,
    whichever request failed after it, and keeps the rehearsal sent.
    """
    async with AsyncSessionLocal() as own:
        await own.execute(
            update(IRSceneRehearsal)
            .where(
                IRSceneRehearsal.id == rehearsal_id,
                IRSceneRehearsal.sent_turn_id == turn_id,
                IRSceneRehearsal.sent_at == claimed_at,
                ~_landed(IRSceneRehearsal.session_id, turn_id),
            )
            .values(sent_at=None, sent_turn_id=None)
            .execution_options(synchronize_session=False)
        )
        await own.commit()
