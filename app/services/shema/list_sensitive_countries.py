"""``GET /api/shema/sensitive-countries`` — the list as the Admin reads it (OBT-616).

Only the Admin reads it — Daniel, 19/out/2026 — and that is the route's ``AdminUser``, as every
Admin read of the module (the invitations, the grants, the pending projects) relies on the guard
alone; the writes read the Admin's standing fresh. The rows come from ``_sensitive_list.py``, the
table's one reader, so what the Admin reads is what every save compares a place with.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.shema_sensitive_countries import SensitiveCountry, SensitiveCountryList
from app.services.shema._sensitive_list import listed_countries


async def list_sensitive_countries(db: AsyncSession) -> SensitiveCountryList:
    """Every listed country with its spellings, ordered by name — accents aside."""
    return SensitiveCountryList(
        countries=[
            SensitiveCountry(name=name, spellings=list(spellings))
            for name, spellings in await listed_countries(db)
        ]
    )
