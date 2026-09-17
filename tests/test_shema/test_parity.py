"""The acceptance replay — ``docs/shema.md`` §6.5's *igual, não equivalente*.

``dataJsParity.json`` beside this file is ``src/utils/__tests__/dataJsParity.json`` of
``shemaobt/project-management-ecosystem``, copied byte for byte at :data:`VENDORED_FROM`. It is
the output of FE-44 §7's nine derivations over all 127 export records at ``2026-05-14``, and
§7 says what that makes it: **a server that computes them differently is wrong, not
different.** BE-05 vendors it; every later issue that implements a derivation extends the
replay rather than writing a second artifact.

``shemaProjectsExport.json`` is the input half, ``src/fixtures/data/projects.json`` of the same
commit, also byte for byte. A golden file without its input is a file nobody can re-run: the
numbers in it become a second statement of the rule instead of a check on the first. Both are
**data and are never edited here** — a hand-fixed value is exactly the second source this test
exists to prevent, and re-vendoring is a copy from over there, not a patch.

**This file adapts the export; it does not import it.** :class:`ExportRecord` reads the eleven
keys the nine derivations touch and nothing else. BE-16 owns the real import — the ``DD/MM/YYYY``
dates, the free-text ``sensitivity`` becoming a boolean, ``[0, 0]`` becoming *no coordinate* —
and a second mapping written here to seed a test would be the second owner of an interpretation
whose whole value is being auditable in one place.

**The one place the server and the artifact legitimately disagree, pinned rather than
tolerated.** The artifact was produced over the **raw** export, where ``startDate`` is
``13/04/2024`` and the frontend's ``new Date("13/04/2024T00:00:00")`` is ``Invalid Date`` — so
``daysSinceUpdate`` is ``NaN`` on the eight dated records and ``getStaleStatus`` answers
``em-dia`` for them, because ``NaN >= 120`` is false and so is ``NaN >= 60``. A server that
stores a real ``date`` column cannot reproduce a parse failure and must not try. The frontend's
own ``parity.test.ts`` records the same divergence from the other side, asserts it is exactly
those eight records, and asserts nothing else moves — and so does this file.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from app.db.models.shema_enums import ShemaHealthLevel, ShemaProjectStatus
from app.utils.shema_derivations import derive, get_region

HERE = Path(__file__).parent

#: The commit of ``shemaobt/project-management-ecosystem`` both files were copied from.
#: Without it, a copy older than the contract is invisible instead of reviewable — the
#: sibling's ``EMITTED_FROM`` makes the same check for the same reason.
VENDORED_FROM = "d4fa47c7df4786770430cb76616620b65f285c0b"

PARITY: dict[str, Any] = json.loads((HERE / "dataJsParity.json").read_text(encoding="utf-8"))
EXPORT: list[dict[str, Any]] = json.loads(
    (HERE / "shemaProjectsExport.json").read_text(encoding="utf-8")
)

REFERENCE_DATE = date.fromisoformat(PARITY["referenceDate"])

#: The eight records the export dated as ``DD/MM/YYYY``. They are the whole of the divergence
#: above, listed rather than computed so that a ninth one appearing is a failure and not a
#: silently wider allowance.
DATED_BY_THE_EXPORT = frozenset(
    {
        "mixteco-de-magdalena-penasco",
        "mixteco-de-san-esteban-atatlahuca",
        "popoluca",
        "purepecha-angahuan",
        "purepecha-de-capacuaro",
        "tenek-huasteco",
        "zapoteco-de-santiago-lachirigi",
        "zoque-de-francisco-leon",
    }
)

#: The one of the eight whose start date is **after** the reference day. Named because it is
#: the record that makes ``days_since_update`` negative, and a reviewer who has not seen it
#: reads a negative day count as a bug.
NOT_STARTED_YET = "tenek-huasteco"


def _parse_export_date(value: str) -> date | None:
    """``DD/MM/YYYY`` as the server would store it, or ``None`` for the export's empty string.

    Day first, which is the only reading that makes the export's own dates real: ``13/04/2024``
    has no thirteenth month. This is a **test** adapter and not BE-16's importer — see the
    module docstring.
    """
    if not value:
        return None
    day, month, year = (int(part) for part in value.split("/"))
    return date(year, month, day)


@dataclass(frozen=True)
class ExportRecord:
    """One export row, reduced to what the nine derivations read.

    Satisfies :class:`~app.utils.shema_derivations.Derivable` structurally, which is the point
    of that protocol being structural: the replay does not need a database, a session or a
    response model to check a pure function.
    """

    status: ShemaProjectStatus | None
    total_units: int
    translated_units: int
    health_emotional: ShemaHealthLevel | None
    health_relational: ShemaHealthLevel | None
    health_spiritual: ShemaHealthLevel | None
    health_physical: ShemaHealthLevel | None
    start_date: date | None
    last_progress_date: date | None
    last_updated: date | None
    deadline: date | None


def _rating(value: str | None) -> ShemaHealthLevel | None:
    """``""`` is *not assessed* and is NULL here — never ``boa`` (FE-44 §7.4)."""
    return ShemaHealthLevel(value) if value else None


def _status(value: str | None) -> ShemaProjectStatus | None:
    """A stored status outside the eight-member vocabulary reads as nothing stored."""
    try:
        return ShemaProjectStatus(value) if value else None
    except ValueError:
        return None


def _record(row: dict[str, Any]) -> ExportRecord:
    history = row.get("progressHistory") or []
    return ExportRecord(
        status=_status(row.get("status")),
        total_units=int(row.get("totalUnits") or 0),
        translated_units=int(row.get("translatedUnits") or 0),
        health_emotional=_rating(row.get("healthEmotional")),
        health_relational=_rating(row.get("healthRelational")),
        health_spiritual=_rating(row.get("healthSpiritual")),
        health_physical=_rating(row.get("healthPhysical")),
        start_date=_parse_export_date(row.get("startDate") or ""),
        last_progress_date=_parse_export_date(history[-1]["date"]) if history else None,
        last_updated=_parse_export_date(row.get("lastUpdated") or ""),
        deadline=_parse_export_date(row.get("deadline") or ""),
    )


def _derived(row: dict[str, Any]) -> dict[str, Any]:
    """The nine, as this server computes them, keyed the way the artifact keys them."""
    derivations = derive(_record(row), REFERENCE_DATE, region=get_region(row.get("location") or ""))
    return {
        "id": row["id"],
        "status": derivations.status.value,
        "health": derivations.health.value,
        "stale": derivations.stale.value if derivations.stale else None,
        "progress": derivations.progress,
        "priority": derivations.priority.value,
        "healthScore": derivations.health_score,
        "daysSinceUpdate": derivations.days_since_update,
        "lastProgressUpdate": (
            derivations.last_progress_update.isoformat()
            if derivations.last_progress_update
            else None
        ),
        "region": derivations.region.value,
    }


GOLDEN: dict[str, dict[str, Any]] = {row["id"]: row for row in PARITY["projects"]}
COMPUTED: dict[str, dict[str, Any]] = {row["id"]: _derived(row) for row in EXPORT}


def test_the_vendored_pair_says_where_it_came_from_and_covers_the_whole_export() -> None:
    """Both halves, same commit, same 127 records — the check that the copy is a copy."""
    assert len(VENDORED_FROM) == 40 and not VENDORED_FROM.endswith("-dirty")
    assert len(EXPORT) == 127
    assert len(PARITY["projects"]) == len(EXPORT)
    assert GOLDEN.keys() == COMPUTED.keys()


@pytest.mark.parametrize("field", ["status", "health", "progress", "healthScore", "region"])
def test_the_date_free_derivations_reproduce_the_artifact_exactly(field: str) -> None:
    """Five of the nine, over all 127 records, with no allowance at all.

    Parametrised per field rather than compared as whole rows so that a failure says *which*
    derivation moved. A single dict comparison over 127 records reports one enormous diff and
    sends the reader to find the first difference by eye.
    """
    assert {i: row[field] for i, row in COMPUTED.items()} == {
        i: row[field] for i, row in GOLDEN.items()
    }


@pytest.mark.parametrize("field", ["stale", "daysSinceUpdate", "lastProgressUpdate", "priority"])
def test_nothing_but_the_eight_dated_records_moves(field: str) -> None:
    """The other four — the three that read a date and the one that composes them.

    ``priority`` is here and not above on purpose: it reads staleness, so it is allowed to
    move exactly where staleness moves and nowhere else. Bounding it by the same eight ids is
    what proves the divergence propagates no further than the parse failure it comes from.
    """
    moved = {i for i, row in COMPUTED.items() if row[field] != GOLDEN[i][field]}
    assert moved <= DATED_BY_THE_EXPORT


def test_the_dated_records_become_real_days_without_news() -> None:
    """What the server gains by storing a date: a parse failure becomes a measurement.

    Over there all eight are ``em-dia`` with ``NaN`` days — because ``NaN >= 120`` is false and
    so is ``NaN >= 60``, which puts the projects most out of contact on the screen as the
    healthiest. Here they are dated and measured, and seven of them are years past the
    120-day line.
    """
    for project_id in DATED_BY_THE_EXPORT:
        assert GOLDEN[project_id]["daysSinceUpdate"] == "NaN"
        assert GOLDEN[project_id]["stale"] == "em-dia"
        assert isinstance(COMPUTED[project_id]["daysSinceUpdate"], int)

    silent = {i for i in DATED_BY_THE_EXPORT if COMPUTED[i]["stale"] == "critico"}
    assert silent == DATED_BY_THE_EXPORT - {NOT_STARTED_YET}


def test_the_one_record_dated_after_the_reference_day_is_not_silent() -> None:
    """A negative day count is a project that has not started, and it is not *sem notícias*.

    ``tenek-huasteco`` starts on 2026-06-16, thirty-three days after the reference date. It is
    the case a clamp to zero would erase and a ``max(0, …)`` would make indistinguishable from
    a project that reported today — so the number is negative and the band is ``em-dia``, which
    is the honest answer to *how long since we heard anything* for something that has not
    begun. It is also the only one of the eight the artifact and this server agree about, and
    they agree for opposite reasons.
    """
    assert COMPUTED[NOT_STARTED_YET]["daysSinceUpdate"] == -33
    assert COMPUTED[NOT_STARTED_YET]["stale"] == GOLDEN[NOT_STARTED_YET]["stale"] == "em-dia"
    assert COMPUTED[NOT_STARTED_YET]["priority"] == GOLDEN[NOT_STARTED_YET]["priority"]


def test_the_region_counts_are_the_ones_the_contract_publishes() -> None:
    """FE-44 §7.6's own numbers, as a second check on the country map.

    The per-field comparison above already covers ``region``, and this covers the **map**: a
    typo in one of the 25 country strings moves a handful of records to ``other`` and the two
    files would still agree if the artifact had been regenerated with the typo in place. These
    six numbers are written in the contract's prose, by a human, from the data.
    """
    counts: dict[str, int] = {}
    for row in COMPUTED.values():
        counts[row["region"]] = counts.get(row["region"], 0) + 1
    assert counts == {
        "oceania": 36,
        "asia": 31,
        "south-america": 29,
        "africa": 17,
        "north-america": 12,
        "other": 2,
    }
    assert "europe" not in counts
