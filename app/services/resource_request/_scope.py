"""Which requests a caller reaches — the axis capabilities were never built to answer.

``edit_requests`` belongs to all three roles (GATE-02 D4), so the capability says *may edit a
request* and says nothing about **which** ones — neither which it reaches, decided here, nor
which it writes, which is the instance's pen since BE-25 (``_editing.py``, OBT-534).
The frontend's table has no scope column and should not grow one: adding
``read_all_requests`` would put a row the client never saw into contract §5.3, which is a
client artefact.

So this is the one place in the module that reads a **role** rather than a capability, and
it reads it for a scope rather than for a permission. Two narrow reaches are decided here;
everything else reaches everything:

* a caller who is only ``equipe`` reaches the requests it authored **and every request of
  the projects it is a live member of**, drafts included — GATE-04 D1 and D2 (OBT-519),
  built by BE-19 (OBT-520). Who may *edit* one of those is the instance's question
  (OBT-534), never the scope's;
* **the base leader reaches nothing here**, and that is BE-23 (OBT-535): since the 22/set
  meeting the leader has no account and reads the one request a link was mailed for, through
  the link's own public door (``read_endorsement``), never through this scope. BE-16's middle
  reach — every submitted request, no draft — left with the account it was built for, and
  ``20260930_rr12`` revokes every live ``lider`` grant, so the subtraction below never meets one.

**The wide rule subtracts rather than tests for membership, and that is the whole of it.**
An account carries a row per grant, ``user_app_roles`` has no constraint on ``(user_id,
app_id)``, and since ``20260828_rr02`` turned ``auto_approve`` on every account that
registers is already ``equipe`` — so a mesa member is ``equipe`` **plus** ``mesa``, and
that is the ordinary account rather than an exotic one. ``granted - {TEAM_ROLE}``
asks whether anything besides the narrow reach is held, which stays
true for that account. Asked the other way round, as ``TEAM_ROLE in granted``, it would
answer *team* for exactly the mesa member it was written to serve and hide the board from
them. ``holds_capability`` reads the same union for
capabilities, with the grant rules that stand beside it.

A platform admin reaches everything, as they pass every other guard in this module
unconditionally (``require_capability`` in ``_deps.py`` says the same, with the reason).
"""

from typing import NamedTuple

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.auth import User
from app.services.resource_request._membership import TEAM_ROLE, granted_roles


async def _granted_roles(db: AsyncSession, user: User, app_key: str) -> set[str]:
    """The grants alone. ``reach`` never needs the membership that holds ``equipe``: *every*
    subtracts it, so asking would be a query whose answer changes nothing (PR #569, review).
    What a member reaches of their projects is the listing's and the read's own clause, not a
    role."""
    return await granted_roles(db, user.id, app_key)


class Reach(NamedTuple):
    """How far a caller reaches.

    A value and not a bare bool so a second narrow reach, if one is ever decided, lands as a
    field its callers must read rather than a meaning squeezed into the first. BE-16's
    *submitted* reach was one, and it left with the base leader's account (BE-23, OBT-535).
    """

    #: The whole board's worth of requests — the mesa, the Gestor, the platform admin.
    every: bool


async def reach(db: AsyncSession, user: User, app_key: str) -> Reach:
    """The caller's reach, from one read of their roles.

    A platform admin short-circuits before the query, as they pass every other guard in
    this module.
    """
    if user.is_platform_admin:
        return Reach(every=True)

    granted = await _granted_roles(db, user, app_key)
    return Reach(every=bool(granted - {TEAM_ROLE}))
