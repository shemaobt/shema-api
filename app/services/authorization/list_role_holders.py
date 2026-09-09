from collections.abc import Collection

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.auth import App, Role, User, UserAppRole


async def list_role_holders(
    db: AsyncSession, app_key: str, role_keys: Collection[str]
) -> list[User]:
    """The active accounts holding any of ``role_keys`` in ``app_key``.

    ``list_roles`` asks this same join from the other end — *which roles does this account
    hold* — and every guard in the platform asks it that way, because a guard is answering
    about the caller. Addressing a notification is the first thing in this repository that
    needs the reverse direction, and it belongs here rather than in the module that wants
    it: ``docs/resource_requests.md`` §2.2 says a module service that reached for
    ``user_app_roles`` itself would have reimplemented ``require_role`` badly. The auth
    spine owns those tables; a module asks it a question.

    Revoked grants are excluded, as in ``list_roles``. Inactive accounts are excluded too,
    which is this function's own rule rather than that one's: a guard must answer about a
    role whatever the account's state, while delivery to somebody who cannot sign in has
    nowhere to land.

    An account holding two of the named roles appears **once** — the caller is addressing
    people, not grants. Ordered by e-mail so a recipient list is stable between calls,
    which is what lets a test assert one.
    """
    if not role_keys:
        return []

    stmt = (
        select(User)
        .join(UserAppRole, UserAppRole.user_id == User.id)
        .join(
            Role,
            and_(Role.id == UserAppRole.role_id, Role.app_id == UserAppRole.app_id),
        )
        .join(App, App.id == Role.app_id)
        .where(
            App.app_key == app_key,
            Role.role_key.in_(list(role_keys)),
            UserAppRole.revoked_at.is_(None),
            User.is_active.is_(True),
        )
        .distinct()
        .order_by(User.email)
    )
    return list((await db.execute(stmt)).scalars().all())
