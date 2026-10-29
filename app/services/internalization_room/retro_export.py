"""The retroverificação file as her `retroExport.ts` writes it, read off one draft's rows."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import (
    IRRelease,
    IRSegment,
    IRSession,
    IRTake,
    IRTakeKind,
)
from app.models.internalization_room import PlayedTake
from app.models.retro_export import (
    RetroApproval,
    RetroApprovalFinding,
    RetroApprovalFrase,
    RetroApprovalTake,
    RetroCheck,
    RetroCheckFinding,
    RetroExport,
    RetroFrase,
    RetroHistoryEntry,
    RetroPrevious,
    RetroSupersededTake,
)
from app.services.internalization_room.approved_draft import latest_release
from app.services.internalization_room.back_translation import (
    JOINED_WITHIN_MS,
    frase_numbers,
    joined_spans,
    listening_to_the_parts,
)
from app.services.internalization_room.forced import was_forced
from app.services.internalization_room.segments import (
    current_segments,
    final_segments,
    retired_segments,
    stale_segments,
    told_back,
)
from app.services.internalization_room.sessions import back_translation_of
from app.services.internalization_room.take_downloads import (
    _with_bytes,
    file_name,
    keys_of_the_takes,
)
from app.services.internalization_room.takes import (
    current_parts,
    takes_of,
)
from app.utils.stored_time import as_utc

NOT_APPROVED = (
    "rascunho ainda não aprovado — as frases abaixo são a tradução ao vivo, não uma versão fechada"
)
APPROVED_BEFORE_THE_RECORD = (
    "esta versão foi aprovada antes do registro de aprovação existir — "
    "sem estado de conferência gravado; as frases abaixo são a tradução ao vivo"
)

#: Where a facilitator's browser fetches one take, as the file points at it. A path and never
#: a signed link: a signed URL expires in minutes and this document is meant to outlive it.
TAKE_AUDIO_ROUTE = "/api/internalization-room/facilitator/takes/{take_id}/audio"


async def _version(db: AsyncSession, session: IRSession, release: IRRelease | None) -> int:
    """The draft's release number when one stands, else the passage's latest plus one, else 1.

    The column and never the name (a release before ADR 0048 is named by its row id). The counter
    is the passage's, in the live draft and in an archive alike, as the download list reads it.
    """
    if release is not None:
        return release.version
    latest = (
        await latest_release(db, session.project_id, session.pericope)
        if session.project_id
        else None
    )
    return latest.version + 1 if latest else 1


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


def _previous(takes: list[IRTake]) -> list[RetroPrevious]:
    """The earlier lives a grain switch set aside, oldest first, each named by its moment.

    A switch stamps every take the session held with its time, so the stamps are the switches
    that archived something: a first choice, or a flip over nothing, stamps none and names none
    (her `previousAfterSwitch`). The grain a stamp abandoned is that of the last take recorded
    under it, which is the one in force: a whole has no number.
    """
    stamped: dict[datetime, list[IRTake]] = {}
    for take in takes:
        if take.set_aside_at:
            stamped.setdefault(take.set_aside_at, []).append(take)
    return [
        RetroPrevious(
            at=as_utc(moment).isoformat(),
            grain="whole"
            if max(group, key=lambda one: one.created_at).ordinal is None
            else "scene",
        )
        for moment, group in sorted(stamped.items())
    ]


def _heard(entry: PlayedTake | None) -> float:
    """The share of a part the team heard, her rule's joined spans over the part's length."""
    if entry is None or not entry.clip_duration_ms:
        return 0
    length = entry.clip_duration_ms
    covered = sum(
        max(0, min(end, length) - start)
        for start, end in joined_spans(entry.played_ranges, within_ms=JOINED_WITHIN_MS)
    )
    return min(1, covered / length)


async def retro_export(
    db: AsyncSession, session: IRSession, release: IRRelease | None, release_id: str
) -> RetroExport:
    """Her file down to the history of every frase.

    ``release`` is the version the draft stands approved under, or none while it is a draft.
    An approved frase finds its live stretch by its idx: itself while current, else its
    replacement, else after a restart the top stretch of its part starting where it did.
    """
    takes = await takes_of(db, session.id)
    keys = keys_of_the_takes(takes)
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
    telling_back = back_translation_of(session)
    rows = {row.id: row for row in (*standing.values(), *retired)}
    numbered = {one.idx: one.n for one in approval.frases} if approval else numbers

    def _address(segment_id: str | None) -> dict[str, Any]:
        row = rows.get(segment_id or "")
        return {
            "idx": segment_id,
            "frase": numbered.get(segment_id or ""),
            "clipKey": keys.get(row.take_id) if row else None,
        }

    parts = current_parts(takes)
    listened = {
        entry.take_id: entry
        for entry in listening_to_the_parts(telling_back.played_by_take, parts, leaves)
    }
    heard_by_clip = {part.id: _heard(listened.get(part.id)) for part in parts}
    ever_told = sorted(
        (row for row in (*standing.values(), *retired) if row.transcript),
        key=lambda row: (row.created_at, row.superseded_at is None, row.ordinal, row.id),
    )
    return RetroExport(
        releaseId=release_id,
        pericopeId=session.pericope,
        version=await _version(db, session, release),
        finalized=release is not None,
        note=None
        if approval
        else (NOT_APPROVED if release is None else APPROVED_BEFORE_THE_RECORD),
        approval=approval,
        frases=frases,
        history=[
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
        ],
        checks=[
            RetroCheck(
                at=check.at.isoformat(),
                findings=[
                    RetroCheckFinding(
                        kind=one.kind.value, note=one.note, **_address(one.segment_id)
                    )
                    for one in check.findings
                ]
                + [
                    RetroCheckFinding(
                        kind="nuance",
                        note=one.note,
                        quote=one.quote,
                        story=one.story,
                        voiced=one.voiced,
                        **_address(one.segment_id),
                    )
                    for one in check.nuances
                ],
                spoken=check.spoken,
                outcome=check.outcome,
                conferida=check.conferida,
            )
            for check in telling_back.checks
        ],
        heardByClip={keys[take_id]: share for take_id, share in heard_by_clip.items()},
        supersededTakes=[
            RetroSupersededTake(
                key=keys[take.id],
                takeId=take.id,
                sha256=take.sha256,
                durationMs=take.duration_ms,
                bytes=take.size_bytes,
                contentType=take.content_type,
                recordedAt=as_utc(take.recorded_at).isoformat(),
                filename=file_name(release_id, keys[take.id], take, superseded=True),
                url=TAKE_AUDIO_ROUTE.format(take_id=take.id),
            )
            for take in takes
            if take.kind is IRTakeKind.ENSAIO
            and _with_bytes(take)
            and take.set_aside_at is None
            and take.id not in {part.id for part in parts}
        ],
        previous=_previous(takes) or None,
        exportedAt=datetime.now(UTC).isoformat(),
    )
