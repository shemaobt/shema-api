"""``/api/shema/eten`` — the ETEN report and its manual ledger, FE-44 §9.8's three routes.

Each handler declares its dependencies, calls one service and returns what it answers: no query,
no filter, no role check of its own. The caller's reach arrives as a ``RegionScope`` from
``_deps.py`` and is handed straight down (``docs/shema.md`` §6.2); who may set a manual figure is
``app/services/shema/record_eten_credit.py``'s question, asked in the service so the rule travels
with the operation rather than with this file.

**The report is not a coordination surface.** Its line is a ``LeavingShape`` and
``tests/test_shema/test_privacy_owners.py`` audits all three routes with no exemption: an ETEN
report is a document that leaves the system, withheld for every reader.

**The day is the UTC day**, BE-05's choice for a read, and the cost is stated rather than hidden:
between 21:00 and midnight on 31 July in UTC-3 the year that is closing is already treated as
closed. The day decides only whether the rule may read a record as it stands for the open year,
which a record born in the product almost never needs — every change it has had wrote a history
entry — and which a migrated record's copied count never gets.

**``GET /eten/report`` answers FE-44 §9.8's form, the one in force.** ETEN's own format changes
every year and this year's had not arrived on 28/sep/2026; when it does, it is a presenter in
``app/models/shema_eten.py`` — served, if the server is the one that writes ETEN's file, by a
route of its own here beside this one — and the console's contract does not change under it.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Path, Query

from app.api.shema._deps import APP_KEY, CurrentUser, Db, Scope
from app.models.shema_eten import (
    FIRST_REPORT_YEAR,
    LAST_REPORT_YEAR,
    EtenCreditEntry,
    EtenCreditWrite,
    EtenYearReport,
)
from app.services.shema import eten_report, list_eten_credits, record_eten_credit

router = APIRouter()

#: The fiscal year — the one that **ends** on 31 July of this number.
FiscalYear = Annotated[int, Query(ge=FIRST_REPORT_YEAR, le=LAST_REPORT_YEAR)]


@router.get("/eten/report", response_model=EtenYearReport)
async def read_eten_report(
    year: FiscalYear, db: Db, scope: Scope, user: CurrentUser
) -> EtenYearReport:
    """One fiscal year's credits, with the working behind each line — recorded as answered.

    ``year`` is required: a report defaulted to a year nobody chose is a figure nobody asked for.
    """
    return await eten_report(db, scope, year, user=user, today=datetime.now(UTC).date())


@router.get("/eten/credits", response_model=list[EtenCreditEntry])
async def read_eten_credits(db: Db, scope: Scope) -> list[EtenCreditEntry]:
    """The manual figures on the projects the caller reaches."""
    return await list_eten_credits(db, scope)


@router.put("/eten/credits/{project_id}/{year}", response_model=EtenCreditEntry)
async def put_eten_credit(
    project_id: str,
    year: Annotated[int, Path(ge=FIRST_REPORT_YEAR, le=LAST_REPORT_YEAR)],
    payload: EtenCreditWrite,
    db: Db,
    scope: Scope,
    user: CurrentUser,
) -> EtenCreditEntry:
    """Set one project's manual figure for one fiscal year — ``source: "manual"``."""
    return await record_eten_credit(
        db, scope, project_id, year, payload.credits, user=user, app_key=APP_KEY
    )
