"""What the Admin's request links share: who may issue them, and what state one is in (BE-26).

**The Admin is one role in two apps** (OBT-522, seeded by ``scripts/seed_apps_roles.py`` in both
``shema`` and ``resource-request-form``): the PME's dialog (OBT-544) issues links for an account
that holds ``admin`` there, and this module's own screens for one that holds it here. So either
grant passes, and so does the platform admin — the reading BE-24's project cards already make.
Nobody else issues, lists or revokes, the mesa and the Gestor included.

**A link's state is the token module's**, read by ``tokens.status`` over the one row — ``revoked``
before ``expired`` before *used* — with ``verified_at`` as its *used*: a request link is
multi-use, so verifying it is its first use and not its end, which is exactly why *expired* is
read before it (BE-20).
"""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthorizationError
from app.db.models.auth import User
from app.db.models.resource_request import RRRequestLink
from app.models.resource_request import LinkStatus
from app.services.common import tokens
from app.services.resource_request._membership import granted_roles
from app.services.shema._scope import ADMIN_ROLE


@dataclass
class _LinkState:
    expires_at: datetime
    used_at: datetime | None
    revoked_at: datetime | None


def link_status(link: RRRequestLink, now: datetime) -> LinkStatus:
    state = tokens.status(
        _LinkState(
            expires_at=link.expires_at, used_at=link.verified_at, revoked_at=link.revoked_at
        ),
        now,
    )
    return "verified" if state == "used" else state


async def require_link_admin(
    db: AsyncSession, user: User, app_key: str, shema_app_key: str
) -> None:
    """Refuse anyone but the Admin — the platform admin, or ``admin`` in either app."""
    if user.is_platform_admin:
        return
    if ADMIN_ROLE in await granted_roles(db, user.id, app_key):
        return
    if ADMIN_ROLE in await granted_roles(db, user.id, shema_app_key):
        return
    raise AuthorizationError("Only the Admin issues, lists and revokes request links.")
