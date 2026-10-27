"""The list of sensitive countries — the Admin reads it and replaces it whole (OBT-616).

Two routes, each behind :data:`~app.api.shema._deps.AdminUser`, inside the ``authenticated``
router that already refuses anybody with no Shemá role — so every other role reads a 403 and the
Admin alone reaches the list (Daniel, 19/out/2026, *só o Admin edita a lista*):

* ``GET /sensitive-countries`` — the list, every country with its spellings;
* ``PUT /sensitive-countries`` — the list as it is to stand.

Not under ``/access``: that surface is who enters and with which role, and this list decides which
places are withheld. The handlers declare the guard and the body and call one service each (ADR
0009); ``docs/shema.md`` §9.5 is the contract.
"""

from __future__ import annotations

from fastapi import APIRouter, Response

from app.api.shema._deps import APP_KEY, PER_READER_CACHE_CONTROL, AdminUser, Db
from app.models.shema_sensitive_countries import SensitiveCountryList, SensitiveCountryListWrite
from app.services.shema import list_sensitive_countries, save_sensitive_countries

router = APIRouter()


@router.get("/sensitive-countries", response_model=SensitiveCountryList)
async def read_sensitive_countries(
    admin: AdminUser, db: Db, response: Response
) -> SensitiveCountryList:
    """Every listed country, ordered by name, with the other spellings a place may use."""
    response.headers["Cache-Control"] = PER_READER_CACHE_CONTROL
    return await list_sensitive_countries(db)


@router.put("/sensitive-countries", response_model=SensitiveCountryList)
async def put_sensitive_countries(
    payload: SensitiveCountryListWrite, admin: AdminUser, db: Db
) -> SensitiveCountryList:
    """Replace the list; the next write of every project reads it, and no stored one moves."""
    return await save_sensitive_countries(db, payload, actor=admin, app_key=APP_KEY)
