"""The manual ETEN ledger — ``GET /api/shema/eten/credits``, scoped like every read.

**Only manual rows exist to list.** BE-11 never writes a calculated credit into
``shema_eten_credits`` (``app/db/models/shema_eten.py`` says why: a calculated figure belongs
beside the readings it came from, in the recorded report), so this is the list of overrides —
which is also what the console already reads it as.

A row of a project outside the caller's scope is absent, not refused: the ledger is joined to
``shema_projects`` under ``within_scope``, the same predicate every read of the module carries.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.shema import ShemaProject
from app.db.models.shema_enums import ShemaEtenCreditSource
from app.db.models.shema_eten import ShemaEtenCredit
from app.models.shema_eten import EtenCreditEntry
from app.services.shema._scope import RegionScope, within_scope


def credit_entry(row: ShemaEtenCredit) -> EtenCreditEntry:
    """One ledger row on the wire: the contract's four keys, and who set it and when.

    Built field by field rather than validated off the row: the row's ``recorded_by`` is the
    account id, and the wire's ``recordedBy`` is the name as it was then.
    """
    return EtenCreditEntry(
        project_id=row.project_id,
        year=row.year,
        credits=row.credits or 0,
        source=row.source,
        recorded_by=row.recorded_by_name,
        recorded_at=row.updated_at,
    )


async def list_eten_credits(db: AsyncSession, scope: RegionScope) -> list[EtenCreditEntry]:
    """Every manual figure on a project the caller reaches, newest year first."""
    stmt = (
        select(ShemaEtenCredit)
        .join(ShemaProject, ShemaProject.id == ShemaEtenCredit.project_id)
        .where(within_scope(scope), ShemaEtenCredit.source == ShemaEtenCreditSource.MANUAL)
        .order_by(ShemaEtenCredit.year.desc(), ShemaEtenCredit.project_id)
    )
    return [credit_entry(row) for row in (await db.execute(stmt)).scalars()]
