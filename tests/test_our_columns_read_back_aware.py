"""A moment read back out of our own tables says which clock it is on, whatever the engine.

`DateTime(timezone=True)` is a promise the driver keeps differently on either side:
**Postgres reads back aware and SQLite reads back naive**, off one schema and one writer. So
the suite has been measuring a wire format production does not produce — every case that
compares an `isoformat` string has been pinning the engine it runs on rather than the
contract.

The fix is a column type, not a rule each route remembers, and these two tests are the two
halves of that. The first is the contract itself and is red on SQLite before the type exists.
The second is what stops the fix expiring at the next migration: a new column declared with
the raw type is not covered by anything the first test can see.

**Scope is this stack's own tables — the room and the Desk's devices — and no further.** The
other five products declare their columns the same way and have the same defect; that is
recorded as an issue rather than fixed here, because a diff across six products lands in a
stack nobody merges and conflicts with everyone.
"""

from __future__ import annotations

import ast
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.device import Device
from app.db.models.internalization_room import IRSession

#: The declarations this slice covers. Both are read by the Desk.
OUR_MODELS = (
    Path("app/db/models/internalization_room.py"),
    Path("app/db/models/device.py"),
)

STORED = datetime(2026, 8, 21, 1, 0, tzinfo=UTC)


async def test_a_moment_read_back_out_of_our_tables_is_aware(db_session: AsyncSession) -> None:
    """Red on SQLite until the column type says so; a no-op on Postgres, which already does.

    Read through a fresh query rather than off the object that wrote it: the identity map
    hands back the aware value the test assigned, which is how a case like this passes over a
    schema that normalises nothing.
    """
    db_session.add(IRSession(id="sessao-do-relogio", pericope="P03", ended_at=STORED))
    await db_session.commit()
    db_session.expire_all()

    session = (
        await db_session.execute(select(IRSession).where(IRSession.id == "sessao-do-relogio"))
    ).scalar_one()

    assert session.ended_at is not None
    assert session.ended_at.tzinfo is not None, (
        f"ended_at came back as {session.ended_at!r}, which names no clock — "
        "on this engine the column type is not saying what it stores"
    )
    assert session.ended_at == STORED


async def test_a_moment_read_back_off_a_device_row_is_aware(db_session: AsyncSession) -> None:
    """The Desk's half of the same contract.

    Two tables and not one, because the type is applied per declaration: covering only the
    room's would leave the devices panel's columns resting on the syntax check alone.
    """
    db_session.add(
        Device(
            id="tablet-do-relogio",
            claim_code_hash="x",
            claim_code_expires_at=STORED,
            last_seen_at=STORED,
        )
    )
    await db_session.commit()
    db_session.expire_all()

    device = (
        await db_session.execute(select(Device).where(Device.id == "tablet-do-relogio"))
    ).scalar_one()

    assert device.last_seen_at is not None
    assert device.last_seen_at.tzinfo is not None, (
        f"last_seen_at came back as {device.last_seen_at!r}, which names no clock"
    )
    assert device.last_seen_at == STORED


async def test_every_datetime_column_of_ours_is_declared_with_the_utc_type() -> None:
    """What stops the fix expiring at the next migration.

    The test above reads one column of one table. A column added tomorrow with the raw
    `DateTime` is invisible to it — the row simply is not in any assertion — so this reads the
    declarations instead and requires the type by name.

    It is syntax and asks the ORM nothing, which is the same trade `eslint-rules/marks.js`
    takes in the Desk: it cannot see a column built some other way, and what it does see it
    sees for nothing.
    """
    raw: list[str] = []
    for path in OUR_MODELS:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "DateTime"
            ):
                raw.append(f"{path}:{node.lineno}")

    assert not raw, (
        "these columns are declared with the raw DateTime instead of UtcDateTime, so they "
        f"read back naive on SQLite: {', '.join(raw)}"
    )
