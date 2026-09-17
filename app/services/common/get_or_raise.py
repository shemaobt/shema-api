from typing import TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError

T = TypeVar("T")


async def get_or_raise(
    db: AsyncSession,
    model: type[T],
    entity_id: str,
    *,
    label: str | None = None,
    for_update: bool = False,
) -> T:
    """Fetch a row by primary key or raise NotFoundError.

    With ``for_update`` the row is taken with ``SELECT ... FOR UPDATE``, so concurrent
    writers serialize behind it until the transaction commits or rolls back.
    """
    stmt = select(model).where(model.id == entity_id)  # type: ignore[attr-defined]
    if for_update:
        stmt = stmt.with_for_update()
    result = await db.execute(stmt)
    row = result.scalar_one_or_none()
    if row is None:
        name = label or model.__name__  # type: ignore[attr-defined]
        raise NotFoundError(f"{name} {entity_id} not found")
    return row  # type: ignore[return-value]
