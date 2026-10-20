from __future__ import annotations

import asyncio

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRSession, IRTake, IRTakeKind
from app.models.internalization_room import (
    SupersededTakeDownload,
    TakeDownload,
    TakeDownloadsResponse,
)
from app.services.internalization_room.release import (
    _mother_tongue,
    release_name,
    releases_of_passage,
)
from app.services.internalization_room.takes import (
    DOWNLOAD_LINK_SECONDS,
    current_parts,
    download_url,
    extension,
    part_keys,
    takes_of,
)
from app.utils.stored_time import as_utc


async def _release_id(db: AsyncSession, session: IRSession) -> str:
    releases = (
        []
        if session.project_id is None
        else await releases_of_passage(db, session.project_id, session.pericope)
    )
    if releases:
        latest = releases[-1]
        return str(latest.packet.get("release_id") or latest.id)
    return release_name(await _mother_tongue(db, session), session.pericope, 1)


def _with_bytes(take: IRTake) -> bool:
    return take.kind is IRTakeKind.ENSAIO and take.sha256 != ""


async def take_downloads_of(db: AsyncSession, session: IRSession) -> TakeDownloadsResponse:
    """The session's rehearsal takes named the way Refine receives them, with hour-long links."""
    takes = await takes_of(db, session.id)
    parts = current_parts(takes)
    keys = part_keys(parts)
    release_id = await _release_id(db, session)
    live_ids = {part.id for part in parts}
    rehearsals = [take for take in takes if _with_bytes(take)]
    replaced_at = {
        take.id: as_utc(successor.created_at).isoformat()
        for take, successor in _each_with_its_successor(takes)
    }

    def filename(take: IRTake) -> str:
        stem = f"{release_id}-{keys[take.ordinal]}"
        if take.id not in live_ids:
            stem += f"-substituida-{take.id}"
        return f"{stem}.{extension(take.content_type)}"

    names = [filename(take) for take in rehearsals]
    links = await asyncio.gather(
        *(download_url(take, name) for take, name in zip(rehearsals, names, strict=True))
    )
    live: list[TakeDownload] = []
    superseded: list[SupersededTakeDownload] = []
    for take, name, link in zip(rehearsals, names, links, strict=True):
        entry = TakeDownload(
            take_id=take.id,
            key=keys[take.ordinal],
            filename=name,
            url=link,
            sha256=take.sha256,
            size_bytes=take.size_bytes,
            duration_ms=take.duration_ms,
            content_type=take.content_type,
        )
        if take.id in live_ids:
            live.append(entry)
        else:
            superseded.append(
                SupersededTakeDownload(**entry.model_dump(), superseded_at=replaced_at[take.id])
            )
    return TakeDownloadsResponse(
        session_id=session.id,
        release_id=release_id,
        links_valid_for_s=DOWNLOAD_LINK_SECONDS,
        takes=live,
        superseded_takes=superseded,
    )


def _each_with_its_successor(takes: list[IRTake]) -> list[tuple[IRTake, IRTake]]:
    """Every rehearsal take paired with the next one under its number, in `takes_of`'s order."""
    last: dict[int | None, IRTake] = {}
    pairs: list[tuple[IRTake, IRTake]] = []
    for take in takes:
        if take.kind is not IRTakeKind.ENSAIO:
            continue
        if take.ordinal in last:
            pairs.append((last[take.ordinal], take))
        last[take.ordinal] = take
    return pairs
