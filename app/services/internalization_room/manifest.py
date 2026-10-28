"""The **Manifest** Refine receives for an approved passage: her document, in her order."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DraftNotApproved
from app.db.models.internalization_room import IRRelease, IRSceneRehearsal, IRSession, IRTake
from app.services.internalization_room.approved_draft import approved_draft, stands_on
from app.services.internalization_room.back_translation import LaidInSentence
from app.services.internalization_room.canon.book_material import meaning_map_ref
from app.services.internalization_room.canon.kept import reading_the_canon_of
from app.services.internalization_room.canon.parse_map import load_map
from app.services.internalization_room.check_block import passage_retro_url
from app.services.internalization_room.coverage import is_panorama
from app.services.internalization_room.release import (
    InternalizationReleaseBlocked,
    _mother_tongue,
    _recording_grain,
    packet_as_read,
    released_as,
)
from app.services.internalization_room.sessions import back_translation_of
from app.services.internalization_room.take_downloads import (
    download_link,
    file_name,
    part_keys_by_number,
)
from app.services.internalization_room.takes import current_parts, is_declared, is_wav, takes_of
from app.services.internalization_room.whole_passage import (
    whole_filename,
    whole_is_offered,
    whole_url,
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


async def manifest_clips(
    db: AsyncSession, session: IRSession
) -> tuple[IRRelease, list[IRTake], list[IRTake]]:
    release = await approved_draft(db, session)
    takes = await takes_of(db, session.id)
    parts = current_parts(takes)
    if release is None or not stands_on(release, parts):
        raise DraftNotApproved(f"Internalization room session {session.id} has no approved draft")
    return release, takes, [part for part in parts if not is_declared(part)]


async def refine_manifest(db: AsyncSession, session: IRSession) -> dict[str, Any]:
    """The manifest of this session's approved draft, or ``DraftNotApproved``.

    Built from the release the draft stands approved under, the session's current parts and
    the canon read at the session's pin. It carries no frase's words, no note, no superseded
    take, nobody who forced it, no order clock and no clock offset: those are the consultant's,
    in the **Retroverification file**, and the stored **Packet** stays the record.
    """
    if is_panorama(session.pericope):
        raise InternalizationReleaseBlocked(["panorama_sessions_never_release"])
    with reading_the_canon_of(session.canon_pin):
        meaning_map = meaning_map_ref(session.pericope)
        reference = load_map(session.pericope).reference
    release, takes, clips = await manifest_clips(db, session)
    parts = current_parts(takes)
    packet = packet_as_read(release)
    release_id = released_as(release)
    keys = part_keys_by_number(parts)
    names = [file_name(release_id, keys[part.ordinal], part) for part in clips]
    links = await asyncio.gather(
        *(download_link(part, name) for part, name in zip(clips, names, strict=True))
    )
    laid = {sentence.take_id: sentence for sentence in back_translation_of(session).sentences}
    chains = {part.id: _chain(part.id, laid) for part in clips}
    by_id = {take.id: take for take in takes}
    first_take_of_chain = {part.id: by_id[chains[part.id][-1]] for part in clips if part.origin}
    origins = await _origins(db, clips, first_take_of_chain)

    warnings = []
    if meaning_map is None:
        warnings.append(f"no vendored meaning-map for {session.pericope} in VENDOR_MANIFEST.json")
    stored_check = packet.get("check")
    check = _her_check(stored_check, session) if stored_check else None
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
            _clip(
                part, keys[part.ordinal], name, link, origins.get(part.id), len(chains[part.id]) - 1
            )
            for part, name, link in zip(clips, names, links, strict=True)
        ],
        "finalizedAt": as_utc(release.approved_at).isoformat(),
        "finalizeCount": release.version,
        "sessionIds": await _session_ids(db, session),
        "audioFormat": AUDIO_FORMAT
        if clips and all(is_wav(part.content_type) for part in clips)
        else None,
    }
    if whole_is_offered(parts):
        manifest["whole"] = {"filename": whole_filename(release_id), "url": whole_url(session.id)}
    manifest |= {
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


async def _origins(
    db: AsyncSession, clips: list[IRTake], first_take_of_chain: dict[str, IRTake]
) -> dict[str, dict[str, Any]]:
    """Her five keys for each joined part whose scene rehearsal is found, by the part's id.

    ``joinedAt`` is when the part was joined, which is the first take of its chain: a sentence
    laid in later makes a new take that carries the origin forward and lands at its own time.
    """
    joined = [part for part in clips if part.origin]
    if not joined:
        return {}
    found = await db.execute(
        select(IRSceneRehearsal).where(IRSceneRehearsal.id.in_({part.origin for part in joined}))
    )
    rehearsals = {rehearsal.id: rehearsal for rehearsal in found.scalars()}
    return {
        part.id: {
            "kind": "scene-rehearsal",
            "sessionId": rehearsal.session_id,
            "n": rehearsal.n,
            "takeRecordedAt": as_utc(rehearsal.recorded_at).isoformat(),
            "joinedAt": as_utc(first_take_of_chain[part.id].created_at).isoformat(),
        }
        for part in joined
        if (rehearsal := rehearsals.get(part.origin or "")) is not None
    }


def _chain(take_id: str, laid: dict[str, LaidInSentence]) -> list[str]:
    """This part's take and every take a laid-in sentence was spliced over, back to the first."""
    chain = [take_id]
    while chain[-1] in laid:
        chain.append(laid[chain[-1]].previous_take_id)
    return chain


def _her_check(stored: dict[str, Any], session: IRSession) -> dict[str, Any]:
    """The stored check in her keys and order, with nobody's name on it."""
    check = {key: stored.get(key) for key in _HER_CHECK}
    if stored.get("nuances"):
        check["nuances"] = stored["nuances"]
    check["retroUrl"] = passage_retro_url(session)
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
