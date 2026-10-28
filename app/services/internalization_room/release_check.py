from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.db.models.internalization_room import IRRelease, IRSession, IRTake
from app.services.internalization_room.approved_draft import approved_draft
from app.services.internalization_room.segments import final_segments, told_back
from app.services.internalization_room.takes import (
    TakeStore,
    is_declared,
    recording_digest,
    take_store,
    takes_of,
)

logger = logging.getLogger(__name__)


async def _bytes_match_their_sha256(db: AsyncSession, store: TakeStore, release: IRRelease) -> bool:
    pinned = release.packet["audio"]["rehearsal_takes"]
    rows = await db.execute(select(IRTake).where(IRTake.id.in_([one["take_id"] for one in pinned])))
    held = {take.id: take for take in rows.scalars()}
    for one in pinned:
        take = held.get(one["take_id"])
        if take is None:
            return False
        if is_declared(take):
            continue
        audio = await store.get(take.storage_key)
        if not audio or recording_digest(audio) != one["sha256"]:
            return False
    return True


async def run_release_check(
    db: AsyncSession, store: TakeStore, release: IRRelease
) -> dict[str, Any]:
    session = await db.get_one(IRSession, release.session_id)
    takes = await takes_of(db, session.id)
    stretches = await final_segments(db, session.id, takes)
    standing = await approved_draft(db, session)
    verdicts = {
        "bytes_match_sha256": await _bytes_match_their_sha256(db, store, release),
        "nothing_awaiting_translation": told_back(stretches) == stretches,
        "approval_matches_live_state": standing is not None and standing.id == release.id,
    }
    return {
        "ran_at": datetime.now(UTC).isoformat(),
        "whole": all(verdicts.values()),
        "checks": [{"name": name, "passed": passed} for name, passed in verdicts.items()],
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
