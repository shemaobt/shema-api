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
)
from app.services.internalization_room.approved_draft import latest_release
from app.services.internalization_room.forced import was_forced
from app.services.internalization_room.passage_retroverification import (
    APPROVED_BEFORE_THE_RECORD,
    NOT_APPROVED,
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
    """The head of her file: the release, its version and the approval it stands under.

    ``release`` is the version the draft stands approved under, or none while it is a draft.
    """
    keys = keys_of_the_takes(await takes_of(db, session.id))
    approval = _approval(release, keys) if release else None
    latest = (
        None
        if release or session.project_id is None
        else await latest_release(db, session.project_id, session.pericope)
    )
    return RetroExport(
        releaseId=release_id,
        pericopeId=session.pericope,
        version=release.version if release else (latest.version if latest else 1),
        finalized=release is not None,
        note=None
        if approval
        else (NOT_APPROVED if release is None else APPROVED_BEFORE_THE_RECORD),
        approval=approval,
    )
