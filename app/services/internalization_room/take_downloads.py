from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRArchive, IRRelease, IRSession, IRTake, IRTakeKind
from app.models.internalization_room import (
    InsertDownload,
    SupersededTakeDownload,
    TakeDownload,
    TakeDownloadsResponse,
    WholeDownload,
)
from app.services.internalization_room.approved_draft import (
    approved_draft,
    latest_release,
    stands_on,
)
from app.services.internalization_room.back_translation import LaidInSentence
from app.services.internalization_room.release import (
    _mother_tongue,
    release_name,
    released_as,
    zeroed_name,
)
from app.services.internalization_room.sentences import WAV
from app.services.internalization_room.sessions import back_translation_of
from app.services.internalization_room.takes import (
    DOWNLOAD_LINK_SECONDS,
    current_parts,
    extension,
    is_declared,
    part_positions,
    set_aside_moment,
    signed_url,
    superseded_moment,
    takes_of,
)
from app.services.internalization_room.whole_passage import (
    whole_filename,
    whole_is_offered,
    whole_url,
)


async def _release_id(db: AsyncSession, session: IRSession, parts: list[IRTake]) -> str:
    """The id of the version this draft stands approved under, the name the next will have, or
    the archive's name for a session a Zerar archived.

    A file names a release only while the draft stands under it (ADR 0081): after a re-open the
    takes are the next version's draft, numbered on from the passage's last. A session a Zerar
    archived is no draft any more, and keeps the name of the release its takes were approved
    as, while they still stand on it; past that they carry the archive's name, never a version
    an approval can mint.
    """
    standing = await approved_draft(db, session)
    if standing is not None:
        return released_as(standing)
    if session.archive_id is not None:
        own = await db.scalar(
            select(IRRelease)
            .where(IRRelease.session_id == session.id)
            .order_by(IRRelease.version.desc())
            .limit(1)
        )
        if own is not None and stands_on(own, parts):
            return released_as(own)
        archive = await db.get(IRArchive, session.archive_id)
        if archive is None:
            raise RuntimeError(f"Archive {session.archive_id} of session {session.id} is gone")
        return zeroed_name(await _mother_tongue(db, session), session, archive.archived_at)
    latest = (
        None
        if session.project_id is None
        else await latest_release(db, session.project_id, session.pericope)
    )
    version = latest.version + 1 if latest is not None else 1
    return release_name(await _mother_tongue(db, session), session.pericope, version)


def part_keys_by_number(parts: list[IRTake]) -> dict[int | None, str]:
    """The **Part key** under each number the current parts carry, `whole` when told whole."""
    return {
        None: "whole",
        **{
            ordinal: "whole" if position is None else f"S{position}"
            for ordinal, position in part_positions(parts).items()
        },
    }


def keys_of_the_takes(takes: list[IRTake]) -> dict[str, str]:
    """The **Part key** of every rehearsal take, a replaced one under the number it carried."""
    rehearsals = [take for take in takes if take.kind is IRTakeKind.ENSAIO]
    by_number = part_keys_by_number(current_parts(takes))
    keys = {take.id: by_number[take.ordinal] for take in rehearsals if take.set_aside_at is None}
    return keys | _keys_as_they_stood(rehearsals)


def file_name(release_id: str, key: str, take: IRTake, *, superseded: bool = False) -> str:
    """The name a take downloads under, and the name the **Manifest** gives it (ADR 0073)."""
    stem = f"{release_id}-{key}"
    if superseded:
        stem += f"-substituida-{take.id}"
    return f"{stem}.{extension(take.content_type)}"


def insert_name(key: str, sentence_id: str) -> str:
    """The name a re-recorded sentence's raw recording downloads under (her insertDerivedName)."""
    return f"insert-{key}-{sentence_id}.wav"


def inserts_of(session: IRSession, keys: dict[str, str]) -> list[tuple[LaidInSentence, str]]:
    """Every sentence laid into this session, with the **Part key** of the part it went into."""
    return [
        (laid, keys[laid.take_id])
        for laid in back_translation_of(session).sentences
        if laid.take_id in keys
    ]


def insert_link(laid: LaidInSentence, key: str) -> Awaitable[str]:
    return signed_url(
        laid.storage_key,
        WAV,
        minutes=DOWNLOAD_LINK_SECONDS // 60,
        disposition=f'attachment; filename="{insert_name(key, laid.sentence_id)}"',
    )


def _with_bytes(take: IRTake) -> bool:
    return take.kind is IRTakeKind.ENSAIO and not is_declared(take)


def download_link(take: IRTake, filename: str) -> Awaitable[str]:
    return signed_url(
        take.storage_key,
        take.content_type,
        minutes=DOWNLOAD_LINK_SECONDS // 60,
        disposition=f'attachment; filename="{filename}"',
    )


async def take_downloads_of(db: AsyncSession, session: IRSession) -> TakeDownloadsResponse:
    """The session's rehearsal takes named the way Refine receives them, with hour-long links."""
    takes = await takes_of(db, session.id)
    parts = current_parts(takes)
    release_id = await _release_id(db, session, parts)
    live_ids = {part.id for part in parts}
    rehearsals = [take for take in takes if _with_bytes(take)]
    keys = keys_of_the_takes(takes)
    names = [
        file_name(release_id, keys[take.id], take, superseded=take.id not in live_ids)
        for take in rehearsals
    ]
    links = await asyncio.gather(
        *(download_link(take, name) for take, name in zip(rehearsals, names, strict=True))
    )
    live: list[TakeDownload] = []
    superseded: list[SupersededTakeDownload] = []
    for take, name, link in zip(rehearsals, names, links, strict=True):
        entry = TakeDownload(
            take_id=take.id,
            key=keys[take.id],
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
                SupersededTakeDownload(
                    **entry.model_dump(),
                    superseded_at=superseded_moment(take),
                    set_aside_at=set_aside_moment(take),
                )
            )
    inserts = inserts_of(session, keys)
    insert_links = await asyncio.gather(*(insert_link(laid, key) for laid, key in inserts))
    lengths = [part.duration_ms for part in parts]
    whole = (
        WholeDownload(
            filename=whole_filename(release_id),
            url=whole_url(session.id),
            duration_ms=None if None in lengths else sum(length or 0 for length in lengths),
        )
        if whole_is_offered(parts)
        else None
    )
    return TakeDownloadsResponse(
        session_id=session.id,
        release_id=release_id,
        links_valid_for_s=DOWNLOAD_LINK_SECONDS,
        takes=live,
        superseded_takes=superseded,
        whole=whole,
        inserts=[
            InsertDownload(
                sentence_id=laid.sentence_id,
                key=key,
                filename=insert_name(key, laid.sentence_id),
                url=link,
            )
            for (laid, key), link in zip(inserts, insert_links, strict=True)
        ],
    )


def _keys_as_they_stood(takes: list[IRTake]) -> dict[str, str]:
    """Each take a **Grain switch** set aside, keyed by its place among the takes it stamped.

    The current parts no longer hold its number, so its key is read off the takes the same
    switch set aside with it: the numbers among them in reading order, from one.
    """
    stamped: dict[datetime, list[IRTake]] = {}
    for take in takes:
        if take.kind is IRTakeKind.ENSAIO and take.set_aside_at is not None:
            stamped.setdefault(take.set_aside_at, []).append(take)
    keys: dict[str, str] = {}
    for group in stamped.values():
        numbers = sorted({take.ordinal for take in group if take.ordinal is not None})
        for take in group:
            keys[take.id] = (
                "whole" if take.ordinal is None else f"S{numbers.index(take.ordinal) + 1}"
            )
    return keys
