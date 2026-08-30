"""Which requests a caller reaches — the axis capabilities were never built to answer.

``edit_requests`` belongs to all three roles (GATE-02 D4: the mesa may edit what the team
wrote), so the capability says *may edit a request* and says nothing about **which** ones.
The frontend's table has no scope column and should not grow one: adding
``read_all_requests`` would put a row the client never saw into contract §5.3, which is a
client artefact.

So this is the one place in the module that reads a **role** rather than a capability, and
it reads it for a scope rather than for a permission. Two narrow reaches are decided here;
everything else reaches everything:

* a caller who is only ``equipe`` reaches the requests it authored;
* the **Líder de Base reaches every submitted request and no draft** — decided by BE-16
  (OBT-476, 30/aug/2026), not inherited. He reads to endorse, and what he endorses is a
  submitted, frozen document: a draft is the team's work still moving, and an endorsement
  of a moving document would vouch for whatever it becomes. His own drafts stay reachable
  through the ``equipe`` floor every account carries. The subtraction below deliberately
  errs wide for a *fifth* role nobody has scoped yet — reaching too much gets noticed and
  decided, the way this role was; inheriting the team's narrow view silently would not.

**"His base" has no representation in this system, and that is recorded rather than
implied.** The endorsement, in the client's own words, is the Líder confirming *"que o
projeto realmente pertence à base dele"* — the attestation is his, not the system's.
Nothing in the form's 45 questions names a base (they stay 45; adding one is the client's
call, not ours), ``rr_requests`` carries no organization column, and the platform's
``organizations`` tables are another product's aggregates this module has never read —
wiring one to the other would invent a membership model the client has never seen, to
verify a fact the client asked the Líder to attest. So every Líder reaches every
submitted request, and which base's leader vouched for which request is exactly what his
signature records: ``endorsed_by`` is a person, not a guess. The day the client wants
bases in the system, that is a form question and a granting process (BE-17), never a
silent scope patch here.

**The wide rule subtracts rather than tests for membership, and that is the whole of it.**
An account carries a row per grant, ``user_app_roles`` has no constraint on ``(user_id,
app_id)``, and since ``20260828_rr02`` turned ``auto_approve`` on every account that
registers is already ``equipe`` — so a mesa member is ``equipe`` **plus** ``mesa``, and
that is the ordinary account rather than an exotic one. ``granted - {TEAM_ROLE,
LEADER_ROLE}`` asks whether anything besides the two narrow reaches is held, which stays
true for that account. Asked the other way round, as ``TEAM_ROLE in granted``, it would
answer *team* for exactly the mesa member it was written to serve and hide the board from
them. A Líder who is also mesa reaches everything by the same subtraction, and the wide
answer is right for the same reason. ``holds_capability`` reads the same union for
capabilities, with the grant rules that stand beside it.

A platform admin reaches everything, as they pass every other guard in this module
unconditionally (``require_capability`` in ``_deps.py`` says the same, with the reason).
"""

from typing import NamedTuple

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.auth import User
from app.services import authorization_service

TEAM_ROLE = "equipe"
LEADER_ROLE = "lider"


async def _granted_roles(db: AsyncSession, user: User, app_key: str) -> set[str]:
    return {
        role_key
        for _app_key, role_key in await authorization_service.list_roles(db, user.id, app_key)
    }


class Reach(NamedTuple):
    """How far a caller reaches, as the two answers the scope actually has.

    **One value and not two functions**, because the two answers come from one fact — the
    set of roles the account holds — and asking them separately meant reading that set
    twice. ``_granted_roles`` does not memoise (``holds_capability`` says why it reads the
    database on every call, and the cache the tests clear is ``require_app_access``'s), so
    a caller that took both answers ran the same three-table join twice per request. That
    is the ordinary team account since ``20260828_rr02`` turned ``auto_approve`` on:
    everyone is ``equipe``, so ``every`` is false for every team member and the second
    question was always asked. Read once, answered twice (PR #281, review).
    """

    #: The whole board's worth of requests — the mesa, the Gestor, the platform admin.
    every: bool
    #: The Líder's middle reach: every submitted request, no draft of another team.
    submitted: bool


async def reach(db: AsyncSession, user: User, app_key: str) -> Reach:
    """The caller's reach, from one read of their roles.

    A platform admin short-circuits before the query, as they pass every other guard in
    this module — and both answers are true for them, though only ``every`` is ever read:
    a reach that contains everything contains the submitted half of it.
    """
    if user.is_platform_admin:
        return Reach(every=True, submitted=True)

    granted = await _granted_roles(db, user, app_key)
    return Reach(
        every=bool(granted - {TEAM_ROLE, LEADER_ROLE}),
        submitted=LEADER_ROLE in granted,
    )
