"""Postgres' row lock on `ir_sessions`, stood in for on SQLite, where `FOR UPDATE` does nothing.

The room touches the session's row with two statements that lock it: a `SELECT … FOR UPDATE`
naming `ir_sessions`, and an `UPDATE` of `ir_sessions` (the **Turn claim**'s conditional write and
every `_written_forward`, both through `execute(update(...))`). Either one, run by a session that
does not hold the row, waits until the holder commits, rolls back or closes; then it holds the
row. A wait past `WAITS_AT_MOST_S` raises, as `lock_timeout` does.

Only statements run through `execute` and `scalar` are seen: ORM flushes, `get` and `refresh`
with a lock are not, which the witness that the row is taken in one place covers. The model is
stricter than Postgres: one lock for every session row, taken even by a statement whose `WHERE`
matches no row.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

WAITS_AT_MOST_S = 10.0


class SessionRowLock:
    def __init__(self) -> None:
        self.holder: AsyncSession | None = None
        self.taken_at = 0.0
        self.spans: list[float] = []
        self.free = asyncio.Event()
        self.free.set()

    @property
    def held(self) -> bool:
        return self.holder is not None

    async def take(self, by: AsyncSession) -> None:
        async with asyncio.timeout(WAITS_AT_MOST_S):
            while self.holder is not None and self.holder is not by:
                await self.free.wait()
        if self.holder is None:
            self.holder, self.taken_at = by, time.monotonic()
            self.free.clear()

    def let_go(self, by: AsyncSession) -> None:
        if self.holder is by:
            self.spans.append(time.monotonic() - self.taken_at)
            self.holder = None
            self.free.set()


def _locks_the_session_row(statement: Any) -> bool:
    if getattr(statement, "is_update", False):
        return bool(statement.table.name == "ir_sessions")
    if getattr(statement, "_for_update_arg", None) is None:
        return False
    return any(getattr(one, "name", None) == "ir_sessions" for one in statement.get_final_froms())


def the_session_row_locks_as_postgres_does(monkeypatch: pytest.MonkeyPatch) -> SessionRowLock:
    lock = SessionRowLock()
    execute, scalar, commit = AsyncSession.execute, AsyncSession.scalar, AsyncSession.commit
    rollback, close = AsyncSession.rollback, AsyncSession.close

    async def locking(self: AsyncSession, statement: Any, *args: Any, **kwargs: Any) -> Any:
        if _locks_the_session_row(statement):
            await lock.take(self)
        return await execute(self, statement, *args, **kwargs)

    async def locking_one(self: AsyncSession, statement: Any, *args: Any, **kwargs: Any) -> Any:
        if _locks_the_session_row(statement):
            await lock.take(self)
        return await scalar(self, statement, *args, **kwargs)

    async def committing(self: AsyncSession) -> None:
        try:
            await commit(self)
        finally:
            lock.let_go(self)

    async def rolling_back(self: AsyncSession) -> None:
        try:
            await rollback(self)
        finally:
            lock.let_go(self)

    async def closing(self: AsyncSession) -> None:
        try:
            await close(self)
        finally:
            lock.let_go(self)

    monkeypatch.setattr(AsyncSession, "execute", locking)
    monkeypatch.setattr(AsyncSession, "scalar", locking_one)
    monkeypatch.setattr(AsyncSession, "commit", committing)
    monkeypatch.setattr(AsyncSession, "rollback", rolling_back)
    monkeypatch.setattr(AsyncSession, "close", closing)
    return lock
