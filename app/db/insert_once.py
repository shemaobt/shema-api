"""``INSERT … ON CONFLICT DO NOTHING``, which SQLAlchemy ships once per dialect and not once.

``on_conflict_do_nothing`` lives on ``postgresql.insert`` and on ``sqlite.insert`` and on no
common statement, and production runs one engine where the suite runs the other. The three
doors that insert-or-find a row (the team's session key, the idempotency key, the turn's
answer) dispatch on the bind's dialect here, once.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.ext.asyncio import AsyncSession


async def insert_once(
    db: AsyncSession,
    model: type[Any],
    values: Mapping[str, Any],
    *,
    conflict_on: Sequence[str],
) -> bool:
    """Insert one row of ``model`` unless one already holds ``conflict_on``, and say whether
    this call inserted it. Never commits: the caller's transaction is the caller's.
    """
    insert = postgresql.insert if db.get_bind().dialect.name == "postgresql" else sqlite.insert
    result = await db.execute(
        insert(model).values(**values).on_conflict_do_nothing(index_elements=list(conflict_on))
    )
    return bool(result.rowcount)  # type: ignore[attr-defined]
