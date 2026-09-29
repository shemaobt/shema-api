"""Being a member of a PME project is what makes an account the team — GATE-04 D1 (OBT-519).

Until BE-19 (OBT-520) the team was a role of this app, ``equipe``, granted to whoever
registered (``auto_approve``, GATE-02 D1). The access model of 22 and 25/sep/2026 (OBT-522)
moved the team to the PME: a team is **the members of a project**
(``shema_project_members``, OBT-524), and every ``equipe`` grant of this app is revoked by
the migration ``20260928_rr08`` — the role row stays, because it is a key of the capability
table, and only an Admin's review of an access request
hands it out again (``_default_roles.py``).

So ``equipe`` stays a key of the capability table — the frontend's ``capabilities.ts`` and
``capabilities.json`` do not move — and stops being a row in ``user_app_roles``. **A live
membership is what holds it.** This is the PME's own reading, not a new one: its session
answers ``EQUIPE_ROLE`` from ``holds_membership`` (``app/services/shema/_scope.py``), and
this module reads the same fact through the same function rather than keeping a second
statement of *who is a member*.

So the answer to *which of this app's roles does the account hold* is the grants, plus
``equipe`` when a live membership exists — and **the membership is asked only when the grants
did not already answer** (PR #569, review): the door asks it only for an account with no
grant, the capabilities only when no granted role carries the one asked for, and the scope's
two answers (``_scope.reach``) never need it at all. Every reader asks ``is_member`` here, so
none of them keeps a second statement of *who is a member*.
"""

from __future__ import annotations

from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.shema_project_member import ShemaProjectMember
from app.services import authorization_service

#: The team's key in the capability table — held through a membership, never granted.
TEAM_ROLE = "equipe"


async def granted_roles(db: AsyncSession, user_id: str, app_key: str) -> set[str]:
    """The roles ``user_id`` was **granted** in ``app_key`` — ``user_app_roles``, read live."""
    granted = await authorization_service.list_roles(db, user_id, app_key)
    return {role_key for _app_key, role_key in granted}


async def is_member(db: AsyncSession, user_id: str) -> bool:
    """Whether ``user_id`` is a live member of any PME project — what holds ``equipe`` here.

    ``holds_membership`` is imported here and not at the top: ``app.services.shema._scope``
    reaches the access services, which reach ``holds_capability``, which reaches this module —
    a cycle at import time only. Importing it where it is called keeps the PME's function the
    one statement of *who is a member*, rather than a copy written to dodge the cycle.
    """
    from app.services.shema._scope import holds_membership

    return await holds_membership(db, user_id)


def member_project_ids(user_id: str) -> Select[tuple[str]]:
    """The ids of the projects ``user_id`` is a live member of, as a subquery to filter by.

    The PME's ``live_membership_ids``, imported late for ``is_member``'s reason, so *live* is
    written once — in ``app/services/shema/_scope.py``, beside ``holds_membership``.
    """
    from app.services.shema._scope import live_membership_ids

    return live_membership_ids(user_id)


async def is_member_of(db: AsyncSession, user_id: str, project_id: str) -> bool:
    """Whether ``user_id`` is a live member of ``project_id`` — the check a creation stands on."""
    found = await db.execute(
        member_project_ids(user_id).where(ShemaProjectMember.project_id == project_id).limit(1)
    )
    return found.scalar_one_or_none() is not None
