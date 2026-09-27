"""A manual ETEN credit — ``PUT /api/shema/eten/credits/{projectId}/{year}``.

**The manual figure wins over the calculated one** (FE-44 §5.6), and it is the valve GATE-01
left for what the rule cannot date: a project concluded before ``completed_date`` was stamped
earns ``null`` until somebody states its year here. Because it overrides a funder-facing number,
two things travel with it: **who may set it**, and **who did**.

**Who may: the coordination** — :data:`ETEN_LEDGER_AUDIENCE`, and a platform admin, as they pass
every guard in this repository. GATE-04's answer (OBT-486, 23/sep) names the coordination as
``globalStrategist`` and ``coordinator`` in their own region; ``obtLab`` and ``resourceCircle``
(the Intercessor seat, FE-44 §5.3) do not set funding figures. That is this issue's reading and
not a client answer, so it is one tuple, declared in the pull request. The refusal is a 403 and
comes **before** the project is looked at, so it says nothing about any project; a project outside
the caller's region is then refused as missing (``_scope.py``), indistinguishably.

**Who did** is stamped on the row — the account and the name as it was then. The row is
overwritten by the next write for the same project and year; the value a report used before that
is kept by the report (``shema_eten_reports``), which is where *what was reported* lives.
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthorizationError
from app.db.models.auth import User
from app.db.models.shema_enums import ShemaEtenCreditSource
from app.db.models.shema_eten import ShemaEtenCredit
from app.models.shema_eten import EtenCreditEntry
from app.services.shema._audit import author_name
from app.services.shema._scope import COORDINATOR_ROLE, GLOBAL_ROLE, RegionScope, granted_roles
from app.services.shema.get_project import get_project
from app.services.shema.list_eten_credits import credit_entry

logger = logging.getLogger(__name__)

#: The roles that may set a manual ETEN figure. Read the module docstring before widening it.
ETEN_LEDGER_AUDIENCE: tuple[str, ...] = (GLOBAL_ROLE, COORDINATOR_ROLE)


async def _require_ledger_audience(db: AsyncSession, user: User, app_key: str) -> None:
    """Refuse an account outside :data:`ETEN_LEDGER_AUDIENCE`, and say so in the log.

    Read fresh rather than from the request's cached grant, ``_health_audience.py``'s trade: a
    rule that decides what a funder is told reads the grant as it stands.
    """
    if user.is_platform_admin:
        return
    if await granted_roles(db, user.id, app_key) & set(ETEN_LEDGER_AUDIENCE):
        return
    logger.warning(
        "shema authorization refused: outside the ETEN ledger audience",
        extra={
            "shema_operation": "record_eten_credit",
            "shema_user_id": user.id,
            "shema_audience": list(ETEN_LEDGER_AUDIENCE),
        },
    )
    raise AuthorizationError(
        "A manual ETEN credit is set by the coordination; this account holds neither "
        "globalStrategist nor coordinator in Shemá"
    )


async def record_eten_credit(
    db: AsyncSession,
    scope: RegionScope,
    project_id: str,
    year: int,
    credits: int,
    *,
    user: User,
    app_key: str,
) -> EtenCreditEntry:
    """Set the manual figure for one project and fiscal year, or refuse to.

    An upsert on ``(project, year, manual)`` — the ledger's unique key keeps the calculated half
    of the pair free, though nothing writes it. ``scope`` is positional and has no default.
    """
    await _require_ledger_audience(db, user, app_key)
    project = await get_project(db, scope, project_id, user=user, operation="record_eten_credit")

    row = (
        await db.execute(
            select(ShemaEtenCredit).where(
                ShemaEtenCredit.project_id == project.id,
                ShemaEtenCredit.year == year,
                ShemaEtenCredit.source == ShemaEtenCreditSource.MANUAL,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        row = ShemaEtenCredit(project_id=project.id, year=year, source=ShemaEtenCreditSource.MANUAL)
        db.add(row)

    row.credits = credits
    row.recorded_by = user.id
    row.recorded_by_name = author_name(user)
    await db.commit()
    await db.refresh(row)
    return credit_entry(row)
