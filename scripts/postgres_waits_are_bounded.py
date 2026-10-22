"""Exit 1 unless a transaction of the app's engine carries its two waits on Postgres.

Production reaches Neon through its pooler, which hands a connection to another client
between transactions and drops what a connection was started with. So the two waits are
set in every transaction instead (ADR 0079), and only a transaction on a real Postgres can
show that they are. The migrations job has one, and runs this against it with
`DATABASE_URL` pointing there.
"""

from __future__ import annotations

import asyncio

from sqlalchemy import text

from app.core.database import LOCK_TIMEOUT, STATEMENT_TIMEOUT, engine

#: What Postgres answers `SHOW` with for each wait the app sets.
EXPECTED = {"lock_timeout": LOCK_TIMEOUT, "statement_timeout": STATEMENT_TIMEOUT}


async def waits_in_a_transaction() -> dict[str, str]:
    async with engine.connect() as connection:
        return {
            name: str((await connection.execute(text(f"SHOW {name}"))).scalar_one())
            for name in EXPECTED
        }


def main() -> None:
    found = asyncio.run(waits_in_a_transaction())
    if found != EXPECTED:
        raise SystemExit(f"a transaction of the app carries {found}, not {EXPECTED}")
    print(f"a transaction of the app carries {found}")


if __name__ == "__main__":
    main()
