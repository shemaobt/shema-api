"""The **Manifest** Refine receives for an approved passage: her document, in her order."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DraftNotApproved, NotFoundError
from app.db.models.internalization_room import IRRelease, IRSceneRehearsal, IRSession, IRTake
from app.services.device.demo_team import is_the_demo_team
from app.services.internalization_room.approved_draft import (
    approved_draft,
    latest_release,
    stands_on,
)
from app.services.internalization_room.back_translation import LaidInSentence
from app.services.internalization_room.canon.book_material import meaning_map_ref
from app.services.internalization_room.canon.kept import reading_the_canon_of
from app.services.internalization_room.canon.parse_map import load_map
from app.services.internalization_room.check_block import passage_retro_url
from app.services.internalization_room.coverage import is_panorama
from app.services.internalization_room.outside_listeners import external_check_pointer
from app.services.internalization_room.release import (
    InternalizationReleaseBlocked,
    _mother_tongue,
    _recording_grain,
    packet_as_read,
    release_name,
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


@dataclass
class _Reading:
    """What differs between the manifest of a standing approval and the live one."""

    release_id: str
    language: str | None
    finalized_at: str | None
    finalize_count: int
    check: dict[str, Any] | None
    external_check: dict[str, Any] | None
    warn_no_check: bool


async def _of_the_approval(db: AsyncSession, session: IRSession, release: IRRelease) -> _Reading:
    packet = packet_as_read(release)
    stored_check = packet.get("check")
    check = _her_check(stored_check, session) if stored_check else None
    return _Reading(
        release_id=released_as(release),
        language=packet["language"] if "language" in packet else await _mother_tongue(db, session),
        finalized_at=as_utc(release.approved_at).isoformat(),
        finalize_count=release.version,
        check=check,
        external_check=await external_check_pointer(db, release),
        warn_no_check=check is None,
    )


async def _of_the_live_draft(db: AsyncSession, session: IRSession) -> _Reading:
    """The draft as it stands, named after the passage's last release: version 1 when none."""
    if (
        session.project_id is None
        or session.archive_id is not None
        or await is_the_demo_team(db, session.project_id)
    ):
        raise DraftNotApproved(f"Internalization room session {session.id} has no approved draft")
    language = await _mother_tongue(db, session)
    last = await latest_release(db, session.project_id, session.pericope)
    return _Reading(
        release_id=released_as(last) if last else release_name(language, session.pericope, 1),
        language=language,
        finalized_at=None,
        finalize_count=last.version if last else 0,
        check=None,
        external_check=None,
        warn_no_check=False,
    )


async def refine_manifest(db: AsyncSession, session: IRSession) -> dict[str, Any]:
    """The manifest of this session's draft: the approved one, or the live one before approval.

    A draft that stands approved is built from the release it stands under. Any other draft of
    a live team session is read as it is now, under the passage's last release's id (version 1
    when none), with an empty finalised time and an empty check, and is ``NotFoundError`` when
    it holds no take. An archived, demo or team-less session is ``DraftNotApproved``. Both read
    the session's current parts and the canon at the session's pin. Neither carries a frase's
    words, a note, a superseded take, nobody who forced it, no order clock and no clock offset:
    those are the consultant's, in the **Retroverification file**, and the stored **Packet**
    stays the record.
    """
    if is_panorama(session.pericope):
        raise InternalizationReleaseBlocked(["panorama_sessions_never_release"])
    with reading_the_canon_of(session.canon_pin):
        meaning_map = meaning_map_ref(session.pericope)
        reference = load_map(session.pericope).reference
    release = await approved_draft(db, session)
    takes = await takes_of(db, session.id)
    parts = current_parts(takes)
    if release is not None and stands_on(release, parts):
        reading = await _of_the_approval(db, session, release)
    else:
        reading = await _of_the_live_draft(db, session)
    clips = [part for part in parts if not is_declared(part)]
    if reading.finalized_at is None and not clips:
        raise NotFoundError(f"Internalization room session {session.id} holds no take")
    release_id = reading.release_id
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
    if reading.warn_no_check:
        warnings.append(NO_CHECK_RECORDED)

    manifest: dict[str, Any] = {
        "releaseId": release_id,
        "pericopeId": session.pericope,
        "reference": reference,
        "language": reading.language,
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
        "finalizedAt": reading.finalized_at,
        "finalizeCount": reading.finalize_count,
        "sessionIds": await _session_ids(db, session),
        "audioFormat": AUDIO_FORMAT
        if clips and all(is_wav(part.content_type) for part in clips)
        else None,
    }
    if whole_is_offered(parts):
        manifest["whole"] = {"filename": whole_filename(release_id), "url": whole_url(session.id)}
    manifest |= {
        "integrity": INTEGRITY,
        "externalCheck": reading.external_check,
        "check": reading.check,
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
