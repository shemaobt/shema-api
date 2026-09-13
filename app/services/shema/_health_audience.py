"""Who may read a team's health assessment, and who is told when one turns critical.

**One list, two uses, and that is the decision this file is.** *Who may read an assessment* and
*who is told about one* are the same question asked from two ends: a notice that reaches
somebody who may not open the assessment has leaked the fact it exists, and a reader who may
open it and is not told has to go looking. Keeping the two as two lists is how they drift, so
there is one — :data:`HEALTH_AUDIENCE` — and the functions below are the read gate and the
recipient list read off it.

**Why the read is narrower than the record's, which is the issue's own fourth line.** The
record admits any holder of any Shemá role; an assessment is an OBT Lab mentor's reading of how
four people are actually doing, and FE-44 §5.8's audience table already answers who it is for:
*field, health, need and stale reach ``coordinator`` and ``obtLab``; prayer reaches
``resourceCircle`` alone*. So ``resourceCircle`` — the role that handles needs, materials and
the prayer chain — is **not** in the audience, and the narrowing is deliberate rather than
inherited: the Resource Circle does not need to know that a team is in emotional difficulty in
order to send them a recorder.

``globalStrategist`` **is** in the audience, and that is this file's one departure from FE-44's
table. It is the unscoped seat — the role with no region and no org-chart row — and reading the
table literally would make the one person who sees every region the only person not told that a
team went critical. The table is about the three regional roles and the global seat is outside
its frame rather than excluded by it; the pull request declares the reading.

**The region is the other half and it is not relaxed.** A recipient reaches a project exactly
when ``_scope.py`` says they do, so a coordinator scoped to Africa is not told about Asia. The
two axes compose the way they compose everywhere else in this module: the role says *what kind
of question you may be asked*, the region says *about which projects*.

**A platform admin reads.** They pass every other guard in this repository and refusing here
would make one route stricter than the route beside it while buying nothing. It does **not**
put them on the recipient list: :func:`recipients` is read off actual grants, so an admin is
notified when they hold one of the three roles and not otherwise. An administrative capability
is not a pastoral responsibility, and a notice addressed to whoever holds the platform's keys is
a notice nobody owns.
"""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthorizationError
from app.db.models.auth import User
from app.db.models.shema_enums import ShemaRegionKey
from app.services import authorization_service
from app.services.shema._scope import (
    COORDINATOR_ROLE,
    GLOBAL_ROLE,
    OBT_LAB_ROLE,
    granted_roles,
    reaches,
    scopes_for,
)

logger = logging.getLogger(__name__)

#: The roles an assessment reaches. Read the module docstring before widening it.
HEALTH_AUDIENCE: tuple[str, ...] = (GLOBAL_ROLE, COORDINATOR_ROLE, OBT_LAB_ROLE)


async def reads_assessments(db: AsyncSession, user: User, app_key: str) -> bool:
    """Whether this account may read a health assessment at all — the role half, alone.

    The region half is the scope every query in this module already takes, so composing them
    here would be a second place the project filter is applied; this answers the question the
    scope cannot.
    """
    if user.is_platform_admin:
        return True
    return bool(await granted_roles(db, user.id, app_key) & set(HEALTH_AUDIENCE))


async def require_reads_assessments(db: AsyncSession, user: User, app_key: str) -> None:
    """Refuse an account outside :data:`HEALTH_AUDIENCE`, and say so in the log.

    **A 403 and not the 404 the scope answers**, and the difference is what each one conceals.
    ``_scope.py``'s ``NotFoundError`` hides *whether this project exists*, which is the fact a
    sensitive record needs hidden. Here the project is not the subject: the caller is being told
    about their own grant, which they already hold, so there is no oracle in the answer and
    *not found* would be a worse message for no privacy. It is the same split
    ``create_project`` draws one file over.

    A service function and not a router condition, for ``docs/shema.md`` §6.6's reason: the rule
    then holds for the next caller, and the next caller is BE-15's panel.
    """
    if await reads_assessments(db, user, app_key):
        return
    logger.warning(
        "shema authorization refused: outside the health assessment audience",
        extra={
            "shema_operation": "health_assessment",
            "shema_user_id": user.id,
            "shema_audience": list(HEALTH_AUDIENCE),
        },
    )
    raise AuthorizationError(
        "A health assessment reaches the coordination and the OBT Lab; this account holds "
        "neither role in Shemá"
    )


async def recipients(
    db: AsyncSession, *, app_key: str, region: ShemaRegionKey, exclude: str | None = None
) -> list[User]:
    """The accounts to notify about one project's assessment — audience, then region.

    Read through ``authorization_service.list_role_holders``, which is the auth spine answering
    *who holds this role*: ``docs/shema.md`` §2.4 forbids this module from touching
    ``user_app_roles`` itself, and that function exists because addressing a notification was
    the first thing in this repository to need the join from that end. Inactive and revoked
    accounts are already excluded there.

    **The region is applied per holder and not in the query**, because the second axis is this
    module's own table: each holder's reach is resolved by ``_scope.py``, which is the same value
    their own requests are scoped by. A regional role with no row in ``shema_user_regions``
    reaches nothing and is therefore told nothing — the fail-closed floor that file states,
    arriving here unchanged rather than relaxed for the convenience of a fuller recipient list.

    **Three queries and not two per holder**, which is the difference between a constant and an
    ``n`` on a write a mentor is sitting in front of: the holders, the ids among them whose role
    is unscoped, and ``_scope.py``'s one read of the region table for the whole list. The sibling
    ``board_watchers`` has the same shape for the same reason — read the holders once and filter
    in Python, never go back per person.

    ``exclude`` drops one account **before** the reach is resolved, which is how the mentor who
    filed the assessment is not told about their own act and also why they cost nothing to skip —
    the sibling's ``board_watchers`` does the first half for the same reason.
    """
    holders = [
        holder
        for holder in await authorization_service.list_role_holders(db, app_key, HEALTH_AUDIENCE)
        if holder.id != exclude
    ]
    if not holders:
        return []
    unscoped = await authorization_service.list_role_holders(db, app_key, (GLOBAL_ROLE,))
    scopes = await scopes_for(db, holders, unscoped={holder.id for holder in unscoped})
    return [holder for holder in holders if reaches(scopes[holder.id], region)]
