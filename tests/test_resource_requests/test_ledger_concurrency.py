"""The double-approve, serialized on the fund row — the test that cannot run on SQLite.

SQLAlchemy compiles ``with_for_update()`` to nothing on that dialect, **silently**: the
same statement reads ``… FOR UPDATE`` on PostgreSQL and loses the clause on SQLite
(design §7.3). A version of this test on the default suite would therefore lock nothing
and pass anyway, which is worse than not having one. So it runs only when
``RR_POSTGRES_TEST_URL`` names a PostgreSQL database, and skips with that reason
declared. The ``test.yml`` service block that would set the variable on every pull request
is written but waits on a push with the ``workflow`` scope, so until that lands the test
runs wherever the variable is set and CI shows the declared skip.

⚠️ The database must be **disposable** — the test drops and recreates the tables it
needs. Point the variable at a scratch database, never at one holding data.

What it proves is exactly what GATE-01 D5 did not relax: the two approvals **serialize**
on the fund row — the second acquires the lock only after the first commits — no
deduction is lost, **both succeed**, and the balance ends negative and correct. There is
no ``insufficient_funds`` refusal to assert, because the product does not have one.
"""

from __future__ import annotations

import asyncio
import os
import time
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base
from app.db.models.auth import User
from app.db.models.resource_request import (
    RRFund,
    RRFundMovement,
    RRMovementKind,
    RRRequest,
    RRSnapshot,
)
from app.services.resource_request import append_movement, fund_balances

POSTGRES_URL_ENV = "RR_POSTGRES_TEST_URL"

pytestmark = pytest.mark.skipif(
    not os.environ.get(POSTGRES_URL_ENV),
    reason=(
        "needs PostgreSQL: SQLAlchemy drops FOR UPDATE silently on SQLite, so this test "
        f"would lock nothing and pass for the wrong reason there — set {POSTGRES_URL_ENV} "
        "to a disposable PostgreSQL database to run it; CI does not set it today, so this "
        "skip is what CI shows"
    ),
)

TABLES = [
    User.__table__,
    RRFund.__table__,
    RRRequest.__table__,
    RRSnapshot.__table__,
    RRFundMovement.__table__,
]


def _async_url() -> str:
    """The URL with the async driver spelled out, so a plain ``postgresql://`` works too."""
    url = os.environ[POSTGRES_URL_ENV]
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


async def test_two_approvals_against_one_fund_serialize_and_both_succeed() -> None:
    engine = create_async_engine(_async_url())
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all, tables=TABLES, checkfirst=True)
            await conn.run_sync(Base.metadata.create_all, tables=TABLES)

        factory = async_sessionmaker(
            engine, expire_on_commit=False, class_=AsyncSession, autoflush=False
        )

        async with factory() as db:
            author = User(email="mesa@concurrency.test", password_hash="irrelevante")
            db.add(author)
            db.add(RRFund(id="linguas", name="Shema Línguas"))
            await db.flush()
            first_request = RRRequest(
                request_type="traducao", created_by=author.id, fund_id="linguas"
            )
            second_request = RRRequest(
                request_type="traducao", created_by=author.id, fund_id="linguas"
            )
            db.add_all([first_request, second_request])
            await db.flush()
            await append_movement(
                db,
                fund_id="linguas",
                kind=RRMovementKind.ALLOCATION,
                amount=Decimal("1000.00"),
                author_id=author.id,
                reason="alocação do Gestor",
            )
            await db.commit()
            author_id = author.id
            request_ids = (first_request.id, second_request.id)

        first_holds_the_lock = asyncio.Event()
        release_the_first = asyncio.Event()
        second_attempting = asyncio.Event()
        first_committed_at: list[float] = []
        second_acquired_at: list[float] = []

        async def first_approval() -> None:
            async with factory() as db:
                await append_movement(
                    db,
                    fund_id="linguas",
                    kind=RRMovementKind.APPROVAL_DEDUCTION,
                    amount=Decimal("700.00"),
                    author_id=author_id,
                    reason="primeira aprovação",
                    request_id=request_ids[0],
                )
                first_holds_the_lock.set()
                await release_the_first.wait()
                await db.commit()
                first_committed_at.append(time.monotonic())

        async def second_approval() -> None:
            await first_holds_the_lock.wait()
            async with factory() as db:
                second_attempting.set()
                await append_movement(
                    db,
                    fund_id="linguas",
                    kind=RRMovementKind.APPROVAL_DEDUCTION,
                    amount=Decimal("600.00"),
                    author_id=author_id,
                    reason="segunda aprovação",
                    request_id=request_ids[1],
                )
                second_acquired_at.append(time.monotonic())
                await db.commit()

        first = asyncio.create_task(first_approval())
        second = asyncio.create_task(second_approval())

        await asyncio.wait_for(second_attempting.wait(), timeout=10)
        await asyncio.sleep(0.4)
        assert not second_acquired_at, (
            "the second approval acquired the fund row while the first still held it — "
            "FOR UPDATE is not serializing"
        )

        release_the_first.set()
        await asyncio.wait_for(asyncio.gather(first, second), timeout=30)

        assert second_acquired_at[0] >= first_committed_at[0], (
            "the second approval's lock must only be granted after the first commits"
        )

        async with factory() as db:
            (balance,) = await fund_balances(db)
            assert balance.allocated == Decimal("1000.00")
            assert balance.committed == Decimal("1300.00"), "a deduction was lost"
            assert balance.available == Decimal("-300.00"), (
                "both approvals succeed and the fund goes negative — GATE-01 D5's answer, "
                "with the warning left to the caller and no refusal anywhere"
            )
    finally:
        await engine.dispose()
