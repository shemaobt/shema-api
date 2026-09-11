"""Import the 127 Notion projects into ``shema_projects`` — once, and fail-closed.

    uv run python -m scripts.import_shema_projects \\
        --export ../project-management-ecosystem/src/fixtures/data/projects.json \\
        --report ~/shema/import-report.md
    # ...read the report, then:
    uv run python -m scripts.import_shema_projects --export … --report … --apply

**This is real data about real people, and it is the moment errors become permanent.** A
project put in the wrong region is an annoyance; a project in a sensitive country loaded
without its flag is a disclosure nobody notices until it has already happened. Every
default below is chosen from that asymmetry.

**The source file never enters this repository.** It is the whole dataset and it names
sensitive-country projects, so it is read from a path given on the command line and nothing
of it is copied here. What survives the run is ``shema_projects.source`` — the export row as
it arrived, per record, in the database — which is also the answer to *keep the original
alongside the parsed value*: where a column is an interpretation (a ``DD/MM/YYYY`` string
became a ``date``, a free-text sensitivity became a boolean, two columns became one), the
uninterpreted row is still there to audit the interpretation against, without going back to
a file nobody can find.

**Dry-run is the default and ``--apply`` is the opt-in**, so *the first real run is preceded
by one that changes nothing* is a property of the program rather than a habit of whoever
runs it.

Four rules, each of which the export can and does violate somewhere:

**One — the sensitive-country flag comes from the client, never from the export.** The
issue's own words: *do not infer them from the CSV, from country names, or from anything in
the prototype; get the list from the client, in writing, and treat an unrecognised country
as sensitive until confirmed otherwise.* So the list is an argument
(:func:`SensitiveCountries.from_file`), the list is **empty until it arrives**, and an empty
list flags all 127. :class:`SensitiveCountries` is the whole of the rule and
:func:`_is_sensitive` is the whole of its application.

**Two — the export may raise that flag and may never lower it.** Two records carry
``sensitiveCountry: true`` and ``sensitivity: "Confidential"``, and one of them —
``zapoteco-de-santiago-lachirigi`` — is in **Mexico**, where seven other records are
``Unrestricted``. A list keyed by country cannot express that, and the day the client
confirms Mexico is a day this import would otherwise quietly unflag a record somebody
marked confidential. So the two compose, most restrictive wins, and the composition only
ever goes one way: a country verdict cannot clear a record the export marked. Rule one is
not weakened by this — nothing here *derives* the flag from the export, and the export is
never read as permission.

**Three — the only operation that can remove protection asks for itself by name.** Lowering
a flag needs ``--allow-lowering`` on top of ``--apply``. The normal second run — the one
that arrives with the client's list and corrects the 127 fail-closed placeholders — is
``--apply --allow-lowering`` after its dry-run has been read. Without the flag the lowerings
are reported and **not performed**, which is the state that cannot leak.

**Four — nothing is cleaned in silence.** A value this program cannot interpret stops the
run and is named (:class:`Refusal`); a value it can interpret but that is empty, ambiguous
or contradicted is imported under a rule stated out loud and listed in the report
(:class:`Finding`). Guessing quietly is what produces data that looks authoritative and is
not.

**The report is written outside this repository, and the program refuses to write it
inside.** It names projects in sensitive countries — that is the point of it, since the
human who checks the flags has to see which records carry them — so a path under the
working tree is refused rather than trusted to ``.gitignore``.

**Re-running reconciles the flag and the region, and touches nothing a person can type.**
This is a one-time migration, not a Notion synchroniser (the issue puts synchronisation out
of scope), so an existing record keeps every field a coordinator may have edited since. What
a second run does is re-apply the two values no human owns: ``sensitive_country``, because
the client's list is the authority and arrives after the first run, and ``region_key``,
which is a function of ``location`` and is re-derived only while ``location`` still holds
what was imported. A record whose ``source`` is NULL was born in the product and is not this
program's business at all.
"""

import argparse
import asyncio
import hashlib
import json
import sys
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal, engine
from app.db.models.shema import ShemaProject
from app.db.models.shema_enums import (
    ShemaHealthLevel,
    ShemaProjectStatus,
    ShemaRegionKey,
    ShemaYesNo,
)
from app.utils.shema_derivations import COUNTRY_REGION, countries_named, region_of

#: The 55 keys FE-44 §5.1 pins as *exactly the keys the Notion export has*. The file is
#: checked against this set rather than read key by key: a record missing one has been
#: edited on its way here, and a record carrying an extra one is carrying a field this
#: schema never decided what to do with. Either way the honest move is to stop.
EXPORT_KEYS: frozenset[str] = frozenset(
    {
        "id",
        "languageName",
        "languageCode",
        "bridgeLanguage",
        "vitalityStatus",
        "location",
        "speakerCount",
        "coords",
        "translationType",
        "financialResources",
        "team",
        "ywamBase",
        "teamLeader",
        "mentor",
        "translators",
        "technicalReviewers",
        "partnerOrg",
        "teamContact",
        "objective",
        "scopeDetails",
        "totalUnits",
        "totalUnitsType",
        "translatedUnits",
        "communityCheckedUnits",
        "approvedUnits",
        "startDate",
        "deadline",
        "status",
        "sensitivity",
        "sensitiveCountry",
        "statusComments",
        "statusGoal",
        "orgRole",
        "phases",
        "materials",
        "storyProgress",
        "bookProgress",
        "progressHistory",
        "healthEmotional",
        "healthRelational",
        "healthSpiritual",
        "healthAssessmentDate",
        "healthAssessor",
        "healthNotes",
        "prayerRequests",
        "needsPastoralIntervention",
        "pastoralInterventionName",
        "needsItems",
        "needsNotes",
        "notes",
        "inETEN",
        "regionalCoordinator",
        "obtLabPerson",
        "resourceCirclePerson",
        "lastUpdated",
    }
)

#: Export key → column, for the values that are stored exactly as they arrived. **Nothing
#: here is trimmed, cased or transliterated**: ``Embera Dobida`` carries a non-breaking
#: space, three language names legitimately begin lowercase, ``languageCode`` holds ``?``
#: and ``not iso language``, and ``notes`` round-trips unchanged in any script. A migration
#: that normalises one of these renames a language.
VERBATIM_TEXT: dict[str, str] = {
    "languageName": "language_name",
    "languageCode": "language_code",
    "bridgeLanguage": "bridge_language",
    "vitalityStatus": "vitality_status",
    "location": "location",
    "speakerCount": "speaker_count",
    "sensitivity": "sensitivity",
    "team": "team",
    "teamLeader": "team_leader",
    "mentor": "mentor",
    "translators": "translators",
    "technicalReviewers": "technical_reviewers",
    "partnerOrg": "partner_org",
    "teamContact": "team_contact",
    "scopeDetails": "scope_details",
    "totalUnitsType": "total_units_type",
    "statusComments": "status_comments",
    "statusGoal": "status_goal",
    "orgRole": "org_role",
    "healthAssessor": "health_assessor",
    "healthNotes": "health_notes",
    "prayerRequests": "prayer_requests",
    "pastoralInterventionName": "pastoral_intervention_name",
    "needsNotes": "needs_notes",
    "notes": "notes",
}

VERBATIM_INT: dict[str, str] = {
    "totalUnits": "total_units",
    "translatedUnits": "translated_units",
    "communityCheckedUnits": "community_checked_units",
    "approvedUnits": "approved_units",
}

#: The arrays that are columns rather than child tables, stored as the export wrote them.
VERBATIM_LIST: dict[str, str] = {
    "objective": "objective",
    "translationType": "translation_type",
    "financialResources": "financial_resources",
    "phases": "phases",
    "storyProgress": "story_progress",
    "bookProgress": "book_progress",
}

#: ``DD/MM/YYYY`` in, a real ``date`` column out — FE-44 §6.1's requirement, and the reason
#: is that a text column holding ``13/04/2024`` moves a parsing bug into the database, where
#: fixing it costs a migration instead of a function.
EXPORT_DATES: dict[str, str] = {
    "startDate": "start_date",
    "deadline": "deadline",
    "lastUpdated": "last_updated",
    "healthAssessmentDate": "health_assessment_date",
}

#: Empty on all 127 and nullable because *unassessed* is the dominant state, not an edge
#: case. ``""`` is not ``boa``: a default here reports every silent team as healthy, which
#: is the exact failure the product exists to prevent.
HEALTH_DIMENSIONS: dict[str, str] = {
    "healthEmotional": "health_emotional",
    "healthRelational": "health_relational",
    "healthSpiritual": "health_spiritual",
}

#: Aggregates with their own tables and no column on the record. They are empty on all 127,
#: which is why this import writes no child rows at all — and a non-empty one is data this
#: program would be dropping, so it refuses instead. BE-06…BE-13 own those tables.
OWN_TABLE_KEYS: tuple[str, ...] = ("materials", "needsItems", "progressHistory")

#: Dropped by ``docs/shema.md`` §6.2 and FE-44 §5.3: the region's three role-holders are read
#: from the org chart by reference and never copied onto a project. Empty on all 127 and they
#: stay empty — a value here is a second owner of a fact ``shema_region_teams`` owns, so a
#: non-empty one stops the run rather than being discarded quietly.
DROPPED_KEYS: tuple[str, ...] = ("regionalCoordinator", "obtLabPerson", "resourceCirclePerson")

#: Values of the export's free-text ``sensitivity`` column that assert *no restriction*.
#: Everything else in that column — including a value nobody here has seen — raises the flag.
#: The asymmetry is the point: an unknown word is a reason to be careful, never a permission.
NOT_A_RESTRICTION: frozenset[str] = frozenset({"", "Unrestricted"})

#: The two verdicts the client's file may carry per country. Spelled out rather than
#: ``true``/``false`` so a half-written or truncated file fails loudly instead of reading as
#: a country cleared for publication.
SENSITIVE = "sensitive"
NOT_SENSITIVE = "not-sensitive"


@dataclass(frozen=True)
class Finding:
    """Something the export said that a human should see, with what the import did about it.

    A finding never stops the run. It is the *report what was empty, what was ambiguous and
    what the migration decided* half of the issue: the value was interpretable, the rule
    that interpreted it is named, and the record it happened on is named too so the person
    who knows the data can disagree.
    """

    kind: str
    project_id: str
    detail: str


@dataclass(frozen=True)
class Refusal:
    """Something the export said that this program will not guess at, so the run stops.

    The distinction from :class:`Finding` is whether a rule exists. An empty ``objective``
    is covered by a rule; a ``status`` outside the eight is not, and inventing one would put
    a value in the database that looks decided and was not.
    """

    project_id: str
    detail: str


@dataclass(frozen=True)
class FlagDecision:
    """Why one record is or is not a sensitive-country record, in a shape a report can print.

    ``reasons`` is every country that raised the flag and how — confirmed by the client, or
    absent from a list that has not answered it yet — plus the export's own marker when it
    is the one raising. Empty ``reasons`` with ``sensitive`` false is the only combination
    that means *the client has cleared every country this record names*.
    """

    sensitive: bool
    reasons: tuple[str, ...]


class SensitiveCountries:
    """The client's written answer about which countries are sensitive, and nothing else.

    **Absence is the answer, not a gap.** A country the file does not name is *unrecognised*
    and therefore sensitive until the client confirms otherwise, so the empty instance —
    which is what this program uses until the list arrives — reports every country as
    sensitive and every one of the 127 records gets the flag. That is the state the issue
    asks for while the list is pending, and it is stated on stdout and in the report on
    every run so nobody mistakes it for a finished import.

    The file is JSON, lives outside this repository, and is shaped::

        {
          "confirmed_on": "2026-09-11",
          "confirmed_by": "who at the client signed this off",
          "countries": {"Brazil": "not-sensitive", "Egypt": "sensitive"}
        }

    The keys are the **export's own spellings** — ``São Tomé e Príncipe`` in Portuguese,
    ``East Timor`` in English — because that is what ``location`` holds and matching them is
    the whole job. A verdict this program does not recognise is refused rather than read as
    one of the two: a typo that silently meant *not sensitive* is the failure this whole
    file is arranged around.
    """

    def __init__(
        self,
        verdicts: dict[str, str],
        source: Path | None = None,
        confirmed_on: str = "",
        confirmed_by: str = "",
    ) -> None:
        self.verdicts = verdicts
        self.source = source
        self.confirmed_on = confirmed_on
        self.confirmed_by = confirmed_by

    @classmethod
    def pending(cls) -> "SensitiveCountries":
        """The list before the client has written it: empty, so everything is sensitive."""
        return cls({})

    @classmethod
    def from_file(cls, path: Path) -> "SensitiveCountries":
        payload = json.loads(path.read_text(encoding="utf-8"))
        countries = payload.get("countries")
        if not isinstance(countries, dict):
            raise SystemExit(
                f"{path}: expected an object under 'countries' mapping each country, spelled "
                f"as the export spells it, to {SENSITIVE!r} or {NOT_SENSITIVE!r}."
            )
        unknown = {
            country: verdict
            for country, verdict in countries.items()
            if verdict not in (SENSITIVE, NOT_SENSITIVE)
        }
        if unknown:
            raise SystemExit(
                f"{path}: {unknown} — a verdict must be {SENSITIVE!r} or {NOT_SENSITIVE!r}. "
                "Nothing is read as a default: a country whose answer cannot be read is not "
                "an answer, and guessing at one is how a sensitive country loses its flag."
            )
        return cls(
            verdicts=dict(countries),
            source=path,
            confirmed_on=str(payload.get("confirmed_on", "")),
            confirmed_by=str(payload.get("confirmed_by", "")),
        )

    @property
    def is_pending(self) -> bool:
        return not self.verdicts

    def verdict_for(self, country: str) -> str:
        """``sensitive`` for anything the client has not explicitly cleared."""
        return self.verdicts.get(country, SENSITIVE)

    def has_answered(self, country: str) -> bool:
        return country in self.verdicts


def to_export_date(value: str, project_id: str) -> tuple[date | None, Refusal | None]:
    """``DD/MM/YYYY`` → a real ``date``; ``""`` → NULL; anything else stops the run.

    ``src/fixtures/normalize.ts``'s ``toIsoDate`` is the reference implementation and this
    reproduces its reading — day first, one or two digits, a four-digit year, month 1-12 and
    day 1-31. It does **not** reproduce its fallback: the frontend passes an unrecognised
    string through unchanged because its field is a string, and a ``date`` column has
    nowhere to put one. The export is unambiguously day-first (FE-44 §6.1 measured it: of
    the 70 dates it carries, 60 have a first component above 12 and none has a second one
    above 12), so a value that does not parse is not a date in another order — it is
    something else, and this program says so instead of choosing.

    The final construction is ``date(...)``, which is what refuses ``31/02/2024``: the
    reference implementation's range checks accept it and produce an ISO string no calendar
    has.
    """
    if not value:
        return None, None
    parts = value.split("/")
    if len(parts) != 3 or not all(part.isdigit() for part in parts):
        return None, Refusal(project_id, f"date {value!r} is not the export's DD/MM/YYYY")
    day, month, year = (int(part) for part in parts)
    if len(parts[2]) != 4 or not 1 <= month <= 12 or not 1 <= day <= 31:
        return None, Refusal(project_id, f"date {value!r} is not the export's DD/MM/YYYY")
    try:
        return date(year, month, day), None
    except ValueError:
        return None, Refusal(project_id, f"date {value!r} is not a day on the calendar")


def _is_sensitive(
    row: dict[str, Any], location: str, countries: SensitiveCountries
) -> FlagDecision:
    """The whole of the sensitive-country rule, and the only place the flag is decided.

    Three inputs and one direction. Every country the ``location`` names is asked of the
    client's list, and **any** country that is sensitive or unanswered flags the record —
    ``China, Laos, Vietnam`` is one record and three questions, and the safe answer to three
    questions is the least safe of the three. A ``location`` that names nothing is a record
    whose country nobody has stated, which is the same thing as an unrecognised one.

    Then the export's own marker, which may raise and may never lower: ``sensitiveCountry``
    already true, or a ``sensitivity`` that is not one of the strings asserting *no
    restriction*. That is the ``zapoteco-de-santiago-lachirigi`` case in the module
    docstring — a confidential record in a country whose other seven records are not.

    ``location`` is passed in rather than read from ``row`` because a re-run asks about the
    record as it stands today: if a coordinator has corrected the country since the import,
    the flag follows the correction and not the export's memory of it.
    """
    reasons: list[str] = []
    named = countries_named(location)
    if not named:
        reasons.append("location names no country, so no country has been confirmed for it")
    for country in named:
        if countries.verdict_for(country) == SENSITIVE:
            why = (
                "confirmed sensitive by the client"
                if countries.has_answered(country)
                else "not on the client's list, so unrecognised and sensitive until confirmed"
            )
            reasons.append(f"{country}: {why}")
    if row.get("sensitiveCountry") is True:
        reasons.append("the export's own sensitiveCountry is true")
    sensitivity = str(row.get("sensitivity", ""))
    if sensitivity not in NOT_A_RESTRICTION:
        reasons.append(f"the export's sensitivity reads {sensitivity!r}")
    return FlagDecision(sensitive=bool(reasons), reasons=tuple(reasons))


@dataclass
class PlannedRecord:
    """One export row, read into the columns it becomes, before anything touches a session."""

    project_id: str
    values: dict[str, Any]
    source: dict[str, Any]
    flag: FlagDecision


@dataclass
class Plan:
    """What the export says, read without a database in hand.

    Splitting the reading from the writing is what lets the report be produced by a dry-run
    that opens no transaction, and what lets the tests drive the rules over a handful of
    synthetic rows instead of over a file that may not be committed anywhere.
    """

    records: list[PlannedRecord] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    refusals: list[Refusal] = field(default_factory=list)
    columns_empty_everywhere: tuple[str, ...] = ()
    countries_named_by_the_export: tuple[str, ...] = ()


def _column_limit(column: str) -> int | None:
    """The declared length of a ``String`` column, read off the model rather than retyped."""
    length = getattr(ShemaProject.__table__.columns[column].type, "length", None)
    return int(length) if length else None


def _read_row(row: dict[str, Any], countries: SensitiveCountries) -> PlannedRecord | list[Refusal]:
    """One export row into one set of column values, or the reasons it cannot be read."""
    project_id = str(row.get("id", ""))
    refusals: list[Refusal] = []
    values: dict[str, Any] = {"id": project_id}

    for key, column in VERBATIM_TEXT.items():
        text = row[key]
        if not isinstance(text, str):
            refusals.append(Refusal(project_id, f"{key} is {type(text).__name__}, not text"))
            continue
        limit = _column_limit(column)
        if limit is not None and len(text) > limit:
            refusals.append(
                Refusal(project_id, f"{key} is {len(text)} characters and {column} holds {limit}")
            )
            continue
        values[column] = text

    for key, column in VERBATIM_INT.items():
        number = row[key]
        if not isinstance(number, int) or isinstance(number, bool):
            refusals.append(Refusal(project_id, f"{key} is {number!r}, not a whole number"))
            continue
        values[column] = number

    for key, column in VERBATIM_LIST.items():
        items = row[key]
        if not isinstance(items, list):
            refusals.append(Refusal(project_id, f"{key} is {type(items).__name__}, not a list"))
            continue
        values[column] = items

    for key, column in EXPORT_DATES.items():
        parsed, refusal = to_export_date(str(row[key]), project_id)
        if refusal is not None:
            refusals.append(refusal)
            continue
        values[column] = parsed

    for key, column in HEALTH_DIMENSIONS.items():
        rating = str(row[key])
        if rating == "":
            values[column] = None
        elif rating in tuple(ShemaHealthLevel):
            values[column] = ShemaHealthLevel(rating)
        else:
            refusals.append(Refusal(project_id, f"{key} reads {rating!r}, which is not a rating"))

    status = str(row["status"])
    if status == "":
        values["status"] = None
    elif status in tuple(ShemaProjectStatus):
        values["status"] = ShemaProjectStatus(status)
    else:
        refusals.append(
            Refusal(project_id, f"status reads {status!r}, which is not one of the eight")
        )

    intervention = str(row["needsPastoralIntervention"])
    if intervention in tuple(ShemaYesNo):
        values["needs_pastoral_intervention"] = ShemaYesNo(intervention)
    else:
        refusals.append(
            Refusal(project_id, f"needsPastoralIntervention reads {intervention!r}, not sim/nao")
        )

    coords = row["coords"]
    if (
        not isinstance(coords, list)
        or len(coords) != 2
        or not all(
            isinstance(value, int | float) and not isinstance(value, bool) for value in coords
        )
    ):
        refusals.append(
            Refusal(project_id, f"coords is {coords!r}, not a [longitude, latitude] pair")
        )
    else:
        values["longitude"], values["latitude"] = float(coords[0]), float(coords[1])

    in_eten = row["inETEN"]
    if not isinstance(in_eten, bool):
        refusals.append(Refusal(project_id, f"inETEN is {in_eten!r}, not a boolean"))
    else:
        values["in_eten"] = in_eten

    for key in OWN_TABLE_KEYS:
        if row[key]:
            refusals.append(
                Refusal(
                    project_id,
                    f"{key} carries {len(row[key])} entries and this import writes no child rows; "
                    "it is empty on all 127 records and dropping it silently would lose data",
                )
            )

    for key in DROPPED_KEYS:
        if row[key]:
            refusals.append(
                Refusal(
                    project_id,
                    f"{key} reads {row[key]!r} and the schema has no column for it: the region's "
                    "role-holders are read from the org chart, never copied onto a project",
                )
            )

    if row["team"] != row["ywamBase"]:
        refusals.append(
            Refusal(
                project_id,
                f"team is {row['team']!r} and ywamBase is {row['ywamBase']!r}; they are one "
                "concept in two columns and BE-02 collapsed them into one, which only holds "
                "while they agree",
            )
        )

    if refusals:
        return refusals

    location = values["location"]
    flag = _is_sensitive(row, location, countries)
    values["sensitive_country"] = flag.sensitive
    values["region_key"] = region_of(location)
    values["approved_units_unverified"] = True
    return PlannedRecord(project_id=project_id, values=values, source=row, flag=flag)


def _findings_for(row: dict[str, Any], record: PlannedRecord) -> list[Finding]:
    """Everything about one row a person should look at, with the rule that handled it."""
    project_id = record.project_id
    found: list[Finding] = []

    if record.values["region_key"] is ShemaRegionKey.OTHER:
        country = countries_named(row["location"])
        detail = (
            "location is empty, so the region is the fallback and no country was read"
            if not country
            else f"{country[0]!r} is not in the region map, so the region is the fallback"
        )
        found.append(Finding("region fell back to 'other'", project_id, detail))

    named = countries_named(row["location"])
    if len(named) > 1:
        found.append(
            Finding(
                "location names more than one country",
                project_id,
                f"{row['location']!r} — the region follows {named[0]!r}; the flag asks about all "
                f"{len(named)}",
            )
        )

    if row["coords"] == [0, 0]:
        found.append(
            Finding(
                "coords are [0, 0]",
                project_id,
                "stored as they arrived; [0, 0] means no coordinate rather than the Gulf of "
                "Guinea, and hasPlottableCoords is the single owner of that reading",
            )
        )

    code = row["languageCode"]
    if not (len(code) == 3 and code.isalpha() and code.islower()):
        found.append(
            Finding(
                "languageCode is not ISO-shaped",
                project_id,
                f"{code!r} imported unchanged — the code is checked and never refused",
            )
        )

    if row["translatedUnits"] > row["totalUnits"]:
        found.append(
            Finding(
                "translated units exceed the scope",
                project_id,
                f"{row['translatedUnits']}/{row['totalUnits']} imported as it stands; no "
                "translated <= total constraint exists, because the scope is what is wrong here",
            )
        )

    if row["totalUnits"] == 0:
        found.append(
            Finding("scope is zero", project_id, "totalUnits is 0, so progress has no denominator")
        )

    if not row["objective"]:
        found.append(
            Finding(
                "objective is empty",
                project_id,
                "imported empty; it is one of the four fields required to save, so this record "
                "cannot be saved through the API until somebody fills it",
            )
        )

    if not row["bridgeLanguage"]:
        found.append(
            Finding(
                "bridgeLanguage is empty",
                project_id,
                "imported empty; required to save and empty on all 127 records",
            )
        )

    if row["approvedUnits"] == row["translatedUnits"] and row["approvedUnits"] > 0:
        found.append(
            Finding(
                "approved units are a copy of the translated ones",
                project_id,
                f"{row['approvedUnits']} imported as it stands with approved_units_unverified "
                "set, so the ETEN report can tell a migrated number from an approval anybody made",
            )
        )

    name = row["languageName"]
    if name != name.strip() or "\xa0" in name:
        found.append(
            Finding(
                "languageName carries unusual whitespace",
                project_id,
                f"{name!r} imported unchanged — trimming or casing a language name renames it",
            )
        )

    if row["sensitivity"] and not record.flag.sensitive:
        found.append(
            Finding(
                "the export's sensitivity text was not a restriction",
                project_id,
                f"{row['sensitivity']!r} asserts no restriction and the client has cleared every "
                "country this record names, so the flag is off",
            )
        )

    if bool(row["sensitiveCountry"]) != record.flag.sensitive:
        found.append(
            Finding(
                "the flag disagrees with the export",
                project_id,
                f"the export said {row['sensitiveCountry']!r} and this import decided "
                f"{record.flag.sensitive!r}: "
                f"{'; '.join(record.flag.reasons) or 'every country it names is cleared'}",
            )
        )

    return found


def plan(rows: list[dict[str, Any]], countries: SensitiveCountries) -> Plan:
    """Read the whole export into column values and findings, with no database in hand.

    The shape checks come first and stop everything: a duplicate id would make *idempotent*
    meaningless, and a record whose key set is not the export's 55 is not the file this
    program was written against. Refusing the whole run rather than the offending record is
    deliberate — a partial import of a dataset whose shape has changed is the state nobody
    can reason about afterwards.
    """
    built = Plan()
    seen: set[str] = set()
    for row in rows:
        project_id = str(row.get("id", ""))
        if not project_id:
            built.refusals.append(
                Refusal("<no id>", "the record carries no id, and the id is the address")
            )
            continue
        if project_id in seen:
            built.refusals.append(
                Refusal(project_id, "the id appears more than once in the export")
            )
            continue
        seen.add(project_id)
        missing = EXPORT_KEYS - row.keys()
        extra = row.keys() - EXPORT_KEYS
        if missing or extra:
            built.refusals.append(
                Refusal(
                    project_id,
                    f"the record's keys are not the export's 55: missing {sorted(missing)}, "
                    f"unexpected {sorted(extra)}",
                )
            )
            continue
        read = _read_row(row, countries)
        if isinstance(read, list):
            built.refusals.extend(read)
            continue
        built.records.append(read)
        built.findings.extend(_findings_for(row, read))

    if rows:
        built.columns_empty_everywhere = tuple(
            sorted(key for key in EXPORT_KEYS if all(not row.get(key) for row in rows))
        )
        built.countries_named_by_the_export = tuple(
            sorted(
                {
                    country
                    for row in rows
                    for country in countries_named(str(row.get("location", "")))
                }
            )
        )
    return built


@dataclass
class Change:
    """One thing a run did, or would do, to one record."""

    project_id: str
    detail: str


@dataclass
class Outcome:
    """What the run did — or, in a dry-run, what it would have done and did not."""

    inserted: list[Change] = field(default_factory=list)
    flags_raised: list[Change] = field(default_factory=list)
    flags_lowered: list[Change] = field(default_factory=list)
    flags_lowering_withheld: list[Change] = field(default_factory=list)
    regions_corrected: list[Change] = field(default_factory=list)
    left_alone: list[Change] = field(default_factory=list)
    unchanged: int = 0


async def apply_plan(
    db: AsyncSession,
    built: Plan,
    countries: SensitiveCountries,
    *,
    write: bool,
    allow_lowering: bool,
) -> Outcome:
    """Insert what is missing and reconcile the two values no person owns.

    Missing records are written in full. Existing ones keep every field a coordinator may
    have typed since — this is a one-time migration and not a synchroniser — and receive
    only ``sensitive_country``, from the client's list, and ``region_key``, and the latter
    only while ``location`` still holds what was imported: once somebody has corrected the
    country, the region belongs to the service that wrote the correction.

    A record whose ``source`` is NULL was born in the product and is left entirely alone,
    even when its id collides with an export slug. Nothing in this file writes over a record
    that did not come from this file.

    ``write=False`` runs every comparison and issues no INSERT, no UPDATE and no commit,
    which is what makes the dry-run's report the same report the real run produces.

    ``countries`` is asked again here rather than reused from the plan, and the difference
    is the point: the plan decided each flag from the **export's** location, and a reconcile
    decides it from the **record's** location as it stands today, so a country a coordinator
    corrected is the country the flag answers to.
    """
    outcome = Outcome()
    existing = {
        row.id: row
        for row in (
            await db.execute(
                select(ShemaProject).where(
                    ShemaProject.id.in_([record.project_id for record in built.records])
                )
            )
        )
        .scalars()
        .all()
    }

    for record in built.records:
        current = existing.get(record.project_id)
        if current is None:
            outcome.inserted.append(
                Change(
                    record.project_id,
                    f"region {record.values['region_key'].value}, "
                    f"sensitive_country {record.values['sensitive_country']}",
                )
            )
            if write:
                db.add(ShemaProject(source=record.source, **record.values))
            continue

        if current.source is None:
            outcome.left_alone.append(
                Change(
                    record.project_id,
                    "the record has no source and was not born in this import",
                )
            )
            continue

        reported = False
        wanted = _is_sensitive(current.source, current.location, countries)
        if wanted.sensitive and not current.sensitive_country:
            outcome.flags_raised.append(Change(record.project_id, "; ".join(wanted.reasons)))
            if write:
                current.sensitive_country = True
            reported = True
        elif not wanted.sensitive and current.sensitive_country:
            if allow_lowering:
                outcome.flags_lowered.append(
                    Change(record.project_id, "every country this record names is confirmed clear")
                )
                if write:
                    current.sensitive_country = False
            else:
                outcome.flags_lowering_withheld.append(
                    Change(
                        record.project_id,
                        "every country it names is confirmed clear, and the flag stays on because "
                        "--allow-lowering was not given",
                    )
                )
            reported = True

        derived = region_of(current.location)
        if current.region_key == derived:
            pass
        elif current.location == record.values["location"]:
            outcome.regions_corrected.append(
                Change(record.project_id, f"{current.region_key.value} → {derived.value}")
            )
            if write:
                current.region_key = derived
            reported = True
        else:
            outcome.left_alone.append(
                Change(
                    record.project_id,
                    f"location has been edited to {current.location!r} since the import; the "
                    "region is left to the service that wrote it",
                )
            )
            reported = True

        if not reported:
            outcome.unchanged += 1

    if write:
        await db.commit()
    return outcome


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def render_report(
    built: Plan,
    outcome: Outcome,
    *,
    export: Path,
    countries: SensitiveCountries,
    write: bool,
    allow_lowering: bool,
) -> str:
    """The written record of what was empty, what was ambiguous and what this import decided.

    It names projects in sensitive countries — the reviewer has to see which records carry
    the flag in order to check it — which is why :func:`_report_destination` refuses to put
    it anywhere inside this repository.
    """
    lines: list[str] = []
    add = lines.append
    add("# Shemá — importing the 127 Notion projects")
    add("")
    add(
        f"- Run at **{datetime.now(UTC).isoformat(timespec='seconds')}**, "
        f"**{'applied' if write else 'dry-run, nothing written'}**"
    )
    add(f"- Export: `{export}` — sha256 `{_sha256(export)}`, {len(built.records)} records read")
    add(f"- Database: `{engine.url.render_as_string(hide_password=True)}`")
    if countries.source is None:
        add("- Client country list: **NOT SUPPLIED**")
    else:
        add(
            f"- Client country list: `{countries.source}` — sha256 `{_sha256(countries.source)}`, "
            f"confirmed on {countries.confirmed_on or '(unstated)'} by "
            f"{countries.confirmed_by or '(unstated)'}"
        )
    add("")

    add("## 1. The sensitive-country gate")
    add("")
    if countries.is_pending:
        add(
            "> **The client's list has not arrived.** Every country is therefore unrecognised, "
            "every one of the records below is flagged sensitive, and that is the intended state "
            "rather than a finished import. Re-run with `--countries` when the written list "
            "exists; nothing in the code changes when it does."
        )
        add("")
    add(
        "The flag is never derived from the export. It is the client's answer per country, "
        "with two one-way additions: a country the list does not name is unrecognised and "
        "therefore sensitive, and a record the export itself marked confidential keeps the flag "
        "whatever the list says about its country. Lowering a flag needs `--allow-lowering`."
    )
    add("")
    add("### 1.1 Every country the export names, and the answer it has")
    add("")
    add("| Country | Client's verdict | Region map |")
    add("|---|---|---|")
    for country in built.countries_named_by_the_export:
        verdict = (
            countries.verdict_for(country)
            if countries.has_answered(country)
            else "**unanswered → sensitive**"
        )
        mapped = (
            COUNTRY_REGION[country].value if country in COUNTRY_REGION else "— (falls to `other`)"
        )
        add(f"| `{country}` | {verdict} | {mapped} |")
    add("")
    flagged = [record for record in built.records if record.flag.sensitive]
    add(f"### 1.2 Records this import flags sensitive — {len(flagged)} of {len(built.records)}")
    add("")
    if not flagged:
        add("None.")
    else:
        add("| Project | Why |")
        add("|---|---|")
        for record in flagged:
            add(f"| `{record.project_id}` | {'; '.join(record.flag.reasons)} |")
    add("")

    add("## 2. What stopped the run")
    add("")
    if not built.refusals:
        add("Nothing. Every record was readable.")
    else:
        add("These values have no rule, so this import refused them rather than choosing one.")
        add("")
        for refusal in built.refusals:
            add(f"- `{refusal.project_id}` — {refusal.detail}")
    add("")

    add("## 3. What was empty")
    add("")
    add(
        f"{len(built.columns_empty_everywhere)} of the export's 55 columns are empty on every "
        "record read. They are imported as empty, not as absent: an export column's word for "
        "*nothing was written here* is the empty string, and the columns the product added — "
        "which the export does not have at all — are the ones that stay NULL."
    )
    add("")
    for key in built.columns_empty_everywhere:
        add(f"- `{key}`")
    add("")

    add("## 4. What was ambiguous, and what was decided about it")
    add("")
    by_kind: dict[str, list[Finding]] = {}
    for finding in built.findings:
        by_kind.setdefault(finding.kind, []).append(finding)
    if not by_kind:
        add("Nothing.")
    for kind in sorted(by_kind):
        group = by_kind[kind]
        add(f"### {kind} — {len(group)} record(s)")
        add("")
        for finding in group:
            add(f"- `{finding.project_id}` — {finding.detail}")
        add("")

    add("## 5. What this run did")
    add("")
    if not write:
        add("**Nothing.** This was a dry-run; the lists below are what an `--apply` run would do.")
        add("")
    add(f"- Inserted: {len(outcome.inserted)}")
    add(f"- Flags raised: {len(outcome.flags_raised)}")
    add(f"- Flags lowered: {len(outcome.flags_lowered)}")
    add(
        f"- Flags that would have been lowered and were not: {len(outcome.flags_lowering_withheld)}"
    )
    add(f"- Regions corrected: {len(outcome.regions_corrected)}")
    add(f"- Left alone: {len(outcome.left_alone)}")
    add(f"- Already correct, nothing to do: {outcome.unchanged}")
    add("")
    for title, changes in (
        ("Inserted", outcome.inserted),
        ("Flags raised", outcome.flags_raised),
        ("Flags lowered", outcome.flags_lowered),
        (
            "Flags withheld from lowering (`--allow-lowering` not given)",
            outcome.flags_lowering_withheld,
        ),
        ("Regions corrected", outcome.regions_corrected),
        ("Left alone", outcome.left_alone),
    ):
        if not changes:
            continue
        add(f"### {title}")
        add("")
        for change in changes:
            add(f"- `{change.project_id}` — {change.detail}")
        add("")

    add("## 6. What this import deliberately did not write")
    add("")
    add(
        "- **No child rows.** `materials`, `needsItems` and `progressHistory` are empty on every "
        "record; `shema_materials`, `shema_needs` and `shema_progress_history` stay empty, and a "
        "non-empty one would have stopped the run rather than been dropped."
    )
    add(
        "- **No prayer request and no visibility.** The export's `prayerRequests` is empty on "
        "every record, and `prayer_visibility` is left NULL, which means `coordenacao`. The "
        "prototype's `prayerSeed.json` is a frontend fixture invented to exercise the wall; "
        "importing it would put fabricated requests in a store the product treats as real."
    )
    add(
        "- **No health rating.** The three dimensions are empty on every record and are stored "
        'NULL. `""` is not `boa`: a default here would report every silent team as healthy.'
    )
    add(
        "- **No org-chart names.** `regionalCoordinator`, `obtLabPerson` and "
        "`resourceCirclePerson` have no column; the region's role-holders are read from the "
        "org chart by reference."
    )
    add(
        "- **No history.** The export carries none and this import invents none — every year-end "
        "ETEN reconstruction reads `shema_progress_history`, so it is empty until the field "
        "starts reporting."
    )
    add("")
    return "\n".join(lines) + "\n"


def _report_destination(path: Path) -> Path:
    """Refuse to write the report inside the repository, and say why.

    The report names projects in sensitive countries. A path under the working tree is one
    `git add .` away from being published, and `.gitignore` is a promise somebody else can
    edit; refusing the path is not.
    """
    resolved = path.expanduser().resolve()
    repository = Path(__file__).resolve().parent.parent
    if resolved == repository or repository in resolved.parents:
        raise SystemExit(
            f"{resolved} is inside {repository}. The report names projects in sensitive "
            "countries and does not belong in a repository; write it somewhere else."
        )
    return resolved


async def run(
    export: Path,
    countries: SensitiveCountries,
    report: Path,
    *,
    write: bool,
    allow_lowering: bool,
) -> int:
    payload = json.loads(export.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise SystemExit(f"{export}: expected a JSON array of project records.")

    built = plan(payload, countries)
    if built.refusals:
        for refusal in built.refusals:
            print(f"refused: {refusal.project_id} — {refusal.detail}", file=sys.stderr)
        report.write_text(
            render_report(
                built,
                Outcome(),
                export=export,
                countries=countries,
                write=False,
                allow_lowering=allow_lowering,
            ),
            encoding="utf-8",
        )
        print(f"\n{len(built.refusals)} value(s) this import will not guess at. Report: {report}")
        return 1

    async with AsyncSessionLocal() as db:
        outcome = await apply_plan(db, built, countries, write=write, allow_lowering=allow_lowering)

    report.write_text(
        render_report(
            built,
            outcome,
            export=export,
            countries=countries,
            write=write,
            allow_lowering=allow_lowering,
        ),
        encoding="utf-8",
    )

    if countries.is_pending:
        print(
            "\n*** The client's country list was not supplied. Every country is unrecognised, "
            f"so all {len(built.records)} records are flagged sensitive. This is the fail-closed "
            "default, not a finished import. ***\n"
        )
    print(f"{len(built.records)} records read, {len(built.findings)} findings")
    print(
        f"{'applied' if write else 'dry-run'}: "
        f"{len(outcome.inserted)} inserted, {len(outcome.flags_raised)} flags raised, "
        f"{len(outcome.flags_lowered)} lowered, "
        f"{len(outcome.flags_lowering_withheld)} lowerings withheld, "
        f"{len(outcome.regions_corrected)} regions corrected, {outcome.unchanged} unchanged"
    )
    if outcome.flags_lowering_withheld:
        print(
            f"{len(outcome.flags_lowering_withheld)} record(s) would lose the sensitive flag. "
            "Read the report, then re-run with --allow-lowering if the client's list is right."
        )
    print(f"Report: {report}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Import the Notion project export into shema_projects, fail-closed."
    )
    parser.add_argument(
        "--export",
        required=True,
        type=Path,
        help="the Notion export JSON. It is read from outside this repository and nothing of it "
        "is copied in.",
    )
    parser.add_argument(
        "--countries",
        type=Path,
        default=None,
        help="the client's written verdict per country. Without it the list is empty, every "
        "country is unrecognised, and every record is flagged sensitive.",
    )
    parser.add_argument(
        "--report",
        required=True,
        type=Path,
        help="where to write the report. It names projects in sensitive countries, so a path "
        "inside this repository is refused.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="actually write. Without it the run changes nothing and prints what it would do.",
    )
    parser.add_argument(
        "--allow-lowering",
        action="store_true",
        help="permit clearing the sensitive flag on a record that already carries it. Needed only "
        "for the run that brings the client's list to records imported before it existed.",
    )
    args = parser.parse_args(argv)

    countries = (
        SensitiveCountries.pending()
        if args.countries is None
        else SensitiveCountries.from_file(args.countries.expanduser())
    )
    return asyncio.run(
        run(
            args.export.expanduser(),
            countries,
            _report_destination(args.report),
            write=args.apply,
            allow_lowering=args.allow_lowering,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
