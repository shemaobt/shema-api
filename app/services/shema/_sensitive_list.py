"""The sensitive-country list's one reader and one writer — *lida pelo servidor num lugar só*.

OBT-616. Every write of a project asks the list whether its place names a sensitive country, the
record tells the coordination which listed countries its place names, and the Admin reads and
replaces it. All of them go through :func:`sensitive_countries`, so the rule the save applies and
the list the Admin sees cannot be two readings of the table; ``tests/test_shema/
test_sensitive_countries.py`` fails when another file of the module names the table.

**What the list does with a place is not here.** Reading ``location`` is
``_redaction.py``'s — the one reader of the guarded columns — and comparing a place with the list
is :class:`~app.utils.shema_derivations.SensitiveCountries`', beside the region's map it shares.
This file hands the rows over as that value and nothing more.

**Nothing here commits.** The replace is the Admin's act, and its caller stages the change log's
row beside it and commits once.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import NamedTuple

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.shema_sensitive_country import ShemaSensitiveCountry
from app.utils.shema_derivations import SensitiveCountries, country_key


class ListedCountry(NamedTuple):
    """One listed country as it travels between the table and its callers."""

    name: str
    spellings: tuple[str, ...]


async def listed_countries(db: AsyncSession) -> list[ListedCountry]:
    """The list's rows, in the order a reader of Portuguese expects them — accents aside."""
    rows = (await db.execute(select(ShemaSensitiveCountry))).scalars().all()
    return sorted(
        (ListedCountry(row.name, tuple(row.spellings or ())) for row in rows),
        key=lambda entry: country_key(entry.name),
    )


async def sensitive_countries(db: AsyncSession) -> SensitiveCountries:
    """The list as the write path and the record ask it."""
    return SensitiveCountries.of(await listed_countries(db))


async def replace_sensitive_countries(db: AsyncSession, entries: Sequence[ListedCountry]) -> None:
    """Stage the list as ``entries`` — every row replaced, inside the caller's transaction."""
    await db.execute(delete(ShemaSensitiveCountry))
    db.add_all(
        ShemaSensitiveCountry(name=name, spellings=list(spellings)) for name, spellings in entries
    )
    await db.flush()
