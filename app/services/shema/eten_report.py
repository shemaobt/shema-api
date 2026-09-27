"""The ETEN report for one fiscal year — computed, explained, and recorded as it was answered.

``GET /api/shema/eten/report?year=`` lands here. Three reads, one pure rule, one write:

1. **the projects listed in ETEN inside the caller's scope** — ``visible_projects`` with
   ``in_eten``, so a regional reader's report is their region's and nothing else's;
2. **their whole progress history and this year's manual ledger rows**, keyed on ids that came
   out of the scoped read, so neither can reach a project the caller cannot;
3. ``account_for`` (``app/utils/shema_derivations.py``) per project — the rule GATE-01 closed —
   and the lines, totals and order computed **from the redacted lines**, never from the rows;
4. **the report is recorded** in ``shema_eten_reports`` unless the newest recorded report for the
   same year and scope says exactly the same thing.

**Why a read writes.** The issue asks that reports *snapshot the data they were computed from*:
*a report run in March and re-run in June will differ as data changes, and both may be correct —
but only if it is recorded which data produced which figure.* The July report is the one sent to
ETEN, and whether it is on record cannot depend on somebody remembering to save it — so every
report answered is recorded, deduplicated by a digest of its content, append-only. It is an
audit of what the server said rather than a change the caller asked for; the two alternatives
were an evidence-only response (nothing recorded, so the July figures are gone the day the data
moves) and a separate *freeze* endpoint outside FE-44 §9.8 that no screen would call.

**The whole history and not only up to the cut**, because the rule asks one question past it: a
completion stamped in a later year is checked against the readings at the start of that year.

**This file names no guarded column.** The sensitive-country rule is applied by validating the
row into :class:`~app.models.shema_eten.EtenYearSnapshot`, a ``LeavingShape``; the totals read the
lines that came out of it, which is how an aggregate cannot count a place the line beside it
withholds — and a withheld project still counts, because a funder total that dropped it would be
wrong. The recorded content carries the region and never the country.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.auth import User
from app.db.models.shema import ShemaProject
from app.db.models.shema_enums import ShemaEtenCreditSource
from app.db.models.shema_eten import ShemaEtenCredit, ShemaEtenReport
from app.db.models.shema_progress import ShemaProgressEntry
from app.models.shema_eten import (
    EtenManualEntry,
    EtenReading,
    EtenYearReport,
    EtenYearSnapshot,
)
from app.services.shema._audit import author_name
from app.services.shema._scope import RegionScope, visible_projects
from app.utils.shema_derivations import (
    CreditSubject,
    ProgressPoint,
    account_for,
    fiscal_year_end,
    fiscal_year_start,
)
from app.utils.shema_facets import collation_key


async def _history(db: AsyncSession, ids: list[str]) -> dict[str, list[ProgressPoint]]:
    """Every progress entry of every project in ``ids``, oldest first per project.

    Ordered by ``created_at`` under ``entry_date``, the order ``read_record`` reads the trail
    in: two entries on one day come back in the order they were written, and *the newest entry
    up to the cut* has to mean one entry.
    """
    if not ids:
        return {}
    stmt = (
        select(ShemaProgressEntry)
        .where(ShemaProgressEntry.project_id.in_(ids))
        .order_by(
            ShemaProgressEntry.project_id,
            ShemaProgressEntry.entry_date,
            ShemaProgressEntry.created_at,
        )
    )
    grouped: dict[str, list[ProgressPoint]] = defaultdict(list)
    for entry in (await db.execute(stmt)).scalars():
        grouped[entry.project_id].append(
            ProgressPoint(
                id=entry.id,
                entry_date=entry.entry_date,
                approved_units=entry.approved_units,
                total_units=entry.total_units,
                previous_approved=entry.previous_approved,
                initial=entry.initial,
            )
        )
    return grouped


async def _manual(db: AsyncSession, ids: list[str], year: int) -> dict[str, ShemaEtenCredit]:
    """This year's manual ledger rows for ``ids`` — the overrides, one per project at most."""
    if not ids:
        return {}
    stmt = select(ShemaEtenCredit).where(
        ShemaEtenCredit.project_id.in_(ids),
        ShemaEtenCredit.year == year,
        ShemaEtenCredit.source == ShemaEtenCreditSource.MANUAL,
    )
    return {row.project_id: row for row in (await db.execute(stmt)).scalars()}


def _line(
    project: ShemaProject,
    history: list[ProgressPoint],
    manual: ShemaEtenCredit | None,
    year: int,
    today: date,
) -> EtenYearSnapshot:
    """One project's line: the row through the boundary, then its account attached."""
    account = account_for(
        CreditSubject(
            status=project.status,
            total_units=project.total_units,
            approved_units=project.approved_units,
            approved_units_unverified=project.approved_units_unverified,
            completed_date=project.completed_date,
        ),
        history,
        year,
        manual_credits=None if manual is None or manual.credits is None else manual.credits,
        today=today,
    )
    entry = (
        None
        if manual is None or manual.credits is None
        else EtenManualEntry(
            credits=manual.credits,
            recorded_by=manual.recorded_by_name,
            recorded_at=manual.updated_at,
        )
    )
    return EtenYearSnapshot.model_validate(project).model_copy(
        update={
            "scope_units": account.scope_units,
            "approved_at_start": account.approved_at_start,
            "approved_at_end": account.approved_at_end,
            "advanced": account.advanced,
            "concluded": account.concluded,
            "completed_in_year": account.completed_in_year,
            "undated_completion": account.undated_completion,
            "has_data": account.has_data,
            "credits": account.credits,
            "credits_source": account.credits_source,
            "start_reading": EtenReading.of(account.start_reading),
            "end_reading": EtenReading.of(account.end_reading),
            "completion_source": account.completion_source,
            "approved_unverified": account.approved_unverified,
            "manual_entry": entry,
        }
    )


def _order(line: EtenYearSnapshot) -> tuple[int, int, tuple[str, str], str]:
    """``buildEtenReport``'s order: credits down (no figure last), advance down, then the name.

    The name is compared by the Projetos screen's own ``collation_key``
    (``app/utils/shema_facets.py``), which carries why a code-point sort is wrong for these names.
    The id last keeps the order total, which the recorded digest depends on.
    """
    credits = -1 if line.credits is None else line.credits
    return (-credits, -line.advanced, collation_key(line.language_name), line.project_id)


def _scope_key(scope: RegionScope) -> str:
    """``global``, or the regions as ``RegionScope.wire`` already orders them."""
    regions = scope.wire
    return "global" if regions is None else ",".join(regions)


def _content(report: EtenYearReport) -> dict[str, Any]:
    """What is recorded: the report as its shape dumps it, minus three deliberate omissions.

    Built off the model rather than off a second list of keys, so a field added to
    :class:`~app.models.shema_eten.EtenYearReport` reaches the record — and the digest — on its
    own. What stays out is named: ``asOf`` and the report's own id and time are metadata of the
    answer, not of its figures, and the lines are dumped by ``recorded()``, which puts the region
    where the country would be.
    """
    content = report.model_dump(
        mode="json", by_alias=True, exclude={"as_of", "report_id", "recorded_at", "snapshots"}
    )
    content["snapshots"] = [line.recorded() for line in report.snapshots]
    return content


def _digest(content: dict[str, Any]) -> str:
    canonical = json.dumps(content, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


async def _record(
    db: AsyncSession,
    report: EtenYearReport,
    *,
    scope: RegionScope,
    user: User,
) -> ShemaEtenReport:
    """The recorded report this answer is — the newest one when nothing changed, else a new one.

    Compared against the **newest** row for the year and scope only, so a report that went A,
    then B, then A again is recorded three times: the third answer is not the first one.
    """
    content = _content(report)
    digest = _digest(content)
    scope_key = _scope_key(scope)
    newest = (
        await db.execute(
            select(ShemaEtenReport)
            .where(ShemaEtenReport.year == report.year, ShemaEtenReport.scope_key == scope_key)
            .order_by(ShemaEtenReport.created_at.desc(), ShemaEtenReport.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if newest is not None and newest.digest == digest:
        return newest

    row = ShemaEtenReport(
        year=report.year,
        scope_key=scope_key,
        as_of=report.as_of,
        digest=digest,
        content=content,
        computed_by=user.id,
        computed_by_name=author_name(user),
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def eten_report(
    db: AsyncSession,
    scope: RegionScope,
    year: int,
    *,
    user: User,
    today: date,
) -> EtenYearReport:
    """The fiscal year ``year`` — 1 August of ``year - 1`` to 31 July of ``year`` — recorded.

    ``scope`` is positional and has no default, for ``list_projects``'s stated reason. ``today``
    is injected: it decides only which year is still open, which is where the rule reads the
    record as it stands instead of a history entry.

    **An empty report is an honest one.** With nothing listed, or nothing read, the answer says
    so — ``listedProjects`` zero, ``hasData`` false — and nothing is invented to fill it.
    """
    stmt = visible_projects(scope).where(ShemaProject.in_eten.is_(True)).order_by(ShemaProject.id)
    projects = list((await db.execute(stmt)).scalars())
    ids = [project.id for project in projects]
    history = await _history(db, ids)
    ledger = await _manual(db, ids, year)

    lines = sorted(
        (
            _line(project, history.get(project.id, []), ledger.get(project.id), year, today)
            for project in projects
        ),
        key=_order,
    )
    report = EtenYearReport(
        year=year,
        listed_projects=len(lines),
        advancing_projects=sum(1 for line in lines if line.advanced > 0),
        total_credits=sum(line.credits or 0 for line in lines),
        has_data=any(line.has_data or line.credits is not None for line in lines),
        snapshots=lines,
        period_start=fiscal_year_start(year),
        period_end=fiscal_year_end(year),
        as_of=today,
    )
    recorded = await _record(db, report, scope=scope, user=user)
    return report.model_copy(update={"report_id": recorded.id, "recorded_at": recorded.created_at})
