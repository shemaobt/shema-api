"""The **Checagem externa**: the record that a team opened the external check of one version.

One per release (ADR 0082). The first open of an approved version creates it, copying the
version's parts and frases out of the release's stored packet; every later open answers it.
"""

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DraftNotApproved
from app.db.models.internalization_room import IRExternalCheck, IRRelease, IRSession
from app.services.internalization_room.approved_draft import approved_draft
from app.utils.stored_time import as_utc

logger = logging.getLogger(__name__)


async def open_the_external_check(
    db: AsyncSession, session: IRSession, *, device_id: str | None
) -> IRExternalCheck:
    """The external check of the version this session's draft stands approved under.

    Refused while the draft does not stand approved (ADR 0071, ADR 0081). Two opens at once
    leave one record: the loser meets the winner at the unique index and answers it, the way
    the scene rehearsal's first writer wins. Only the open that creates it writes the log line,
    and nothing else tells the facilitator.
    """
    release = await approved_draft(db, session)
    if release is None:
        raise DraftNotApproved(
            "This session's draft does not stand approved: approve it before opening the "
            "external check"
        )
    existing = await the_check_of(db, release.id)
    if existing is not None:
        return existing
    check = IRExternalCheck(
        release_id=release.id,
        session_id=release.session_id,
        version=release.version,
        device_id=device_id,
        takes=_takes(release.packet),
        frases=_frases(release.packet),
    )
    db.add(check)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        winner = await the_check_of(db, check.release_id)
        if winner is None:
            raise
        return winner
    await db.refresh(check)
    _log_the_open(release, check)
    return check


async def the_check_of(db: AsyncSession, release_id: str) -> IRExternalCheck | None:
    found: IRExternalCheck | None = await db.scalar(
        select(IRExternalCheck).where(IRExternalCheck.release_id == release_id)
    )
    return found


def _takes(packet: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {"take_id": take["take_id"], "key": take.get("key")}
        for take in packet["audio"]["rehearsal_takes"]
    ]


def _frases(packet: dict[str, Any]) -> list[dict[str, Any]]:
    """The told stretches as the listeners will hear them, never the team's words (ADR 0111).

    A release written before frases were numbered carries none, and one written before the
    telling-back was stored carries no stretches; its takes may still stand, since approval
    reads only the takes. The frase is the stretch's place in the reading, which is what the
    packet's own order already is.
    """
    segments = (packet.get("back_translation") or {}).get("segments", [])
    return [
        {
            "frase": segment.get("frase", place),
            "segment_id": segment["segment_id"],
            "take_id": segment["take_id"],
            "starts_ms": segment["starts_ms"],
            "ends_ms": segment["ends_ms"],
        }
        for place, segment in enumerate(segments, start=1)
    ]


def _log_the_open(release: IRRelease, check: IRExternalCheck) -> None:
    logger.info(
        "[checagem-externa] opened %s %s v%d frases=%d at %s session=%s",
        release.project_id,
        release.pericope,
        check.version,
        len(check.frases),
        as_utc(check.opened_at).isoformat(),
        check.session_id,
    )
