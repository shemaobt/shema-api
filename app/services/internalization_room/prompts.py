from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRPrompt, IRPromptKey
from app.services.internalization_room._default_prompts import default_prompt


async def seed_room_prompts(db: AsyncSession) -> int:
    """Insert a default row for any room prompt that does not have one yet.

    Idempotent and safe under concurrent boots: each insert runs in a savepoint, so a
    replica losing the race on the unique `key` just moves on.
    """
    result = await db.execute(select(IRPrompt.key))
    existing = set(result.scalars().all())

    inserted = 0
    for key in IRPromptKey:
        if str(key) in existing:
            continue
        default = default_prompt(key)
        row = IRPrompt(
            key=str(key),
            name=default["name"],
            description=default["description"],
            prompt=default["prompt"],
            version=1,
        )
        try:
            async with db.begin_nested():
                db.add(row)
            inserted += 1
        except IntegrityError:
            continue

    if inserted:
        await db.commit()
    return inserted


async def get_prompt_text(db: AsyncSession, key: IRPromptKey) -> str:
    """Stored prompt body when present, otherwise the baked-in default."""
    result = await db.execute(select(IRPrompt.prompt).where(IRPrompt.key == str(key)))
    row = result.scalar_one_or_none()
    if row is not None:
        return row
    return default_prompt(key)["prompt"]
