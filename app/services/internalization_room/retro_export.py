"""The retroverificação file as her `retroExport.ts` writes it, read off one draft's rows."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRRelease, IRSegment, IRSession
from app.models.retro_export import (
    RetroApproval,
    RetroApprovalFinding,
    RetroApprovalFrase,
    RetroApprovalTake,
    RetroExport,
    RetroFrase,
)
from app.services.internalization_room.approved_draft import latest_release
from app.services.internalization_room.back_translation import frase_numbers
from app.services.internalization_room.forced import was_forced
from app.services.internalization_room.passage_retroverification import (
    APPROVED_BEFORE_THE_RECORD,
    NOT_APPROVED,
)
from app.services.internalization_room.segments import (
    current_segments,
    final_segments,
    retired_segments,
    stale_segments,
    told_back,
)
from app.services.internalization_room.take_downloads import keys_of_the_takes
from app.services.internalization_room.takes import takes_of


def _finding(entry: dict[str, Any]) -> RetroApprovalFinding:
    return RetroApprovalFinding(
        kind=entry["kind"],
        frase=entry.get("frase"),
        idx=entry.get("idx"),
        clipKey=entry.get("scene"),
        voiced=entry.get("voiced"),
    )


def _approval(release: IRRelease, keys: dict[str, str]) -> RetroApproval | None:
    """The approval her store keeps of the version, from the packet the room froze at it."""
    check = release.packet.get("check")
    if check is None:
        return None
    packet_takes = (release.packet.get("audio") or {}).get("rehearsal_takes")
    stretches = (release.packet.get("back_translation") or {}).get("segments", [])
    return RetroApproval(
        v=release.version,
        at=release.approved_at.isoformat(),
        forced=was_forced(release.forced_by, release.forced_blockers),
        conferida=check["conferida"],
        heardComplete=check["heardComplete"],
        lastCheckAt=check["lastCheckAt"],
        findings=[_finding(one) for one in check["findings"]],
        nuances=[_finding(one) for one in check.get("nuances", [])] or None,
        frases=[
            RetroApprovalFrase(
                n=one["frase"],
                idx=one["segment_id"],
                clipKey=one.get("scene") or keys[one["take_id"]],
                coversFrom=one["starts_ms"] / 1000,
                coversTo=one["ends_ms"] / 1000,
            )
            for one in stretches
            if one.get("frase") is not None
        ],
        takes=None
        if packet_takes is None
        else [
            RetroApprovalTake(
                key=one.get("key") or keys[one["take_id"]],
                takeId=one["take_id"],
                sha256=one["sha256"],
                durationMs=one.get("duration_ms"),
                bytes=one["size_bytes"],
            )
            for one in packet_takes
        ],
    )


async def retro_export(
    db: AsyncSession, session: IRSession, release: IRRelease | None, release_id: str
) -> RetroExport:
    """Her file down to the frases of the telling.

    ``release`` is the version the draft stands approved under, or none while it is a draft.
    An approved frase finds its live stretch by its idx: itself while current, else its
    replacement, else after a restart the top stretch of its part starting where it did.
    """
    keys = keys_of_the_takes(await takes_of(db, session.id))
    standing = {row.id: row for row in await current_segments(db, session.id)}
    leaves = await final_segments(db, session.id)
    retired = await retired_segments(db, session.id)
    waiting = await stale_segments(db, session.id)
    approval = _approval(release, keys) if release else None
    replaces = {
        row.superseded_by_id: row.id for row in retired if row.superseded_by_id and row.transcript
    }
    by_id = {row.id: row for row in retired}

    def _frase(
        n: int,
        idx: str,
        row: IRSegment | None,
        place: tuple[str, float | None, float | None],
        *,
        stale: bool = False,
    ) -> RetroFrase:
        return RetroFrase(
            n=n,
            idx=idx,
            clipKey=place[0],
            coversFrom=place[1],
            coversTo=place[2],
            transcript=(row.transcript or "") if row else "",
            pass_number=row.pass_number if row else 1,
            recordedAt=row.created_at.isoformat() if row else "",
            supersedes=replaces.get(row.id) if row else None,
            stale=stale or row is None,
        )

    def _live(idx: str, place: tuple[str, float | None, float | None]) -> IRSegment | None:
        at, seen = idx, set()
        while at in by_id and by_id[at].superseded_by_id and at not in seen:
            seen.add(at)
            at = by_id[at].superseded_by_id or at
        if at in standing:
            return standing[at]
        return next(
            (
                row
                for row in standing.values()
                if row.parent_id is None
                and keys.get(row.take_id) == place[0]
                and row.starts_ms / 1000 == place[1]
            ),
            None,
        )

    numbers = frase_numbers(told_back(leaves))
    told = [row for row in leaves if row.id in numbers]
    if approval:
        frases = []
        for one in approval.frases:
            place = (one.clipKey, one.coversFrom, one.coversTo)
            frases.append(_frase(one.n, one.idx, _live(one.idx, place), place))
    else:
        counted = [(numbers[row.id], row, False) for row in told]
        waiting_on = [(len(told) + k, row, True) for k, row in enumerate(waiting, 1)]
        frases = [
            _frase(
                n,
                row.id,
                row,
                (keys.get(row.take_id, ""), row.starts_ms / 1000, row.ends_ms / 1000),
                stale=stale,
            )
            for n, row, stale in counted + waiting_on
        ]
    latest = (
        None
        if release or session.project_id is None
        else await latest_release(db, session.project_id, session.pericope)
    )
    return RetroExport(
        releaseId=release_id,
        pericopeId=session.pericope,
        version=release.version if release else (latest.version + 1 if latest else 1),
        finalized=release is not None,
        note=None
        if approval
        else (NOT_APPROVED if release is None else APPROVED_BEFORE_THE_RECORD),
        approval=approval,
        frases=frases,
    )
