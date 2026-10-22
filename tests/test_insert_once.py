"""ENG-1263 — `insert_once` inserts a row unless one already holds the conflict key."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.insert_once import insert_once
from app.db.models.internalization_room import IRIdempotencyKey


def a_key(*, claim: str = "first") -> dict[str, object]:
    return {
        "key": "k-1",
        "route": "turns",
        "request_hash": "h",
        "claim": claim,
        "claimed_at": datetime.now(UTC),
    }


async def rows(db: AsyncSession) -> list[IRIdempotencyKey]:
    return list((await db.execute(select(IRIdempotencyKey))).scalars().all())


async def test_the_first_insert_lands_and_says_so(db_session: AsyncSession) -> None:
    inserted = await insert_once(
        db_session, IRIdempotencyKey, a_key(), conflict_on=["key", "route"]
    )

    assert inserted is True
    assert [row.claim for row in await rows(db_session)] == ["first"]


async def test_a_second_insert_on_the_same_key_leaves_the_first_and_says_it_inserted_nothing(
    db_session: AsyncSession,
) -> None:
    await insert_once(db_session, IRIdempotencyKey, a_key(), conflict_on=["key", "route"])

    inserted = await insert_once(
        db_session, IRIdempotencyKey, a_key(claim="second"), conflict_on=["key", "route"]
    )

    assert inserted is False
    assert [row.claim for row in await rows(db_session)] == ["first"]


async def test_the_insert_is_not_committed_for_the_caller(db_session: AsyncSession) -> None:
    await insert_once(db_session, IRIdempotencyKey, a_key(), conflict_on=["key", "route"])

    await db_session.rollback()

    assert await db_session.scalar(select(func.count()).select_from(IRIdempotencyKey)) == 0
