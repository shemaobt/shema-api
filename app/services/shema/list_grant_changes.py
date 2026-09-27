"""``GET /access/changes`` — who granted or revoked what, to whom, and when.

Two sources, one history. **Roles** come from ``user_app_roles`` through the auth spine
(``list_grant_history``): a grant is a row with its author and date and a revocation stamps
its own on the same row, so every door that writes a role is in here — this surface, the
form's ``/access`` until OBT-549, an approved access request, an accepted invite (whose grant
is the inviter's). **Regions** come from ``shema_scope_changes``, which ``set_region_scope``
writes on every change, because moving a coordinator between regions writes no role row at
all. Only the roles this surface writes are read: the ``equipe`` the form hands to everybody
who registers is not somebody's decision.

**What the history cannot say, stated where it is read.** An account deleted takes its role
rows with it (``user_app_roles`` cascades), while its region rows stay under an id with no
name; an author deleted is anonymised (``SET NULL``). ``admin`` reads twice, once per app, as
it is written. Nothing before OBT-543 is in the region half, and the newest
:data:`DEFAULT_LIMIT` entries are all one read returns.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, NamedTuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.auth import User
from app.db.models.shema_grant import ShemaScopeChange
from app.models.shema_grant import GrantChange
from app.services.authorization.list_grant_history import list_grant_history
from app.services.shema._grant_rules import GrantApps, grantable_roles
from app.utils.stored_time import as_utc

#: How many entries one read returns — the org chart trail's figure, for its reason: the
#: history grows forever and the screen shows the recent part of it.
DEFAULT_LIMIT = 200


class _Entry(NamedTuple):
    at: datetime
    action: Literal["granted", "revoked"]
    ref: str
    app_key: str
    role_key: str | None
    region_key: str | None
    user_id: str
    actor_id: str | None


async def list_grant_changes(
    db: AsyncSession, apps: GrantApps, *, limit: int = DEFAULT_LIMIT
) -> list[GrantChange]:
    """The newest ``limit`` role and region changes of the two apps, newest first."""
    entries = [
        _Entry(
            event.at,
            event.action,
            event.grant_id,
            event.app_key,
            event.role_key,
            None,
            event.user_id,
            event.actor_id,
        )
        for event in await list_grant_history(db, grantable_roles(apps), limit=limit)
    ]
    scope_rows = await db.execute(
        select(ShemaScopeChange)
        .order_by(ShemaScopeChange.changed_at.desc(), ShemaScopeChange.id.desc())
        .limit(limit)
    )
    entries += [
        _Entry(
            as_utc(row.changed_at),
            "granted" if row.granted else "revoked",
            row.id,
            apps.shema,
            None,
            row.region_key.value,
            row.user_id,
            row.changed_by,
        )
        for row in scope_rows.scalars()
    ]
    entries.sort(key=lambda entry: (entry.at, entry.action, entry.ref), reverse=True)
    entries = entries[:limit]

    ids = {entry.user_id for entry in entries} | {e.actor_id for e in entries if e.actor_id}
    people: dict[str, tuple[str, str | None]] = {}
    if ids:
        rows = await db.execute(
            select(User.id, User.email, User.display_name).where(User.id.in_(sorted(ids)))
        )
        people = {user_id: (email, name) for user_id, email, name in rows.all()}

    return [
        GrantChange(
            action=entry.action,
            at=entry.at,
            appKey=entry.app_key,
            roleKey=entry.role_key,
            regionKey=entry.region_key,
            userId=entry.user_id,
            userEmail=people.get(entry.user_id, (None, None))[0],
            userName=people.get(entry.user_id, (None, None))[1],
            actorId=entry.actor_id,
            actorEmail=people[entry.actor_id][0] if entry.actor_id in people else None,
            actorName=people[entry.actor_id][1] if entry.actor_id in people else None,
        )
        for entry in entries
    ]
