"""``PUT /api/shema/sensitive-countries`` — the Admin replaces the list, whole (OBT-616).

**Whole, because the screen edits it whole**: a list of nineteen countries is read, changed and
sent back as one act, the way the org chart states its three seats together. The body is the list
as it is to stand, and anything left out is off it.

**What changes with it, and what does not.** From the next write on, a place that names a country
on the list raises the project's flag (``_redaction.flag_by_country``). No stored project moves —
Daniel, 19/out/2026, *não há migração nem checagem retroativa* — and taking a country off the list
lowers nobody: the rule only raises.

**The Admin's standing is read fresh** (``_grant_rules.require_admin_in``), as every write of the
access surface reads it: the guard answers from a cache up to thirty seconds old, and an Admin
revoked a moment ago does not get to rewrite what decides which places are withheld.

**A save that changes nothing writes nothing**, the record's own rule (``save_project``'s fourth
step): no row moves and no mark is left. A save that does change it leaves one mark in
``shema_change_log`` — who and when, under ``sensitive_countries`` — with **no subject id and no
keys**: that log is read by the coordination of every region for an act that belongs to none, and
which countries the Admin added or took off is the list itself, which is the Admin's.

**Two Admins saving at the same moment get a 409, not a 500.** The replace deletes every row and
inserts the new ones; a second replace whose delete ran before the first committed inserts names
the first has just written, and the primary key refuses them. ``_instance.py``'s answer to the same
race on a unique index: roll back, and say the list moved.
"""

from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError
from app.db.models.auth import User
from app.db.models.shema_change_log import ChangeAction, ChangeSubject
from app.models.shema_sensitive_countries import SensitiveCountryList, SensitiveCountryListWrite
from app.services.shema import _trail
from app.services.shema._grant_rules import require_admin_in
from app.services.shema._sensitive_list import (
    ListedCountry,
    listed_countries,
    replace_sensitive_countries,
)
from app.services.shema.list_sensitive_countries import list_sensitive_countries

#: Two replaces landing together: the second inserts a name the first has just written.
SAVED_MEANWHILE = "The list was saved by somebody else at the same moment; read it again and save."


async def save_sensitive_countries(
    db: AsyncSession, payload: SensitiveCountryListWrite, *, actor: User, app_key: str
) -> SensitiveCountryList:
    """Replace the list with ``payload`` and answer it as it now stands."""
    await require_admin_in(db, actor, (app_key,))
    wanted = sorted(
        ListedCountry(country.name, tuple(country.spellings)) for country in payload.countries
    )
    if wanted != sorted(await listed_countries(db)):
        try:
            await replace_sensitive_countries(db, wanted)
        except IntegrityError:
            await db.rollback()
            raise ConflictError(SAVED_MEANWHILE) from None
        _trail.stage(
            db,
            actor=actor,
            subject=ChangeSubject.SENSITIVE_COUNTRIES,
            action=ChangeAction.REPLACED,
        )
        await db.commit()
    return await list_sensitive_countries(db)
