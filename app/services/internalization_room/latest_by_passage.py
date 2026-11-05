"""What the Desk reads on each of a team's passages: its release, findings and draft.

One statement each for the whole team, not one per passage, and one for the drafts of a whole
roll. All read live sessions only (ADR 0047), and a release is kept or dropped by its session,
because a release forced on a session after its Zerar is written unstamped.
"""

from __future__ import annotations

from collections.abc import Collection
from typing import NamedTuple

from sqlalchemy import ColumnElement, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRRelease, IRSession, IRTake, IRTakeKind
from app.models.internalization_room import PassageRelease
from app.services.internalization_room.back_translation import (
    BackTranslationState,
    findings_remaining,
)
from app.services.internalization_room.entered import latest_entered_first
from app.services.internalization_room.forced import was_forced
from app.services.internalization_room.live import live


async def latest_releases(db: AsyncSession, project_id: str) -> dict[str, PassageRelease]:
    """Each passage's live release with the highest **Version**, whichever session wrote it."""
    rows = await db.execute(
        select(
            IRRelease.pericope,
            IRRelease.version,
            IRRelease.forced_by,
            IRRelease.forced_at,
            IRRelease.forced_blockers,
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
                forced_at=row.forced_at if was_forced(row.forced_by, row.forced_blockers) else None,
                approved_at=row.approved_at,
            )
    return latest


class Draft(NamedTuple):
    session_id: str
    has_takes: bool


def _rehearsed() -> ColumnElement[bool]:
    return (
        select(IRTake.id)
        .where(IRTake.session_id == IRSession.id, IRTake.kind == IRTakeKind.ENSAIO)
        .exists()
    )


def _the_draft(held: Draft | None, session_id: str, has_takes: bool) -> Draft:
    """Read latest first, the draft is the latest holding a rehearsal take, else the latest."""
    if held is None or (has_takes and not held.has_takes):
        return Draft(session_id, has_takes)
    return held


async def live_sessions(
    db: AsyncSession, project_id: str
) -> tuple[dict[str, int], dict[str, Draft]]:
    """What each passage's live sessions say, in any language, from one statement.

    The open findings on the latest session: the order the Desk already reads a team's
    sessions in, a room the team entered, then the most recent activity. And the draft the
    hand-off reads, the one the force would pick (ADR 0075): the latest holding a rehearsal
    take; when none does, the latest.
    """
    rows = await db.execute(
        select(
            IRSession.pericope,
            IRSession.id,
            IRSession.back_translation,
            _rehearsed().label("has_takes"),
        )
        .where(IRSession.project_id == project_id, live())
        .order_by(*latest_entered_first())
    )
    findings: dict[str, int] = {}
    drafts: dict[str, Draft] = {}
    for row in rows:
        if row.pericope not in findings:
            state = BackTranslationState.model_validate(row.back_translation or {})
            findings[row.pericope] = findings_remaining(state.findings)
        drafts[row.pericope] = _the_draft(drafts.get(row.pericope), row.id, row.has_takes)
    return findings, drafts


async def drafts_on(
    db: AsyncSession, passages: Collection[tuple[str, str]]
) -> dict[tuple[str, str], Draft]:
    """The draft of each ``(project_id, pericope)``, from one statement, for any number of teams."""
    if not passages:
        return {}
    rows = await db.execute(
        select(
            IRSession.project_id,
            IRSession.pericope,
            IRSession.id,
            _rehearsed().label("has_takes"),
        )
        .where(tuple_(IRSession.project_id, IRSession.pericope).in_(passages), live())
        .order_by(*latest_entered_first())
    )
    drafts: dict[tuple[str, str], Draft] = {}
    for row in rows:
        passage = (row.project_id, row.pericope)
        drafts[passage] = _the_draft(drafts.get(passage), row.id, row.has_takes)
    return drafts
