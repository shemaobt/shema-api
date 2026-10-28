"""The retroverificação file as her `retroExport.ts` writes it, read off one draft's rows."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRRelease, IRSession
from app.models.retro_export import (
    RetroApproval,
    RetroApprovalFinding,
    RetroApprovalFrase,
    RetroApprovalTake,
    RetroExport,
    RetroFrase,
    RetroHistoryEntry,
)
from app.services.internalization_room.approved_draft import latest_release
from app.services.internalization_room.back_translation import frase_numbers
from app.services.internalization_room.forced import was_forced
from app.services.internalization_room.passage_retroverification import (
    APPROVED_BEFORE_THE_RECORD,
    NOT_APPROVED,
)
from app.services.internalization_room.retroverification import _walked_forward
from app.services.internalization_room.segments import (
    current_segments,
    final_segments,
    retired_segments,
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


async def _frases_and_history(
    db: AsyncSession, session: IRSession, approval: RetroApproval | None, keys: dict[str, str]
) -> tuple[list[RetroFrase], list[RetroHistoryEntry]]:
    """The telling she lists and every frase ever told, abandoned ones included.

    With an approval the numbers and places are its own and the words are the translation's as it
    stands; a frase whose words a restart abandoned keeps its number and has none.
    """
    standing = await current_segments(db, session.id)
    leaves = await final_segments(db, session.id)
    retired = await retired_segments(db, session.id)
    standing_ids = {row.id for row in standing}
    replaced_by = {row.id: row.superseded_by_id for row in retired}
    replaces = {row.superseded_by_id: row.id for row in retired if row.superseded_by_id}
    live = {row.id for row in leaves}
    in_the_record = {row.id: row for row in standing} | {
        row.id: row
        for row in retired
        if _walked_forward(row.id, replaced_by, standing_ids) is not None
    }

    def _frase(
        n: int, idx: str, clip_key: str, starts: float | None, ends: float | None
    ) -> RetroFrase:
        row = in_the_record.get(idx)
        return RetroFrase(
            n=n,
            idx=idx,
            clipKey=clip_key,
            coversFrom=starts,
            coversTo=ends,
            transcript=(row.transcript or "") if row else "",
            pass_number=row.pass_number if row else 1,
            recordedAt=row.created_at.isoformat() if row else "",
            supersedes=replaces.get(idx),
            stale=idx not in live or (row is not None and row.stale),
        )

    if approval:
        frases = [
            _frase(one.n, one.idx, one.clipKey, one.coversFrom, one.coversTo)
            for one in approval.frases
        ]
    else:
        numbers = frase_numbers(told_back(leaves))
        frases = [
            _frase(
                numbers[row.id], row.id, keys[row.take_id], row.starts_ms / 1000, row.ends_ms / 1000
            )
            for row in leaves
            if row.id in numbers
        ]
    ever_told = sorted(
        (*standing, *retired), key=lambda row: (row.created_at, row.superseded_at is None, row.id)
    )
    history = [
        RetroHistoryEntry(
            idx=row.id,
            clipKey=keys.get(row.take_id, ""),
            coversFrom=row.starts_ms / 1000,
            coversTo=row.ends_ms / 1000,
            transcript=row.transcript or "",
            pass_number=row.pass_number,
            recordedAt=row.created_at.isoformat(),
            supersedes=replaces.get(row.id),
            superseded=row.superseded_by_id is not None,
        )
        for row in ever_told
    ]
    return frases, history


async def retro_export(
    db: AsyncSession, session: IRSession, release: IRRelease | None, release_id: str
) -> RetroExport:
    """Her file down to the history of every frase.

    ``release`` is the version the draft stands approved under, or none while it is a draft.
    """
    keys = keys_of_the_takes(await takes_of(db, session.id))
    approval = _approval(release, keys) if release else None
    frases, history = await _frases_and_history(db, session, approval, keys)
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
        history=history,
    )
