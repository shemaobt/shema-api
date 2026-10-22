"""The **Manifest** Refine receives for an approved passage: her document, in her order."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DraftNotApproved
from app.db.models.internalization_room import IRSceneRehearsal, IRSession, IRTake
from app.services.internalization_room.back_translation import LaidInSentence
from app.services.internalization_room.canon.book_material import meaning_map_ref
from app.services.internalization_room.canon.kept import reading_the_canon_of
from app.services.internalization_room.canon.parse_map import load_map
from app.services.internalization_room.release import (
    RETRO_ROUTE,
    _mother_tongue,
    _recording_grain,
    approved_draft,
)
from app.services.internalization_room.sessions import back_translation_of
from app.services.internalization_room.take_downloads import download_link
from app.services.internalization_room.takes import (
    current_parts,
    extension,
    is_declared,
    is_wav,
    part_keys,
    takes_of,
)
from app.utils.stored_time import as_utc

#: Her audio format, in her keys: what the tablet records when it records WAV.
AUDIO_FORMAT: dict[str, Any] = {
    "container": "wav",
    "codec": "pcm_s16le",
    "sampleRate": 16000,
    "channels": 1,
}

#: Her key, our truth: every take's digest is the server's, taken from the bytes it stored.
INTEGRITY = {
    "sha256": "server-computed from the stored bytes; verify by re-hashing the downloaded file"
}

#: Her warning for a release approved before the approval record existed (ADR 0020).
NO_CHECK_RECORDED = (
    "this release was approved before the approval record existed: no check state "
    "(conferida / forçada / findings) is recorded for it"
)

_HER_CHECK = (
    "version",
    "status",
    "conferida",
    "forced",
    "heardComplete",
    "lastCheckAt",
    "findings",
)


async def refine_manifest(db: AsyncSession, session: IRSession) -> dict[str, Any]:
    """The manifest of this session's approved draft, or ``DraftNotApproved``.

    Built from the release the draft stands approved under, the session's current parts and
    the canon read at the session's pin. It carries no frase's words, no note, no superseded
    take, nobody who forced it, no order clock and no clock offset: those are the consultant's,
    in the **Retroverification file**, and the stored **Packet** stays the record.
    """
    release = await approved_draft(db, session)
    if release is None:
        raise DraftNotApproved(f"Internalization room session {session.id} has no approved draft")
    packet = release.packet
    release_id = str(packet.get("release_id") or release.id)
    parts = current_parts(await takes_of(db, session.id))
    keys = part_keys(parts)
    clips = [part for part in parts if not is_declared(part)]
    names = [f"{release_id}-{keys[part.id]}.{extension(part.content_type)}" for part in clips]
    links = await asyncio.gather(
        *(download_link(part, name) for part, name in zip(clips, names, strict=True))
    )
    origins = await _origins(db, clips)
    laid = {sentence.take_id: sentence for sentence in back_translation_of(session).sentences}
    with reading_the_canon_of(session.canon_pin):
        reference = load_map(session.pericope).reference
        meaning_map = meaning_map_ref(session.pericope)

    warnings = []
    if meaning_map is None:
        warnings.append(f"no vendored meaning-map for {session.pericope} in VENDOR_MANIFEST.json")
    stored_check = packet.get("check")
    check = _her_check(stored_check, session.id) if stored_check else None
    if check is None:
        warnings.append(NO_CHECK_RECORDED)

    manifest: dict[str, Any] = {
        "releaseId": release_id,
        "pericopeId": session.pericope,
        "reference": reference,
        "language": packet["language"]
        if "language" in packet
        else await _mother_tongue(db, session),
    }
    if session.language:
        manifest["sessionLanguage"] = session.language
    manifest |= {
        "meaningMap": meaning_map,
        "grain": "scene" if _recording_grain(parts) == "parts" else "whole",
        "clips": [
            _clip(part, keys[part.id], name, link, origins.get(part.id), _splices(part, laid))
            for part, name, link in zip(clips, names, links, strict=True)
        ],
        "finalizedAt": as_utc(release.approved_at).isoformat(),
        "finalizeCount": release.version,
        "sessionIds": await _session_ids(db, session),
        "audioFormat": AUDIO_FORMAT
        if clips and all(is_wav(part.content_type) for part in clips)
        else None,
        "integrity": INTEGRITY,
        "externalCheck": None,
        "check": check,
    }
    if warnings:
        manifest["warnings"] = warnings
    manifest["exportedAt"] = datetime.now(UTC).isoformat()
    return manifest


def _clip(
    part: IRTake,
    key: str,
    filename: str,
    url: str,
    origin: dict[str, Any] | None,
    splices: int,
) -> dict[str, Any]:
    clip: dict[str, Any] = {
        "key": key,
        "takeId": part.id,
        "sha256": part.sha256,
        "durationMs": part.duration_ms,
        "bytes": part.size_bytes,
        "contentType": part.content_type,
        "recordedAt": as_utc(part.recorded_at).isoformat(),
        "filename": filename,
        "url": url,
    }
    if origin is not None:
        clip["origin"] = origin
    if splices:
        clip["splices"] = splices
    return clip


async def _origins(db: AsyncSession, clips: list[IRTake]) -> dict[str, dict[str, Any]]:
    """Her five keys for each joined part whose scene rehearsal is found, by the part's id."""
    joined = {part.origin: part for part in clips if part.origin}
    if not joined:
        return {}
    found = await db.execute(select(IRSceneRehearsal).where(IRSceneRehearsal.id.in_(joined)))
    return {
        joined[rehearsal.id].id: {
            "kind": "scene-rehearsal",
            "sessionId": rehearsal.session_id,
            "n": rehearsal.n,
            "takeRecordedAt": as_utc(rehearsal.recorded_at).isoformat(),
            "joinedAt": as_utc(joined[rehearsal.id].created_at).isoformat(),
        }
        for rehearsal in found.scalars()
    }


def _splices(part: IRTake, laid: dict[str, LaidInSentence]) -> int:
    """How many sentences were laid into this part's chain, carried from take to take."""
    count = 0
    take_id = part.id
    while take_id in laid:
        count += 1
        take_id = laid[take_id].previous_take_id
    return count


def _her_check(stored: dict[str, Any], session_id: str) -> dict[str, Any]:
    """The stored check in her keys and order, with nobody's name on it."""
    check = {key: stored.get(key) for key in _HER_CHECK}
    if stored.get("nuances"):
        check["nuances"] = stored["nuances"]
    check["retroUrl"] = RETRO_ROUTE.format(session_id=session_id)
    return check


async def _session_ids(db: AsyncSession, session: IRSession) -> list[str]:
    """Every session of this team on this passage, of this session's archive, sorted."""
    found = await db.execute(
        select(IRSession.id, IRSession.archive_id).where(
            IRSession.project_id == session.project_id,
            IRSession.pericope == session.pericope,
        )
    )
    return sorted(id_ for id_, archive_id in found.tuples() if archive_id == session.archive_id)
