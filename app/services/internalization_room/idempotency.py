from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Final

from sqlalchemy import delete, update
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.core.exceptions import IdempotencyKeyInFlight, IdempotencyKeyReused
from app.db.models.internalization_room import IRIdempotencyKey
from app.services.internalization_room.sessions import session_for_room_caller

IDEMPOTENCY_KEY_TTL: Final = timedelta(hours=24)
ABANDONED_AFTER: Final = timedelta(seconds=300)
IN_FLIGHT: Final = "The first request under this Idempotency-Key has not answered yet"


@dataclass(frozen=True)
class Claim:
    key: str
    route: str
    token: str


@dataclass(frozen=True)
class Replay:
    status_code: int
    body: bytes


def utcnow() -> datetime:
    return datetime.now(UTC)


def settles(status_code: int) -> bool:
    return 200 <= status_code < 300 or (400 <= status_code < 500 and status_code not in (409, 429))


async def claim(
    key: str, route: str, request_hash: str, *, session_id: str, project_id: str | None
) -> Claim | Replay:
    async with AsyncSessionLocal() as db:
        await session_for_room_caller(db, session_id, project_id)
        while True:
            now = utcnow()
            row = await db.get(IRIdempotencyKey, (key, route), populate_existing=True)
            if row is not None and now - row.claimed_at >= IDEMPOTENCY_KEY_TTL:
                await _forget(db, row)
            elif row is not None:
                return await _the_answer_to(db, row, request_hash, now)
            else:
                held = Claim(key=key, route=route, token=str(uuid.uuid4()))
                if await _first(db, held, request_hash, now):
                    return held


async def settle(held: Claim, status_code: int, body: bytes) -> None:
    if not settles(status_code):
        await release(held)
        return
    async with AsyncSessionLocal() as db:
        await db.execute(
            update(IRIdempotencyKey)
            .where(*_still_unanswered(held))
            .values(status_code=status_code, body=body)
        )
        await db.commit()


async def release(held: Claim) -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(delete(IRIdempotencyKey).where(*_still_unanswered(held)))
        await db.commit()


def _the_row_of(held: Claim) -> tuple:
    return (
        IRIdempotencyKey.key == held.key,
        IRIdempotencyKey.route == held.route,
        IRIdempotencyKey.claim == held.token,
    )


def _still_unanswered(held: Claim) -> tuple:
    return (*_the_row_of(held), IRIdempotencyKey.status_code.is_(None))


def _held_by(row: IRIdempotencyKey) -> Claim:
    return Claim(key=row.key, route=row.route, token=row.claim)


async def _forget(db: AsyncSession, row: IRIdempotencyKey) -> None:
    await db.execute(delete(IRIdempotencyKey).where(*_the_row_of(_held_by(row))))
    await db.commit()
    db.expunge(row)


async def _first(db: AsyncSession, held: Claim, request_hash: str, now: datetime) -> bool:
    insert = postgresql.insert if db.get_bind().dialect.name == "postgresql" else sqlite.insert
    inserted = await db.execute(
        insert(IRIdempotencyKey)
        .values(
            key=held.key,
            route=held.route,
            request_hash=request_hash,
            claim=held.token,
            claimed_at=now,
        )
        .on_conflict_do_nothing(index_elements=["key", "route"])
    )
    await db.commit()
    return bool(inserted.rowcount)  # type: ignore[attr-defined]


async def _the_answer_to(
    db: AsyncSession, row: IRIdempotencyKey, request_hash: str, now: datetime
) -> Claim | Replay:
    if row.request_hash != request_hash:
        raise IdempotencyKeyReused("This Idempotency-Key was already sent with another request")
    if row.status_code is not None:
        return Replay(status_code=row.status_code, body=row.body or b"")
    if now - row.claimed_at < ABANDONED_AFTER:
        raise IdempotencyKeyInFlight(IN_FLIGHT)
    return await _take_over(db, row, now)


async def _take_over(db: AsyncSession, row: IRIdempotencyKey, now: datetime) -> Claim:
    token = str(uuid.uuid4())
    taken = await db.execute(
        update(IRIdempotencyKey)
        .where(*_still_unanswered(_held_by(row)))
        .values(claim=token, claimed_at=now)
    )
    await db.commit()
    if taken.rowcount != 1:  # type: ignore[attr-defined]
        raise IdempotencyKeyInFlight(IN_FLIGHT)
    return Claim(key=row.key, route=row.route, token=token)
