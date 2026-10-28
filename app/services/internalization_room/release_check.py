from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.core.exceptions import DraftNotApproved
from app.db.models.internalization_room import (
    IRRelease,
    IRSceneRehearsal,
    IRSegment,
    IRSession,
    IRTake,
)
from app.services.internalization_room.approved_draft import approved_draft
from app.services.internalization_room.back_translation import (
    UNTRANSLATED_MIN_MS,
    LaidInSentence,
    rehearsed_parts,
    unheard_parts,
)
from app.services.internalization_room.check_block import standing_state
from app.services.internalization_room.manifest import manifest_clips
from app.services.internalization_room.segments import final_segments, told_back
from app.services.internalization_room.sessions import back_translation_of
from app.services.internalization_room.take_downloads import part_keys_by_number
from app.services.internalization_room.takes import (
    TakeStore,
    current_parts,
    is_declared,
    recording_digest,
    take_store,
    takes_of,
)

logger = logging.getLogger(__name__)

SPAN_TOLERANCE_MS = 50


async def _kept_intact(store: TakeStore, key: str, sha256: str) -> bool:
    audio = await store.get(key)
    return audio is not None and bool(audio) and recording_digest(audio) == sha256


async def _bytes_match_their_sha256(db: AsyncSession, store: TakeStore, release: IRRelease) -> bool:
    pinned = release.packet["audio"]["rehearsal_takes"]
    rows = await db.execute(select(IRTake).where(IRTake.id.in_([one["take_id"] for one in pinned])))
    held = {take.id: take for take in rows.scalars()}
    for one in pinned:
        take = held.get(one["take_id"])
        if take is None:
            return False
        if not is_declared(take) and not await _kept_intact(store, take.storage_key, one["sha256"]):
            return False
    return True


def frases_fit_their_takes(parts: list[IRTake], told: list[IRSegment]) -> tuple[bool, list[str]]:
    notes: list[str] = []
    passed = {one.take_id for one in told} <= {part.id for part in parts}
    for part in parts:
        spans = sorted((one.starts_ms, one.ends_ms) for one in told if one.take_id == part.id)
        passed &= bool(spans)
        covered_to = 0
        for starts, ends in spans:
            if starts - covered_to >= UNTRANSLATED_MIN_MS:
                notes.append(f"{part.id}: {starts - covered_to} ms uncovered at {covered_to} ms")
            passed &= covered_to - starts <= SPAN_TOLERANCE_MS
            passed &= not part.duration_ms or ends - part.duration_ms <= SPAN_TOLERANCE_MS
            covered_to = max(covered_to, ends)
        if part.duration_ms and part.duration_ms - covered_to >= UNTRANSLATED_MIN_MS:
            notes.append(f"{part.id}: {part.duration_ms - covered_to} ms uncovered at the end")
    return passed, notes


async def splices_are_intact(
    store: TakeStore, sentences: list[LaidInSentence], takes: list[IRTake]
) -> bool:
    held = {take.id for take in takes}
    for one in sentences:
        if not {one.take_id, one.previous_take_id} <= held:
            return False
        if not await _kept_intact(store, one.storage_key, one.sha256):
            return False
    return True


async def _every_origin_resolves(db: AsyncSession, parts: list[IRTake]) -> bool:
    origins = {part.origin for part in parts if part.origin}
    found = await db.execute(select(IRSceneRehearsal.id).where(IRSceneRehearsal.id.in_(origins)))
    return origins <= set(found.scalars())


async def _the_manifest_names_the_pinned_takes(
    db: AsyncSession, session: IRSession, release: IRRelease
) -> tuple[bool, list[str]]:
    try:
        _release, takes, clips = await manifest_clips(db, session)
    except DraftNotApproved:
        return True, ["manifest_unread"]
    keys = part_keys_by_number(current_parts(takes))
    declared = {take.id for take in takes if is_declared(take)}
    pinned = [
        [one["key"], one["take_id"], one["sha256"]]
        for one in release.packet["audio"]["rehearsal_takes"]
        if one["take_id"] not in declared
    ]
    return [[keys[clip.ordinal], clip.id, clip.sha256] for clip in clips] == pinned, []


async def run_release_check(
    db: AsyncSession, store: TakeStore, release: IRRelease
) -> dict[str, Any]:
    session = await db.get_one(IRSession, release.session_id)
    takes = await takes_of(db, session.id)
    stretches = await final_segments(db, session.id, takes)
    telling_back = await standing_state(db, session.id, back_translation_of(session), takes)
    standing = await approved_draft(db, session)
    parts = current_parts(takes)
    fit, fit_notes = frases_fit_their_takes(parts, told_back(stretches))
    same, same_notes = await _the_manifest_names_the_pinned_takes(db, session, release)
    verdicts = {
        "bytes_match_sha256": await _bytes_match_their_sha256(db, store, release),
        "frases_fit_their_takes": fit,
        "nothing_awaiting_translation": told_back(stretches) == stretches,
        "splices_intact": await splices_are_intact(store, telling_back.sentences, takes),
        "every_origin_resolves": await _every_origin_resolves(db, parts),
        "everything_heard": not (
            rehearsed_parts(stretches) and unheard_parts(telling_back, parts, stretches)
        ),
        "approval_matches_live_state": standing is not None and standing.id == release.id,
        "manifest_names_the_same_takes": same,
    }
    notes = {"frases_fit_their_takes": fit_notes, "manifest_names_the_same_takes": same_notes}
    return {
        "ran_at": datetime.now(UTC).isoformat(),
        "whole": all(verdicts.values()),
        "checks": [
            {"name": name, "passed": passed, **({"notes": notes[name]} if notes.get(name) else {})}
            for name, passed in verdicts.items()
        ],
    }


async def check_release(release_id: str) -> None:
    try:
        async with AsyncSessionLocal() as db:
            release = await db.get_one(IRRelease, release_id)
            result = await run_release_check(db, take_store(), release)
            await db.execute(
                update(IRRelease)
                .where(IRRelease.id == release_id, IRRelease.release_check.is_(None))
                .values(release_check=result)
            )
            await db.commit()
    except Exception:
        logger.exception("The release check of %s failed", release_id)
