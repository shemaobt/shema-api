"""What ``/api/shema/eten`` answers and accepts — FE-44 §5.6 and §9.8, plus the working.

The frozen shapes are the console's ``src/types/eten.ts``: ``EtenYearReport``
``{year, listedProjects, advancingProjects, totalCredits, hasData, snapshots[]}``, the per-project
``EtenYearSnapshot`` and the ledger's ``EtenCreditEntry``. Every key the contract names is here
under the contract's spelling. **What is added is evidence, and only evidence**, because the issue
sets a standard the frozen shape alone cannot meet: *when someone from ETEN asks why a project
counted, the answer must be derivable from stored data.* So a row also says which history entry
each reading came from and on what day, what decided the year, whether the approved count still
came from the export, and who set a manual figure; and the report says which fiscal period it
covers, the day it was computed for and which recorded report it is. A consumer that reads only
the contract's keys reads exactly what it read before.

**Nothing here marks a figure provisional.** GATE-01 closed on 25/sep/2026, and the flag the
issue once asked for — *ship the endpoint marked explicitly provisional* — was the answer to a
gate that did not close.

**The row leaves coordination, and the redaction travels in its shape.** ``EtenYearSnapshot``
inherits :class:`~app.models.shema_privacy.LeavingShape`: it is validated off the
``ShemaProject`` row, the boundary reduces ``location`` before anything else reads it, and
``country`` — FE-44's ``LocationDisplay``, not a string — is computed from what is left:
``{withheld: false, location: <the first country>}`` or ``{withheld: true, regionLabelKey}``. A
renderer downstream cannot leak what the row does not hold. The row declares no base and no
contact: GATE-04 (1.5) answered *idioma, região e progresso; sem a base* for this report. It is
an ``outside`` reader in OBT-528's words — withheld for every role, the region's own coordinator
included — because an ETEN report is a document that leaves the system. **The ``projectId``
travels on the line**, the export's ``<language>-<place>`` slug: the client allowed it on
28/sep/2026 (``docs/shema.md`` §9.4).

**The data, the form, and the record are three things, and this module owns where they part.**
The fields below are the *data* — every figure and the evidence behind it, filled by
``app/services/shema/eten_report.py`` from ``account_for``. The *form* is how they leave: today
FE-44 §9.8's, which is ``_OUTWARD``'s camelCase and ``country`` as a ``LocationDisplay``, and
nothing else. The *record* is :meth:`EtenYearReport.recorded`, the data by field name, which
reads no alias and no computed field. ETEN changes its own report's format every year, and the
client had not received this year's on 28/sep/2026 — so **a new ETEN format is a presenter in
this module**, a function from :class:`EtenYearReport` to the shape ETEN asks for — served,
if the server writes ETEN's file, by a route of its own beside ``GET /eten/report``. It reads
the lines as they already are, reduced.
The rule does not move and the record does not move: if the format asks for a fact the line
does not carry, that fact is a field here, filled in ``eten_report._line``, and it reaches the
record by itself.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Final, Literal

from pydantic import AliasChoices, AliasGenerator, BaseModel, ConfigDict, Field, computed_field
from pydantic.alias_generators import to_camel

from app.db.models.shema_enums import ShemaEtenCreditSource, ShemaRegionKey
from app.models.shema_privacy import UNKNOWN_REGION, LeavingShape
from app.utils.shema_derivations import (
    CompletionSource,
    ReadingSource,
    YearEndReading,
    get_country,
)

#: ``datetime.date`` under a second name, for the one shape below with a field literally called
#: ``date`` — FE-44's own key for an entry's day — as ``app/models/shema_record.py`` does.
Day = date

#: Read models speak camelCase outward and snake_case inward — BE-05's ``_OUTWARD``.
_OUTWARD = ConfigDict(
    from_attributes=True,
    populate_by_name=True,
    alias_generator=AliasGenerator(serialization_alias=to_camel),
)

#: The i18next key the console renders a region under — ``src/constants/regions.ts``'s
#: ``labelKey``, copied rather than re-derived, as ``REGION_CENTROIDS`` is. FE-44's Appendix A:
#: the server serves keys, never rendered labels.
REGION_LABEL_KEYS: Final[dict[ShemaRegionKey, str]] = {
    ShemaRegionKey.SOUTH_AMERICA: "continent_south_america",
    ShemaRegionKey.NORTH_AMERICA: "continent_north_america",
    ShemaRegionKey.AFRICA: "continent_africa",
    ShemaRegionKey.ASIA: "continent_asia",
    ShemaRegionKey.OCEANIA: "continent_oceania",
    ShemaRegionKey.EUROPE: "continent_europe",
    ShemaRegionKey.OTHER: "continent_other",
}

#: The fiscal years a report may be asked for. Bounds on a calendar value rather than a policy:
#: a year outside them is a typo, and ``date(year, 7, 31)`` must be constructible.
FIRST_REPORT_YEAR: Final = 2000
LAST_REPORT_YEAR: Final = 2100


class EtenLocationShown(BaseModel):
    """``LocationDisplay``'s open half: the first country the ``location`` names.

    Built **only** by :attr:`EtenYearSnapshot.country`, from a ``location`` the boundary has
    already reduced, which is why it is not a leaving shape of its own and why
    ``tests/test_shema/test_privacy_owners.py`` names it in the allowlist it keeps for exactly
    this case.
    """

    model_config = _OUTWARD

    withheld: Literal[False] = False
    location: str


class EtenLocationWithheld(BaseModel):
    """``LocationDisplay``'s withheld half: the region, as the key the console renders it by."""

    model_config = _OUTWARD

    withheld: Literal[True] = True
    region_label_key: str


class EtenReading(BaseModel):
    """Where a year-end reading came from: a history entry on a day, or the record as it stood.

    ``entryId`` names a ``shema_progress_history`` row, which is append-only, so the reference
    means the same thing for as long as it exists. A ``live`` reading has no entry and no day —
    it is the count when the report was computed, and :attr:`EtenYearReport.as_of` says when.
    """

    model_config = _OUTWARD

    source: ReadingSource
    approved_units: int
    total_units: int | None = None
    entry_id: str | None = None
    date: Day | None = None

    @classmethod
    def of(cls, reading: YearEndReading | None) -> EtenReading | None:
        if reading is None:
            return None
        return cls(
            source=reading.source,
            approved_units=reading.approved_units,
            total_units=reading.total_units,
            entry_id=reading.entry_id,
            date=reading.on,
        )


class EtenManualEntry(BaseModel):
    """The ledger row a manual figure came from — the figure, who set it and when."""

    model_config = _OUTWARD

    credits: int
    recorded_by: str
    recorded_at: datetime | None = None


class EtenYearSnapshot(LeavingShape):
    """One project's line of the report — FE-44's ``EtenYearSnapshot``, with its working.

    Validated off the ``ShemaProject`` row, which is what picks up ``sensitive_country`` and
    ``region_key`` and reduces :attr:`location` without the service naming either; the account
    is attached afterwards with ``model_copy``, BE-05's pattern for what a row cannot answer.
    """

    model_config = _OUTWARD

    project_id: str = Field(validation_alias=AliasChoices("id", "project_id"))
    language_name: str = ""
    #: Read off the row and reduced by the boundary; never emitted — :attr:`country` is its
    #: projection, so the shape carries the display and not the string it was made from.
    location: str = Field(default="", exclude=True)

    scope_units: int = 0
    approved_at_start: int = 0
    approved_at_end: int = 0
    advanced: int = 0
    concluded: bool = False
    completed_in_year: bool = False
    undated_completion: bool = False
    has_data: bool = False
    credits: int | None = None
    credits_source: ShemaEtenCreditSource | None = None

    start_reading: EtenReading | None = None
    end_reading: EtenReading | None = None
    #: The stamped completion date, when the record has one. ``save_project`` writes it on the
    #: move into ``concluido``, with the saver's own day.
    completed_date: date | None = None
    completion_source: CompletionSource = CompletionSource.SNAPSHOTS
    #: The record's approved count arrived from the export; readings before the first save that
    #: moved it are not counted (``shema_derivations.trusted_history``).
    approved_unverified: bool = False
    manual_entry: EtenManualEntry | None = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def country(self) -> EtenLocationShown | EtenLocationWithheld:
        """FE-44's ``LocationDisplay``, computed from what the boundary left.

        When the place is withheld the region is read from ``region_key`` rather than from
        :attr:`location`, which already holds only the region's key; when it is not, the first
        country is the console's ``getCountryDisplay``. Either way this reads nothing the
        payload does not already carry.
        """
        if self.location_withheld:
            region = self.region_key or UNKNOWN_REGION
            return EtenLocationWithheld(region_label_key=REGION_LABEL_KEYS[region])
        return EtenLocationShown(location=get_country(self.location))

    def recorded(self) -> dict[str, Any]:
        """This line as ``shema_eten_reports`` keeps it: everything but the place, by field name.

        The region and the withheld bit stand in for ``country``. A country copied into an
        append-only table is out of reach of a flag raised later — the boundary ``_audit.py``
        keeps for the trail — and it is not an input of the credit. By field name and not by
        alias, so the record does not follow the form (see the module docstring).
        """
        line = self.model_dump(mode="json", exclude={"country"})
        line["region"] = (self.region_key or UNKNOWN_REGION).value
        return line


class EtenYearReport(BaseModel):
    """FE-44's ``EtenYearReport`` for one fiscal year, and which recorded report it is.

    ``hasData`` is true when any line has a reading **or states a credit** (a manual figure, a
    stamped completion). The console's ``buildEtenReport`` reads readings only, and a year whose
    only facts are manual credits would then hide its own total behind *no data* — the one place
    this departs from it, declared in the pull request.
    """

    model_config = _OUTWARD

    year: int
    listed_projects: int
    advancing_projects: int
    total_credits: int
    has_data: bool
    snapshots: list[EtenYearSnapshot]

    #: 1 August of the year before and 31 July of ``year`` — the fiscal period, stated.
    period_start: date
    period_end: date
    #: The day the report was computed for; it decides only which year was still open.
    as_of: date
    #: The ``shema_eten_reports`` row holding this report's figures and their evidence.
    report_id: str | None = None
    recorded_at: datetime | None = None

    def recorded(self) -> dict[str, Any]:
        """What ``shema_eten_reports`` keeps of this report: its data, whatever form it left in.

        Dumped off the model rather than off a second list of keys, so a field added here
        reaches the record — and the digest — on its own. What stays out is named: ``as_of``
        and the report's own id and time are metadata of the answer, not of its figures, and
        each line is :meth:`EtenYearSnapshot.recorded`. A new ETEN format reshapes none of it.
        """
        report = self.model_dump(
            mode="json", exclude={"as_of", "report_id", "recorded_at", "snapshots"}
        )
        report["snapshots"] = [line.recorded() for line in self.snapshots]
        return report


class EtenCreditEntry(BaseModel):
    """FE-44's ``EtenCreditEntry`` — a ledger row — plus who set it and when."""

    model_config = _OUTWARD

    project_id: str
    year: int
    credits: int
    source: ShemaEtenCreditSource
    recorded_by: str = ""
    recorded_at: datetime | None = None


class EtenCreditWrite(BaseModel):
    """``PUT /eten/credits/{projectId}/{year}``'s body: ``{credits}``, a whole number of scopes.

    Not bounded above: the contract's ``credits`` is a number, and the manual entry is the valve
    for what the rule cannot express. Negative and fractional are refused.
    """

    model_config = ConfigDict(extra="forbid")

    credits: int = Field(ge=0, strict=True)
