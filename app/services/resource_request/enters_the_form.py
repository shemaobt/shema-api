"""Who enters the form — written once, for the two doors that ask it (BE-19, OBT-520).

Since GATE-04 D1 (OBT-519) the answer has three halves: a **platform admin**, an account
holding a **grant** in this app, or a **live member of a PME project** — the team, which holds
``equipe`` through the membership and no longer through a row in ``user_app_roles``
(``_membership.py``; ``20260928_rr08`` revoked those rows).

Two doors ask it, and before this file each would have kept its own copy:

* **the app's door**, ``_deps._app_member``, asked on every request of this app;
* **the handoff**, ``app/services/auth/create_handoff.py``, asked once when the PME mints the
  code that opens the form (OBT-538, OBT-544). Written as *a grant in the app*, it refused the
  very member the door admits — every account BE-19 moved into the PME — and the PME → form
  flow could not start.

**What the two doors do not share is how fresh the grants are**, and ``cached`` is that
difference, named by the caller. The door reads them through the role cache (``auth_cache``,
ENG-551), the trade every platform gate makes for a question asked on every request. The
handoff reads them live, because minting a credential is a write that matters and a grant
revoked half a minute ago must not mint one — the distinction ``holds_capability`` draws in
``docs/resource_requests.md`` §5.5. Taking the grants as an argument instead was the
alternative, and it would have put the half of the rule that decides *read how* in each
caller, which is what this file exists to stop.

**The membership is asked only when the grants did not already answer** (PR #569, review): an
admin pays nothing, an account with a grant pays the grant read, and only an account with
neither pays the membership query.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_cache import get_cached_roles, set_cached_roles
from app.db.models.auth import User
from app.services import authorization_service
from app.services.resource_request._membership import is_member


async def _holds_a_grant(db: AsyncSession, user_id: str, app_key: str, *, cached: bool) -> bool:
    """Whether ``user_id`` holds any live role in ``app_key`` — through the cache or not."""
    if not cached:
        return bool(await authorization_service.list_roles(db, user_id, app_key))
    roles = get_cached_roles(user_id, app_key)
    if roles is None:
        roles = await authorization_service.list_roles(db, user_id, app_key)
        set_cached_roles(user_id, app_key, roles)
    return bool(roles)


async def enters_the_form(db: AsyncSession, user: User, app_key: str, *, cached: bool) -> bool:
    """Whether ``user`` may enter the form: an admin, a grant here, or a live membership."""
    if user.is_platform_admin:
        return True
    if await _holds_a_grant(db, user.id, app_key, cached=cached):
        return True
    return await is_member(db, user.id)
