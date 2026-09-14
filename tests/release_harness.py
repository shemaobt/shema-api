"""The rows a release case needs before it can ask the packet anything.

A session the room would let the team approve — comprehension supported, coverage met, a
rehearsal recorded, a stretch told back and read, the playback reported — assembled through
the room's own write paths so every case starts from state the field could produce.

Shared by the cases about the artifact and the cases about the frozen numbers, which is why
it is here and not in either of them.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRSession, IRTake, IRTakeKind
from app.models.internalization_room import PlayedTake
from app.services.internalization_room.back_translation import BackTranslationState
from app.services.internalization_room.canon.elements import element_keys
from app.services.internalization_room.comprehension.checkpoints import (
    checkpoints_for,
    scene_ids_for,
)
from app.services.internalization_room.comprehension.evidence import (
    EvidenceMethod,
    EvidenceObservation,
    EvidenceResult,
)
from app.services.internalization_room.comprehension.state import ComprehensionState
from app.services.internalization_room.coverage import initial_state, merge
from app.services.internalization_room.segments import capture_segment, final_segments
from app.services.internalization_room.sessions import (
    create_session,
    report_playback,
    save_comprehension,
)

P = "P03"


def supported_comprehension(pericope: str, *, carry_one: bool = False) -> ComprehensionState:
    checkpoints = list(checkpoints_for(pericope))
    ledger = []
    for index, checkpoint in enumerate(checkpoints):
        result = (
            EvidenceResult.CARRY_TO_REFINE
            if carry_one and index == 0
            else EvidenceResult.DEMONSTRATED
        )
        ledger.append(
            EvidenceObservation(
                id=f"ev-{index}",
                unit_id=checkpoint.id,
                probe_id=f"probe-{index}",
                method=EvidenceMethod.MICRO_TELLBACK,
                result=result,
            )
        )
    return ComprehensionState(
        ledger=list(ledger),
        practiced_scene_ids=scene_ids_for(pericope),
    )


async def one_stretch(db: AsyncSession, session: IRSession, text: str = "Noemi voltou com Rute"):
    return await capture_segment(
        db,
        session,
        take_id="ensaio-1",
        starts_ms=0,
        ends_ms=61000,
        bridge_take_id="retro-1",
        transcript=text,
    )


async def checked_telling_back(db: AsyncSession, session: IRSession) -> BackTranslationState:
    told = await one_stretch(db, session)
    return BackTranslationState(
        scope=P,
        findings=[],
        checked=True,
        analysed_segment_ids=[told.id],
    )


def ensaio_take(
    session_id: str,
    *,
    scope: str = "passagem-inteira",
    pass_number: int | None = None,
    ordinal: int | None = None,
    sha256: str = "a" * 64,
    created_at: datetime | None = None,
) -> IRTake:
    take = IRTake(
        session_id=session_id,
        device_id="tablet-1",
        pericope=P,
        kind=IRTakeKind.ENSAIO,
        scope=scope,
        pass_number=pass_number,
        ordinal=ordinal,
        storage_key=f"takes/{session_id}/ensaio/{sha256}",
        size_bytes=2048,
        sha256=sha256,
        crc32c="AAAAAAA=",
        content_type="audio/mp4",
    )
    if created_at is not None:
        take.created_at = created_at
    return take


def retro_take(
    session_id: str,
    *,
    scope: str = P,
    pass_number: int | None = None,
    ordinal: int | None = None,
    sha256: str = "a" * 64,
    created_at: datetime | None = None,
) -> IRTake:
    take = IRTake(
        session_id=session_id,
        device_id="tablet-1",
        pericope=P,
        kind=IRTakeKind.RETRO,
        scope=scope,
        pass_number=pass_number,
        ordinal=ordinal,
        storage_key=f"takes/{session_id}/retro/{sha256}",
        size_bytes=2048,
        sha256=sha256,
        crc32c="AAAAAAA=",
        content_type="audio/mp4",
    )
    if created_at is not None:
        take.created_at = created_at
    return take


async def reported_playback(
    db: AsyncSession,
    session: IRSession,
    state: BackTranslationState,
    *,
    played_ranges: list[list[int]] | None = None,
    clip_duration_ms: int | None = 61000,
) -> None:
    """Store the telling-back together with the team's report of what the tablet played.

    Through the room's own write path rather than by filling the fields, because the room
    binds a report to the rehearsal it is about at the moment it arrives. A report assembled
    here would name no recording, which is a state the release is entitled to refuse.

    One entry per part the session's stretches name, each carrying the numbers this call was
    given. These sessions rehearse in one part, so the numbers that used to describe the whole
    passage are the numbers that part is measured by, and every case here keeps the verdict it
    had. The flat pair travels beside it, as a tablet still in the field sends it.

    The defaults describe a part played through; a case about a report that falls short says
    so by naming the numbers it means.
    """
    spans = [[0, 61000]] if played_ranges is None else played_ranges
    told = await final_segments(db, session.id)
    await report_playback(
        db,
        session,
        state,
        played_by_take=[
            PlayedTake(take_id=take_id, played_ranges=spans, clip_duration_ms=clip_duration_ms or 0)
            for take_id in sorted({stretch.take_id for stretch in told})
        ],
        played_ranges=spans,
        clip_duration_ms=clip_duration_ms,
    )


async def ready_session(
    db: AsyncSession,
    *,
    project_id: str | None = None,
    tell: Callable[[AsyncSession, IRSession], Awaitable[BackTranslationState]] | None = None,
    **comprehension_kwargs,
):
    """A session carrying everything the packet refuses to travel without.

    ``project_id`` is the team whose conversation this is. It stays optional because most of
    these cases are about the packet and not about whose it is; the release is numbered per
    project, so the cases about the number name one.

    ``tell`` is what the team told back, answering the state one whole reading leaves behind;
    the default is a single stretch, read and clean. A case that needs the passage told in
    several stretches passes its own and inherits the rest of the scaffold rather than
    rebuilding it, which is the only part of this that ever differs.
    """
    session = await create_session(db, pericope=P, project_id=project_id)
    session.coverage_state = merge(initial_state(P), pericope_num=P, engaged=element_keys(P))
    await save_comprehension(db, session, supported_comprehension(P, **comprehension_kwargs))
    db.add(ensaio_take(session.id))
    await db.commit()
    await reported_playback(db, session, await (tell or checked_telling_back)(db, session))
    return session
