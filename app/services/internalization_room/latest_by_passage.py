"""What the Desk reads on each of a team's passages: its latest release and its open findings.

One statement each for the whole team, not one per passage. Both read live sessions only (ADR
0047), and a release is kept or dropped by its session, because a release forced on a session
after its Zerar is written unstamped.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRRelease, IRSession
from app.models.internalization_room import PassageRelease
from app.services.internalization_room.back_translation import (
    BackTranslationState,
    findings_remaining,
)
from app.services.internalization_room.entered import latest_entered_first
from app.services.internalization_room.live import live


async def latest_releases(db: AsyncSession, project_id: str) -> dict[str, PassageRelease]:
    """Each passage's live release with the highest **Version**, whichever session wrote it."""
    rows = await db.execute(
        select(
            IRRelease.pericope,
            IRRelease.version,
            IRRelease.forced_at,
            IRRelease.approved_at,
            IRRelease.packet["release_id"].as_string().label("release_id"),
        )
        .join(IRSession, IRSession.id == IRRelease.session_id)
        .where(IRRelease.project_id == project_id, live())
        .order_by(IRRelease.version.desc())
    )
    latest: dict[str, PassageRelease] = {}
    for row in rows:
        if row.pericope not in latest:
            latest[row.pericope] = PassageRelease(
                release_id=row.release_id,
                version=row.version,
                forced_at=row.forced_at,
                approved_at=row.approved_at,
            )
    return latest


async def open_findings(db: AsyncSession, project_id: str) -> dict[str, int]:
    """The open findings on each passage's latest live session, in any language.

    Latest is the order the Desk already reads a team's sessions in: a room the team entered,
    then the most recent activity.
    """
    rows = await db.execute(
        select(IRSession.pericope, IRSession.back_translation)
        .where(IRSession.project_id == project_id, live())
        .order_by(*latest_entered_first())
    )
    latest: dict[str, int] = {}
    for row in rows:
        if row.pericope not in latest:
            state = BackTranslationState.model_validate(row.back_translation or {})
            latest[row.pericope] = findings_remaining(state.findings)
    return latest
