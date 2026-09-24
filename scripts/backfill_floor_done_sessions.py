"""Close the sessions the old advance gate stranded at the coverage floor.

A dry run by default: it prints what it would do and writes nothing. `--apply` writes it.

    uv run python scripts/backfill_floor_done_sessions.py
    uv run python scripts/backfill_floor_done_sessions.py --apply
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.db.models.internalization_room import IRCoverageEvent, IRSession, IRSessionStatus
from app.services.internalization_room.coverage import PANORAMA_PREFIX, floor_met, furthest
from app.services.internalization_room.progression import active_passages, finished_passages


async def _the_instant_the_floor_was_met(db: AsyncSession, session: IRSession) -> datetime | None:
    events = await db.execute(
        select(IRCoverageEvent.element_key, IRCoverageEvent.status, IRCoverageEvent.at)
        .where(IRCoverageEvent.session_id == session.id)
        .order_by(IRCoverageEvent.at)
    )
    replayed: dict[str, str] = {}
    for key, status, at in events.all():
        replayed = furthest(replayed, {key: status}, pericope_num=session.pericope)
        if floor_met(replayed, session.pericope):
            return at
    return None


async def backfill(db: AsyncSession, *, apply: bool) -> list[str]:
    candidates = await db.execute(
        select(IRSession).where(
            IRSession.status.in_((IRSessionStatus.IN_PROGRESS, IRSessionStatus.NEEDS_PERSON)),
            IRSession.ended_at.is_(None),
            IRSession.pericope.not_like(f"{PANORAMA_PREFIX}%"),
        )
    )
    at_the_floor = [
        session
        for session in candidates.scalars()
        if floor_met(session.coverage_state or {}, session.pericope)
    ]
    stranded = [s for s in at_the_floor if s.status is IRSessionStatus.IN_PROGRESS]
    teams = sorted({s.project_id for s in stranded if s.project_id is not None})
    finished_before = await finished_passages(db, project_ids=teams)
    active_before = await active_passages(db, project_ids=teams)
    report = ["applied" if apply else "dry run: nothing is written"]
    report.extend(
        f"needs_person {session.id} {session.pericope} team={session.project_id} "
        "meets the floor; left as it is"
        for session in at_the_floor
        if session.status is IRSessionStatus.NEEDS_PERSON
    )
    for session in stranded:
        instant = await _the_instant_the_floor_was_met(db, session)
        source = "coverage_event"
        if instant is None:
            instant, source = session.updated_at, "updated_at"
        await db.execute(
            update(IRSession)
            .where(IRSession.id == session.id)
            .values(status=IRSessionStatus.DONE, ended_at=instant, updated_at=IRSession.updated_at)
        )
        report.append(
            f"close {session.id} {session.pericope} team={session.project_id} "
            f"ended_at={instant.isoformat()} from={source}"
        )
    finished_after = await finished_passages(db, project_ids=teams)
    active_after = await active_passages(db, project_ids=teams)
    for team in teams:
        newly = sorted(finished_after.get(team, set()) - finished_before.get(team, set()))
        report.append(
            f"team {team}: finishes {', '.join(newly) or 'nothing'}; "
            f"active passage {active_before[team]} -> {active_after[team]}"
        )
    if apply:
        await db.commit()
    else:
        await db.rollback()
    return report


async def _main(apply: bool) -> None:
    async with AsyncSessionLocal() as db:
        for line in await backfill(db, apply=apply):
            print(line)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="write what the dry run prints")
    asyncio.run(_main(parser.parse_args().apply))


if __name__ == "__main__":
    main()
