"""A joined part carries its scene rehearsal's frases, and the Bring-back lays them again.

A part the tablet laid in from a **Scene rehearsal** of this session, byte for byte, is that
rehearsal: the team already translated it frase by frase, and asking them to tell it back again
scene by scene is the work twice. So the part lands with the rehearsal's current frases as its
told stretches — the frase's place, its words, and its telling, which is the frase's own audio.

**Laid once, and only on ground nobody wrote on.** A resend, another tablet or «juntar» twice
answers the take already kept, and a part on which any stretch was ever written — told here,
laid before, or abandoned by «recomeçar a tradução» — is left as it stands: laying again would
undo a restart without anybody asking. The way back is the **Bring-back**, which abandons what
stands on the part and lays the frases again.

**The telling is a pointer, not a copy.** Each frase's audio is already stored; its telling is a
`retro` take row naming the same object, so a lay is database writes only and lands in the same
transaction as the stretches it tells.

**A frase shorter than a stretch can be is not laid.** The frase door takes any span; a stretch
is at least `SHORTEST_FRASE_MS`. Its ground stays untold and the frase stays in the rehearsal.

**The lock is the part's row** (`ir_takes`), never the session's: the checks are read again
under it, and the telling-back state is written through `save_back_translation`'s
compare-and-set like every capture.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, NothingToBringBack
from app.db.models.internalization_room import (
    IRSceneFrase,
    IRSceneRehearsal,
    IRSegment,
    IRSession,
    IRTake,
    IRTakeKind,
)
from app.services.internalization_room.back_translation import (
    BackTranslationState,
    findings_after_a_part_is_recorded_again,
)
from app.services.internalization_room.hard_stretches import (
    a_capture_after_a_check_unchecks,
    pass_of_a_telling,
)
from app.services.internalization_room.scene_rehearsals import frases_of, replaced_by, restarts_of
from app.services.internalization_room.segments import (
    SHORTEST_FRASE_MS,
    abandon_the_segments_of,
    capture_segment,
    final_segments,
    stop_waiting_on_the_segments_of,
)
from app.services.internalization_room.sessions import back_translation_of, save_back_translation
from app.services.internalization_room.takes import current_parts, takes_of


def _layable(frases: Sequence[IRSceneFrase]) -> list[IRSceneFrase]:
    replaced = replaced_by(frases)
    return [
        frase
        for frase in frases
        if frase.id not in replaced and frase.ends_ms - frase.starts_ms >= SHORTEST_FRASE_MS
    ]


def _its_own(rehearsal: IRSceneRehearsal | None, part: IRTake) -> bool:
    return rehearsal is not None and rehearsal.sha256 == part.sha256


async def _current_frases(db: AsyncSession, rehearsal: IRSceneRehearsal) -> list[IRSceneFrase]:
    """The rehearsal's frases that can stand as stretches now, in place order."""
    return _layable((await frases_of(db, await restarts_of(db, [rehearsal.id])))[rehearsal.id])


async def _own_rehearsal(
    db: AsyncSession, session: IRSession, part: IRTake
) -> IRSceneRehearsal | None:
    """The part's rehearsal when it is of this session and the part is its own bytes."""
    rehearsal = await db.scalar(
        select(IRSceneRehearsal).where(
            IRSceneRehearsal.id == part.origin, IRSceneRehearsal.session_id == session.id
        )
    )
    return rehearsal if _its_own(rehearsal, part) else None


def _laid_here(
    stretches: Sequence[IRSegment], part: IRTake, frases: Sequence[IRSceneFrase]
) -> bool:
    laid = {(frase.starts_ms, frase.ends_ms, frase.transcript) for frase in frases}
    return any(
        (stretch.starts_ms, stretch.ends_ms, stretch.transcript) in laid
        for stretch in stretches
        if stretch.take_id == part.id
    )


async def _ever_told(db: AsyncSession, part: IRTake) -> bool:
    written = await db.scalar(select(IRSegment.id).where(IRSegment.take_id == part.id).limit(1))
    return written is not None


async def _lock(db: AsyncSession, session: IRSession, part: IRTake) -> IRTake | None:
    """Hold the part's row, and answer it only if it is still the session's part."""
    await db.execute(
        select(IRTake)
        .where(IRTake.id == part.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return next(
        (one for one in current_parts(await takes_of(db, session.id)) if one.id == part.id), None
    )


async def _telling(
    db: AsyncSession,
    session: IRSession,
    rehearsal: IRSceneRehearsal,
    frase: IRSceneFrase,
    state: BackTranslationState,
) -> IRTake:
    """The `retro` take that plays the frase's own stored audio, written once per session."""
    kept = await db.scalar(
        select(IRTake).where(
            IRTake.session_id == session.id,
            IRTake.kind == IRTakeKind.RETRO,
            IRTake.sha256 == frase.sha256,
        )
    )
    if kept is not None:
        return kept
    telling = IRTake(
        id=str(uuid.uuid4()),
        project_id=session.project_id,
        session_id=session.id,
        device_id=rehearsal.device_id,
        pericope=session.pericope,
        kind=IRTakeKind.RETRO,
        scope=state.scope or session.pericope,
        pass_number=pass_of_a_telling(state),
        storage_key=frase.storage_key,
        size_bytes=frase.size_bytes,
        sha256=frase.sha256,
        crc32c=frase.crc32c,
        content_type=frase.content_type,
        verified_at=frase.verified_at,
        created_at=datetime.now(UTC),
        recorded_at=frase.created_at,
    )
    db.add(telling)
    return telling


async def _lay(
    db: AsyncSession,
    session: IRSession,
    part: IRTake,
    rehearsal: IRSceneRehearsal,
    frases: Sequence[IRSceneFrase],
    abandoned: set[str],
) -> None:
    async def laid(standing: BackTranslationState) -> None:
        standing.findings = findings_after_a_part_is_recorded_again(standing.findings, abandoned)
        standing.nuances = [one for one in standing.nuances if one.segment_id not in abandoned]
        await a_capture_after_a_check_unchecks(standing)

    state = back_translation_of(session)
    for frase in frases:
        telling = await _telling(db, session, rehearsal, frase, state)
        await db.flush()
        await capture_segment(
            db,
            session,
            take_id=part.id,
            starts_ms=frase.starts_ms,
            ends_ms=frase.ends_ms,
            bridge_take_id=telling.id,
            transcript=frase.transcript,
            pass_number=pass_of_a_telling(state),
            commit=False,
        )
    earlier = await db.scalars(
        select(IRTake.id).where(
            IRTake.session_id == session.id,
            IRTake.kind == IRTakeKind.ENSAIO,
            IRTake.ordinal == part.ordinal,
            IRTake.id != part.id,
        )
    )
    await stop_waiting_on_the_segments_of(db, take_ids=set(earlier))
    state.scope = state.scope or session.pericope
    await laid(state)
    await save_back_translation(db, session, state, commit=False, rule=laid)
    await db.commit()


async def lay_the_rehearsals_frases(db: AsyncSession, session: IRSession, part: IRTake) -> None:
    """Tell a part that just landed with its rehearsal's frases, when nothing was ever told on it.

    Nothing is written unless the part is current, joined from a rehearsal of this session with
    that rehearsal's own bytes, and no stretch row was ever written on it.
    """
    if part.origin is None:
        return
    rehearsal = await _own_rehearsal(db, session, part)
    if rehearsal is None:
        return
    locked = await _lock(db, session, part)
    if locked is None or await _ever_told(db, locked):
        return
    frases = await _current_frases(db, rehearsal)
    if frases:
        await _lay(db, session, locked, rehearsal, frases, set())


async def bring_back_the_rehearsals_frases(
    db: AsyncSession, session: IRSession, number: int
) -> None:
    """Abandon what stands on part `number` and lay its rehearsal's frases there again.

    Refused, with nothing written, for a part not joined, joined from another session, a part a
    sentence was re-recorded in, or a rehearsal with no frase. A part whose frases already stand
    is left as it is, so a second tap lands once.
    """
    part = next(
        (one for one in current_parts(await takes_of(db, session.id)) if one.ordinal == number),
        None,
    )
    locked = None if part is None else await _lock(db, session, part)
    if locked is None:
        raise NotFoundError(f"Session {session.id} has no part {number}")
    rehearsal = None if locked.origin is None else await _own_rehearsal(db, session, locked)
    frases = [] if rehearsal is None else await _current_frases(db, rehearsal)
    if rehearsal is None or not frases:
        raise NothingToBringBack(f"Part {number} has no scene rehearsal's frases to bring back")
    if _laid_here(await final_segments(db, session.id), locked, frases):
        return
    abandoned = await abandon_the_segments_of(db, session.id, take_ids={locked.id})
    await _lay(db, session, locked, rehearsal, frases, {one.id for one in abandoned})


async def parts_to_bring_back(
    db: AsyncSession, session: IRSession, parts: list[IRTake], stretches: list[IRSegment]
) -> list[int]:
    """The numbers of the current `parts` the Bring-back can lay again, in passage order."""
    joined = [
        (part, part.ordinal)
        for part in parts
        if part.origin is not None and part.ordinal is not None
    ]
    if not joined:
        return []
    rehearsals = {
        rehearsal.id: rehearsal
        for rehearsal in await db.scalars(
            select(IRSceneRehearsal).where(
                IRSceneRehearsal.id.in_({part.origin for part, _ in joined}),
                IRSceneRehearsal.session_id == session.id,
            )
        )
    }
    frases = await frases_of(db, await restarts_of(db, list(rehearsals)))
    offered: list[int] = []
    for part, number in joined:
        rehearsal = rehearsals.get(str(part.origin))
        if rehearsal is None or not _its_own(rehearsal, part):
            continue
        layable = _layable(frases[rehearsal.id])
        if layable and not _laid_here(stretches, part, layable):
            offered.append(number)
    return offered
