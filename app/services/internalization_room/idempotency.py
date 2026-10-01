from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Final

from sqlalchemy import delete, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.core.exceptions import IdempotencyKeyInFlight, IdempotencyKeyReused
from app.db.models.internalization_room import IRIdempotencyKey

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
    return 200 <= status_code < 300 or (400 <= status_code < 500 and status_code != 429)


async def claim(key: str, route: str, request_hash: str) -> Claim | Replay:
    async with AsyncSessionLocal() as db:
        now = utcnow()
        held = await db.get(IRIdempotencyKey, (key, route))
        if held is not None and now - held.claimed_at >= IDEMPOTENCY_KEY_TTL:
            await _drop(db, held)
            held = None
        found = held or await _first(db, key, route, request_hash, now)
        if isinstance(found, Claim):
            return found
        return await _the_answer_to(db, found, request_hash, now)


async def settle(held: Claim, status_code: int, body: bytes) -> None:
    if not settles(status_code):
        await release(held)
        return
    async with AsyncSessionLocal() as db:
        await db.execute(
            update(IRIdempotencyKey)
            .where(*_still_mine(held))
            .values(status_code=status_code, body=body)
        )
        await db.commit()


async def release(held: Claim) -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(delete(IRIdempotencyKey).where(*_still_mine(held)))
        await db.commit()


def _still_mine(held: Claim) -> tuple:
    return (
        IRIdempotencyKey.key == held.key,
        IRIdempotencyKey.route == held.route,
        IRIdempotencyKey.claim == held.token,
        IRIdempotencyKey.status_code.is_(None),
    )


async def _drop(db: AsyncSession, held: IRIdempotencyKey) -> None:
    await db.execute(
        delete(IRIdempotencyKey).where(
            IRIdempotencyKey.key == held.key,
            IRIdempotencyKey.route == held.route,
            IRIdempotencyKey.claim == held.claim,
        )
    )
    await db.commit()
    db.expunge(held)


async def _first(
    db: AsyncSession, key: str, route: str, request_hash: str, now: datetime
) -> Claim | IRIdempotencyKey:
    token = str(uuid.uuid4())
    db.add(
        IRIdempotencyKey(
            key=key, route=route, request_hash=request_hash, claim=token, claimed_at=now
        )
    )
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        winner = await db.get(IRIdempotencyKey, (key, route))
        if winner is None:
            raise IdempotencyKeyInFlight(IN_FLIGHT) from None
        return winner
    return Claim(key=key, route=route, token=token)


async def _the_answer_to(
    db: AsyncSession, held: IRIdempotencyKey, request_hash: str, now: datetime
) -> Claim | Replay:
    if held.request_hash != request_hash:
        raise IdempotencyKeyReused("This Idempotency-Key was already sent with another request")
    if held.status_code is not None:
        return Replay(status_code=held.status_code, body=held.body or b"")
    if now - held.claimed_at < ABANDONED_AFTER:
        raise IdempotencyKeyInFlight(IN_FLIGHT)
    return await _take_over(db, held, now)


async def _take_over(db: AsyncSession, held: IRIdempotencyKey, now: datetime) -> Claim:
    token = str(uuid.uuid4())
    taken = await db.execute(
        update(IRIdempotencyKey)
        .where(
            IRIdempotencyKey.key == held.key,
            IRIdempotencyKey.route == held.route,
            IRIdempotencyKey.claim == held.claim,
        )
        .values(claim=token, claimed_at=now)
    )
    await db.commit()
    if taken.rowcount != 1:  # type: ignore[attr-defined]
        raise IdempotencyKeyInFlight(IN_FLIGHT)
    return Claim(key=held.key, route=held.route, token=token)
