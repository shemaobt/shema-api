from __future__ import annotations

import asyncio
import os
import time
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import load_only

from app.core.database import AsyncSessionLocal
from app.db.models.internalization_room import IRSession
from app.services.internalization_room.coverage import is_panorama
from app.services.internalization_room.entered import entered
from app.services.internalization_room.live import live
from app.services.internalization_room.session_end import SessionState, end_of

WINDOW_MINUTES = 60
POLL_SECONDS = 60
DEADLINE_MINUTES = 300


async def holding(db: AsyncSession, now: datetime, window: timedelta) -> list[IRSession]:
    result = await db.execute(
        select(IRSession)
        .options(
            load_only(
                IRSession.project_id,
                IRSession.pericope,
                IRSession.created_at,
                IRSession.ended_at,
                IRSession.updated_at,
            )
        )
        .where(
            IRSession.project_id.is_not(None),
            live(),
            entered(),
            IRSession.updated_at >= now - window,
        )
    )
    return [
        session
        for session in result.scalars()
        if not is_panorama(session.pericope) and end_of(session).state is SessionState.IN_PROGRESS
    ]


def named(sessions: list[IRSession]) -> str:
    return "\n".join(
        f"  {session.id}  project {session.project_id}  passage {session.pericope}"
        f"  last moved {session.updated_at:%Y-%m-%d %H:%M} UTC"
        for session in sessions
    )


async def wait() -> int:
    poll = float(os.environ.get("DEPLOY_HOLD_POLL_SECONDS", POLL_SECONDS))
    deadline = float(os.environ.get("DEPLOY_HOLD_DEADLINE_MINUTES", DEADLINE_MINUTES))
    started = time.monotonic()
    while True:
        async with AsyncSessionLocal() as db:
            held = await holding(db, datetime.now(UTC), timedelta(minutes=WINDOW_MINUTES))
        if not held:
            print("No team session is open; the deploy goes on.", flush=True)
            return 0
        if os.environ.get("DEPLOY_URGENT") == "true":
            print(
                f"::warning::An urgent deploy does not wait for the {len(held)} open team"
                f" session(s):\n{named(held)}",
                flush=True,
            )
            return 0
        if time.monotonic() - started >= deadline * 60:
            print(
                f"::error::The deploy waited {deadline:g} minutes and these team sessions"
                f" were still open, so nothing shipped:\n{named(held)}",
                flush=True,
            )
            return 1
        print(f"Waiting on {len(held)} open team session(s):\n{named(held)}", flush=True)
        await asyncio.sleep(poll)


def main() -> int:
    return asyncio.run(wait())


if __name__ == "__main__":
    raise SystemExit(main())
