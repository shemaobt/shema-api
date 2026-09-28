from collections.abc import Collection, Mapping
from datetime import datetime
from typing import Literal, NamedTuple

from sqlalchemy import ColumnElement, and_, false, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.auth import App, Role, UserAppRole
from app.utils.stored_time import as_utc


class GrantEvent(NamedTuple):
    """One grant or one revocation of one role, as ``user_app_roles`` recorded it."""

    action: Literal["granted", "revoked"]
    at: datetime
    app_key: str
    role_key: str
    user_id: str
    #: Who acted. ``None`` when nobody did (an automatic grant), when the account was since
    #: deleted (the column is ``SET NULL``), or for a revocation written before
    #: ``revoke_role`` recorded its author.
    actor_id: str | None
    #: The grant's own id, so two events at the same instant order the same way every time.
    grant_id: str


async def list_grant_history(
    db: AsyncSession, roles: Mapping[str, Collection[str]], *, limit: int
) -> list[GrantEvent]:
    """The newest ``limit`` grants and revocations of the ``(app, role)`` pairs in ``roles``.

    ``user_app_roles`` already is the history: a grant is a row with ``granted_by`` and
    ``granted_at``, and a revocation stamps ``revoked_by`` and ``revoked_at`` on it rather
    than deleting it. So every door that writes a role — ``assign_role``, the form's own,
    an access-request approval, an accepted invite — is in here without having to remember
    to be. It lives in the auth spine for ``list_role_holders``' reason: a module asks the
    spine about ``user_app_roles`` and does not query it (``docs/shema.md`` §2.4), which is
    also why the pairs are a parameter rather than a vocabulary imported from a module.

    Two reads, one per kind, each cut at ``limit`` before they are merged, which is enough
    for the merged top ``limit`` to be exact. The moments go through ``as_utc`` before they
    are compared: SQLite reads a stored moment back naive, and a revocation stamped by
    Python is aware. Ties — PostgreSQL stamps every row of one transaction with the same
    ``now()`` — break on the action and the grant's id.
    """
    pairs = [
        and_(App.app_key == app_key, Role.role_key.in_(list(role_keys)))
        for app_key, role_keys in roles.items()
        if role_keys
    ]
    if not pairs or limit <= 0:
        return []
    within: ColumnElement[bool] = or_(false(), *pairs)

    base = (
        select(UserAppRole, App.app_key, Role.role_key)
        .join(Role, and_(Role.id == UserAppRole.role_id, Role.app_id == UserAppRole.app_id))
        .join(App, App.id == Role.app_id)
        .where(within)
    )
    granted = await db.execute(
        base.order_by(UserAppRole.granted_at.desc(), UserAppRole.id.desc()).limit(limit)
    )
    revoked = await db.execute(
        base.where(UserAppRole.revoked_at.is_not(None))
        .order_by(UserAppRole.revoked_at.desc(), UserAppRole.id.desc())
        .limit(limit)
    )

    events = [
        GrantEvent(
            "granted",
            as_utc(row.granted_at),
            app_key,
            role_key,
            row.user_id,
            row.granted_by,
            row.id,
        )
        for row, app_key, role_key in granted.all()
    ]
    events += [
        GrantEvent(
            "revoked",
            as_utc(row.revoked_at),
            app_key,
            role_key,
            row.user_id,
            row.revoked_by,
            row.id,
        )
        for row, app_key, role_key in revoked.all()
        if row.revoked_at is not None
    ]
    events.sort(key=lambda event: (event.at, event.action, event.grant_id), reverse=True)
    return events[:limit]
