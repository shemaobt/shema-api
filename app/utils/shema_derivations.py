"""FE-44 §7's nine derivations, as pure functions of ``(record, now)``.

``src/utils/__tests__/dataJsParity.json`` is the acceptance artifact — the output of these
nine over all 127 export records at ``2026-05-14`` — and FE-44 §7 is explicit about what
that makes them: **a server that computes them differently is wrong, not different.** The
file is vendored into ``tests/test_shema/`` and ``tests/test_shema/test_parity.py`` replays
it. The frontend's owners are ``src/utils/progress.ts``, ``health.ts``, ``recency.ts`` and
``region.ts``, read for their semantics and not transcribed.

**In ``app/utils/`` and not in ``app/services/shema/``, which is where a query-shaped reading
of §3 would put them.** ``tests/test_app_boots.py`` forbids any module in ``app/models/`` from
importing ``app/services/`` — ``test_no_dto_module_reaches_up_into_the_service_layer``, the
inversion that closed an import cycle once — and these are needed by the response models *and*
by the services. ``app/utils/description_rule.py`` is the precedent and the same shape, and
``app/utils/`` is flat, so the file carries the ``shema_`` prefix rather than forming a package
its siblings do not have (``docs/shema.md`` §3.1).

**The clock is a date, and that is the fix for both timezone traps rather than a shortcut.**
``docs/shema.md`` §6.5 names two failures the frontend has already had: a year boundary read
through a ``Date`` rather than from the ISO string by field, and a progress stamp taken as a
UTC day rather than the actor's local one. Both are the same defect — a calendar question
answered through an instant. Every comparison below is between two :class:`datetime.date`
values, so there is no instant to be in the wrong zone, and the one place a real clock is
needed (*which day is it for the person asking*) is the caller's to answer and is injected.
``app/utils/stored_time.py`` is this repository's helper for the other direction — reading a
stored moment back — and is deliberately not called here: nothing in this file measures a
moment.

**One consequence of that, stated because it is a real difference and not a rounding.**
``isRecentlyUpdated`` over there divides an unfloored millisecond difference and compares it
to 30, so a record updated exactly 30 days ago stops being *recent* at one second past
midnight; :func:`is_recently_updated` compares whole calendar days and keeps it recent for
the whole of that day. The parity artifact pins ``now`` at midnight, where the two agree, and
the calendar reading is the one this product's own vocabulary means — every date here is a
day somebody wrote down (FE-44 §9.0).
"""

from __future__ import annotations

import enum
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Final, NamedTuple, Protocol

from app.db.models.shema_enums import (
    ShemaEtenCreditSource,
    ShemaHealthLevel,
    ShemaProjectStatus,
    ShemaRegionKey,
)

#: The six statuses a record may carry stored. ``final`` and ``nao-iniciado`` are **derived
#: only** and never stored — FE-44 §7.1 — so a server that narrowed the column to the three
#: the record form edits would make the 24 records stored as ``desconhecido``, ``cancelado``
#: or ``concluido`` unsaveable.
EXPLICIT_PROJECT_STATUSES: Final[frozenset[ShemaProjectStatus]] = frozenset(
    {
        ShemaProjectStatus.EM_ANDAMENTO,
        ShemaProjectStatus.CANCELADO,
        ShemaProjectStatus.PAUSADO,
        ShemaProjectStatus.PLANEJADO,
        ShemaProjectStatus.CONCLUIDO,
        ShemaProjectStatus.DESCONHECIDO,
    }
)

#: The four statuses that make staleness meaningless: a finished or unstarted project is not
#: silent, it is finished (FE-44 §7.3).
NEVER_STALE: Final[frozenset[ShemaProjectStatus]] = frozenset(
    {
        ShemaProjectStatus.CONCLUIDO,
        ShemaProjectStatus.CANCELADO,
        ShemaProjectStatus.PLANEJADO,
        ShemaProjectStatus.DESCONHECIDO,
    }
)

STALE_ATTENTION_DAYS: Final = 60
STALE_CRITICAL_DAYS: Final = 120
RECENT_UPDATE_DAYS: Final = 30
DEADLINE_SOON_DAYS: Final = 90

#: ``boa 3 / atencao 2 / critica 1 / unassessed 0``, summed over the four dimensions. Used
#: **only for sorting** (FE-44 §7.4) — it is not a grade and no screen shows it as one.
HEALTH_SCORES: Final[dict[ShemaHealthLevel | None, int]] = {
    ShemaHealthLevel.BOA: 3,
    ShemaHealthLevel.ATENCAO: 2,
    ShemaHealthLevel.CRITICA: 1,
    None: 0,
}


class OverallHealth(enum.StrEnum):
    """The worst of four dimensions, plus the state the seed is actually in.

    Not in ``app/db/models/shema_enums.py`` with the stored vocabularies because no column
    holds it: it is a **derivation**, and a native PostgreSQL enum for a value that is never
    written would be a migration bought for nothing — the argument
    :class:`~app.models.shema_privacy.ShemaAudience` already makes one file over.

    ``na`` is ``ShemaHealthLevel``'s NULL read from the other side, and it is the dominant
    state: all 127 seed records arrive with every dimension empty. The copy says the team has
    not been heard yet, never that it is well.
    """

    BOA = "boa"
    ATENCAO = "atencao"
    CRITICA = "critica"
    NA = "na"


class StaleStatus(enum.StrEnum):
    """Days since the last progress update, in three bands. ``None`` is *not applicable*."""

    EM_DIA = "em-dia"
    ATENCAO = "atencao"
    CRITICO = "critico"


class ProjectPriority(enum.StrEnum):
    """The card's tone — health, staleness and status composed in one written order."""

    CRITICAL = "critical"
    WARNING = "warning"
    COMPLETED = "completed"
    PLANNED = "planned"
    PAUSED = "paused"
    CANCELED = "canceled"
    UNKNOWN = "unknown"
    DEFAULT = "default"


class DeadlineClass(enum.StrEnum):
    """How a deadline sits against today. ``NONE`` is *no deadline recorded*."""

    OVERDUE = "overdue"
    SOON = "soon"
    OK = "ok"
    NONE = ""


#: Country string → region, keyed on **the export's exact spelling** and never normalised.
#: ``São Tomé e Príncipe`` is in Portuguese and ``East Timor`` in English on purpose: these
#: are the 25 strings the ``location`` column actually holds, and running them through a
#: geocoder or a title-caser would silently move records to ``other``. ``docs/shema.md`` §4.9
#: refuses ``app/api/places.py`` for this reason.
#:
#: ``src/constants/regions.ts``'s ``COUNTRY_REGION``, copied rather than re-derived.
COUNTRY_REGION: Final[dict[str, ShemaRegionKey]] = {
    "Brazil": ShemaRegionKey.SOUTH_AMERICA,
    "Peru": ShemaRegionKey.SOUTH_AMERICA,
    "Colombia": ShemaRegionKey.SOUTH_AMERICA,
    "Mexico": ShemaRegionKey.NORTH_AMERICA,
    "Panama": ShemaRegionKey.NORTH_AMERICA,
    "United States": ShemaRegionKey.NORTH_AMERICA,
    "Canada": ShemaRegionKey.NORTH_AMERICA,
    "Egypt": ShemaRegionKey.AFRICA,
    "Mozambique": ShemaRegionKey.AFRICA,
    "South Africa": ShemaRegionKey.AFRICA,
    "South Sudan": ShemaRegionKey.AFRICA,
    "Sudan": ShemaRegionKey.AFRICA,
    "Guinea-Bissau": ShemaRegionKey.AFRICA,
    "São Tomé e Príncipe": ShemaRegionKey.AFRICA,
    "Togo": ShemaRegionKey.AFRICA,
    "Uganda": ShemaRegionKey.AFRICA,
    "India": ShemaRegionKey.ASIA,
    "China": ShemaRegionKey.ASIA,
    "Indonesia": ShemaRegionKey.ASIA,
    "East Timor": ShemaRegionKey.ASIA,
    "Nepal": ShemaRegionKey.ASIA,
    "Australia": ShemaRegionKey.OCEANIA,
    "Papua New Guinea": ShemaRegionKey.OCEANIA,
    "Fiji": ShemaRegionKey.OCEANIA,
    "Micronesia": ShemaRegionKey.OCEANIA,
}

#: What a country outside the map lands in. Two export records have an empty ``location`` and
#: land here legitimately, which is why ``other`` is a real region and not an error state.
FALLBACK_REGION: Final = ShemaRegionKey.OTHER


class Assessable(Protocol):
    """The four health dimensions, as any carrier of them answers."""

    health_emotional: ShemaHealthLevel | None
    health_relational: ShemaHealthLevel | None
    health_spiritual: ShemaHealthLevel | None
    health_physical: ShemaHealthLevel | None


class Derivable(Assessable, Protocol):
    """What the nine derivations read, and the whole of it.

    Structural rather than a base class, because the two things that satisfy it are a
    Pydantic response model (``app/models/shema_projects.py``) and a test's own record — and
    ``app/utils/`` may not import ``app/models/`` without inverting the dependency that
    ``app/models/`` has on this file.

    :attr:`last_progress_date` is the one member that is **not** a column on
    ``shema_projects``: it is the newest ``shema_progress_history`` entry's date, which the
    service joins in. Naming it here rather than accepting a history list is what keeps this
    file from having an opinion about how that row is found.
    """

    status: ShemaProjectStatus | None
    total_units: int
    translated_units: int
    start_date: date | None
    last_progress_date: date | None
    last_updated: date | None
    deadline: date | None


class Sortable(Derivable, Protocol):
    """The two text columns the Projetos screen orders by, on top of what it derives.

    The orders themselves are ``app/utils/shema_facets.py``'s, with the progress bands: they
    are the screen's, not FE-44 §7's, and this file is the nine.
    """

    language_name: str
    team: str


@dataclass(frozen=True)
class Derivations:
    """The nine, computed together — and the exact shape of a ``dataJsParity.json`` row.

    They are one object rather than nine calls because they are not independent: status feeds
    staleness, staleness and health feed priority, and computing them separately means
    computing status three times per record on the busiest screen in the product. The
    facet pass computes this once per record and both filters and counts on it, which is how
    a count cannot disagree with a card (``docs/shema.md`` §6.5, and the DoD's second line).

    :attr:`region` is **not** derived from the record's ``location`` here — see
    :func:`derive`.
    """

    status: ShemaProjectStatus
    health: OverallHealth
    stale: StaleStatus | None
    progress: float
    priority: ProjectPriority
    health_score: int
    days_since_update: int | None
    last_progress_update: date | None
    region: ShemaRegionKey


def countries_named(location: str) -> tuple[str, ...]:
    """Every country the free-text ``location`` names, in the order it names them.

    ``location`` is free text and five records name more than one country — ``China, Laos,
    Vietnam``, ``Canada, United States``, ``India, Nepal``, ``Mexico, United States``,
    ``Colombia, Peru``. The frontend has no function for this: ``getCountry`` takes the
    first and the region follows from it alone (§7.6), which is right for a region and
    wrong for a safety question. **BE-16's fail-closed flag asks about all of them**, so the
    split lives here, once, beside the reader that uses its first element — rather than
    twice, with a seed script holding its own copy of what a comma means.

    The separator is the comma and only the comma. ``&`` and ``/`` separate people in this
    export, never places, and the record's own fields keep them unsplit for that reason.
    """
    return tuple(part.strip() for part in location.split(",") if part.strip())


def get_country(location: str) -> str:
    """The country a ``location`` names — the first one, or ``""`` when it names none.

    Free text that may name several countries (``China, Laos, Vietnam``); the first is the
    one the region is read from. Nothing is normalised, title-cased or transliterated: the
    keys of :data:`COUNTRY_REGION` are the export's own spellings. The split itself belongs
    to :func:`countries_named`, so *what a comma means* has one definition and BE-16's
    fail-closed flag cannot drift from the region derived here.
    """
    named = countries_named(location)
    return named[0] if named else ""


def get_region(location: str) -> ShemaRegionKey:
    """The region a ``location`` falls in, or :data:`FALLBACK_REGION`.

    **The writer's function, not the reader's.** ``shema_projects.region_key`` is a stored
    column maintained by whoever writes ``location`` (``docs/shema.md`` §6.1), because the
    region predicate rides on every scoped list query and a per-query derivation would make
    it unsargable. Read the column; call this when writing it.
    """
    return COUNTRY_REGION.get(get_country(location), FALLBACK_REGION)


def get_progress(record: Derivable) -> float:
    """``translated / total * 100``, and ``0`` when the scope is zero.

    Never clamped to 100. Three real records report more translated units than their scope
    holds (``156/25``, ``8/0``, ``4/0``) and ``docs/shema.md`` reads that as the scope being
    wrong rather than the count — so the number says 624% and a coordinator goes and looks,
    which a silent ``min(100, …)`` would prevent.
    """
    if record.total_units <= 0:
        return 0.0
    return record.translated_units / record.total_units * 100


def project_status(record: Derivable) -> ShemaProjectStatus:
    """The stored status when it is one of the six explicit ones, else derived from progress.

    The order is the whole of FE-44 §7.1 and the half a reimplementer gets wrong alone: the
    stored value **wins**, and the derivation is the fallback for *not one of the six* —
    which is what the nullable column's NULL is.
    """
    if record.status in EXPLICIT_PROJECT_STATUSES:
        return record.status  # type: ignore[return-value]
    progress = get_progress(record)
    if progress == 0:
        return ShemaProjectStatus.NAO_INICIADO
    if progress == 100:
        return ShemaProjectStatus.CONCLUIDO
    if progress >= 75:
        return ShemaProjectStatus.FINAL
    return ShemaProjectStatus.EM_ANDAMENTO


def _dimensions(record: Assessable) -> list[ShemaHealthLevel]:
    """The dimensions that were actually rated. NULL is absent, never ``boa``."""
    rated = [
        record.health_emotional,
        record.health_relational,
        record.health_spiritual,
        record.health_physical,
    ]
    return [value for value in rated if value is not None]


def is_assessed(record: Assessable) -> bool:
    """Whether anybody has rated any dimension.

    It gates everything that counts an assessment, including Rhythm's readiness, where a
    ``health_assessment_date`` with four empty dimensions would otherwise report a team as
    heard when nobody rated it (FE-44 §7.4).
    """
    return bool(_dimensions(record))


def overall_health(record: Assessable) -> OverallHealth:
    """The worst of the four, and :attr:`OverallHealth.NA` when none is filled.

    *Not assessed* is the dominant state and not an edge case — it is all 127 seed records —
    so the missing answer has a name of its own instead of being folded into ``boa``.
    """
    return overall_of(*_dimensions(record))


def overall_of(*levels: ShemaHealthLevel | None) -> OverallHealth:
    """:func:`overall_health`, for a carrier whose fields are not named ``health_*``.

    One rule, two callers, and no second copy of it: a ``shema_health_assessments`` row spells
    the four dimensions ``emotional``/``relational``/``spiritual``/``physical`` — it is an
    assessment, so the prefix would be saying *health* twice — and so satisfies no protocol
    written for the record. BE-07 needs the overall **per history entry**, which is what lets
    the console draw the trend off the server's computation instead of re-implementing the one
    thing ``docs/shema.md`` says lives here once.

    ``None`` is filtered rather than scored, here as in :func:`_dimensions`: unassessed is not a
    low rating.
    """
    values = [level for level in levels if level is not None]
    if not values:
        return OverallHealth.NA
    if ShemaHealthLevel.CRITICA in values:
        return OverallHealth.CRITICA
    if ShemaHealthLevel.ATENCAO in values:
        return OverallHealth.ATENCAO
    return OverallHealth.BOA


def health_score(record: Assessable) -> int:
    """The four dimensions scored and summed, for sorting and nothing else."""
    return sum(HEALTH_SCORES[value] for value in _dimensions(record))


def last_progress_update(record: Derivable) -> date | None:
    """The date staleness is measured from: the newest progress entry, else the start date.

    Deliberately **not** ``last_updated``, which is the Pulse-cycle freshness signal the
    ``recent`` preset reads (:func:`is_recently_updated`). Two different questions — *when
    did the counts last move* and *when did we last hear anything* — and FE-44 §7.3 keeps
    them apart on purpose.
    """
    return record.last_progress_date or record.start_date


def days_since_update(record: Derivable, now: date) -> int | None:
    """Whole days between the last progress update and ``now``, or ``None`` if never.

    ``None`` is *nothing to measure from* and is not zero: 119 of the 127 export records
    have neither a progress entry nor a start date.
    """
    last = last_progress_update(record)
    if last is None:
        return None
    return (now - last).days


def stale_status(record: Derivable, now: date) -> StaleStatus | None:
    """≥120 days ``critico``, ≥60 ``atencao``, else ``em-dia`` — ``None`` when not applicable.

    Two ways to be ``None`` and they mean the same thing to a reader: the status says
    staleness is meaningless (:data:`NEVER_STALE`), or nothing was ever recorded to measure
    from.
    """
    if project_status(record) in NEVER_STALE:
        return None
    days = days_since_update(record, now)
    if days is None:
        return None
    if days >= STALE_CRITICAL_DAYS:
        return StaleStatus.CRITICO
    if days >= STALE_ATTENTION_DAYS:
        return StaleStatus.ATENCAO
    return StaleStatus.EM_DIA


def is_no_news(status: StaleStatus | None) -> bool:
    """``atencao`` **or** ``critico`` — what the filter named *sem notícias 60+ dias* means.

    **Not the [60, 120) bucket**, and this is the reading FE-44 §7.3 says a reimplementer
    gets wrong alone. Before ``isNoNews`` existed on the frontend, the projects most out of
    contact were absent from the very filter named after them.
    """
    return status in (StaleStatus.ATENCAO, StaleStatus.CRITICO)


def stale_filter_matches(status: StaleStatus | None, wanted: StaleStatus) -> bool:
    """Whether ``status`` answers a filter asking for ``wanted``.

    ``atencao`` is the inclusive reading above; ``em-dia`` and ``critico`` keep exact
    matching. One function so the filter predicate and the facet count cannot disagree —
    they both call it.
    """
    if wanted is StaleStatus.ATENCAO:
        return is_no_news(status)
    return status is wanted


def is_recently_updated(record: Derivable, now: date) -> bool:
    """The ``recent`` preset: ``last_updated`` within 30 calendar days.

    A different field from the one staleness reads, deliberately (FE-44 §7.3). See the module
    docstring for the one boundary day on which this and the frontend's unfloored millisecond
    comparison disagree.
    """
    if record.last_updated is None:
        return False
    return (now - record.last_updated).days <= RECENT_UPDATE_DAYS


def deadline_class(deadline: date | None, now: date) -> DeadlineClass:
    """``overdue`` / ``soon`` (< 90 days) / ``ok``, or :attr:`DeadlineClass.NONE`.

    No export record carries a deadline, so this is entirely for records typed in the
    product; it is here rather than in the screen because the sort by deadline and the badge
    on the card have to agree about what *soon* is.
    """
    days = days_to_deadline(deadline, now)
    if days is None:
        return DeadlineClass.NONE
    if days < 0:
        return DeadlineClass.OVERDUE
    if days < DEADLINE_SOON_DAYS:
        return DeadlineClass.SOON
    return DeadlineClass.OK


def days_to_deadline(deadline: date | None, now: date) -> int | None:
    """Calendar days from ``now`` to ``deadline``; negative once it has passed."""
    if deadline is None:
        return None
    return (deadline - now).days


def priority(record: Derivable, now: date) -> ProjectPriority:
    """The card's tone, from health, staleness and status — in FE-44 §7.4's written order.

    The order is the content: a cancelled project is *cancelled* even when its health is
    critical, because the tone answers *what should I do about this* and there is nothing to
    do about a cancelled one. Reordering the branches is a product change, not a refactor.
    """
    status = project_status(record)
    if status is ShemaProjectStatus.CANCELADO:
        return ProjectPriority.CANCELED
    if status is ShemaProjectStatus.PAUSADO:
        return ProjectPriority.PAUSED

    health = overall_health(record)
    stale = stale_status(record, now)
    if health is OverallHealth.CRITICA or stale is StaleStatus.CRITICO:
        return ProjectPriority.CRITICAL
    if health is OverallHealth.ATENCAO or stale is StaleStatus.ATENCAO:
        return ProjectPriority.WARNING

    if status is ShemaProjectStatus.CONCLUIDO:
        return ProjectPriority.COMPLETED
    if status is ShemaProjectStatus.PLANEJADO:
        return ProjectPriority.PLANNED
    if status is ShemaProjectStatus.DESCONHECIDO:
        return ProjectPriority.UNKNOWN
    return ProjectPriority.DEFAULT


def derive(record: Derivable, now: date, *, region: ShemaRegionKey) -> Derivations:
    """The nine, once, for a record and a day.

    ``region`` is a **parameter and not a derivation of the record**, which is the one place
    this function departs from its frontend counterpart, and the reason is two facts meeting.
    ``shema_projects.region_key`` is the stored, maintained column the scope predicate rides
    on (``docs/shema.md`` §6.1) — so re-deriving it from ``location`` on the read path would
    be a second owner of it. And on a payload that has already left coordination the
    ``location`` **is** the region name, so :func:`get_region` over it would answer ``other``
    for every project in a sensitive country — a derivation that is wrong exactly for the
    records the redaction protects.

    Computing all nine together rather than on demand is deliberate: four of them read
    :func:`project_status` and three read :func:`stale_status`, so the lazy spelling costs
    the busiest screen in the product a third more work for no reader's benefit.
    """
    return Derivations(
        status=project_status(record),
        health=overall_health(record),
        stale=stale_status(record, now),
        progress=get_progress(record),
        priority=priority(record, now),
        health_score=health_score(record),
        days_since_update=days_since_update(record, now),
        last_progress_update=last_progress_update(record),
        region=region,
    )


# --- ETEN credit (FE-44 §7.8) — BE-11 ------------------------------------------------------
#
# GATE-01 closed on 25/sep/2026 (OBT-387): a credit is one completed defined scope, counted in
# approved chapters and never a divisor; the year is ETEN's fiscal year, August to July; each
# partner receives the whole credit; the credit belongs to the fiscal year the project ended;
# partial scope earns nothing. ``src/utils/etenCredits.ts``'s ``accountFor`` is the reference
# and FE-51 (OBT-530) moves it to the fiscal year; the departures below are the ones the server
# can see and the console cannot, and each is argued where it is made.

#: The day ETEN's fiscal year closes, as ``(month, day)``. ``?year=2026`` is the year that
#: **ends** on 31/07/2026, and a day is placed in a year by comparing these two calendar fields —
#: there is no instant here to be in the wrong zone, which is the whole of FE-44 §7.8's trap.
FISCAL_YEAR_CLOSE: Final = (7, 31)


def fiscal_year_of(day: date) -> int:
    """The fiscal year ``day`` belongs to: 31 July closes one, 1 August opens the next."""
    return day.year if (day.month, day.day) <= FISCAL_YEAR_CLOSE else day.year + 1


def fiscal_year_start(year: int) -> date:
    """1 August of the calendar year before — the first day ``year`` covers."""
    return date(year - 1, FISCAL_YEAR_CLOSE[0] + 1, 1)


def fiscal_year_end(year: int) -> date:
    """31 July of ``year`` — the cut the year-end reading is taken at."""
    return date(year, *FISCAL_YEAR_CLOSE)


def completion_date_after(
    previous: ShemaProjectStatus | None,
    current: ShemaProjectStatus | None,
    stamped: date | None,
    day: date,
) -> date | None:
    """The ``completed_date`` a save leaves behind — GATE-01's 25/sep answer, as one function.

    **Stamped on the move into** ``concluido`` **and only then**, with the saver's own day: the
    status records *that* a project finished and the stamp is what records *when*. A save of a
    record that was already ``concluido`` keeps what it had, so the concluded records that
    predate the stamp stay undated — *"só daqui para frente"* — and keep earning ``null`` with the
    manual entry as the valve. **Leaving** ``concluido`` **clears it**: a reopened project has not
    finished, and a date left behind would credit a year for a completion the record no longer
    claims. Moving back in stamps the new day, which is the literal rule and a known residual —
    the trail shows every move.
    """
    if current is not ShemaProjectStatus.CONCLUIDO:
        return None
    if previous is ShemaProjectStatus.CONCLUIDO:
        return stamped
    return day


class ProgressPoint(NamedTuple):
    """One ``shema_progress_history`` entry, as the credit rule reads it.

    A value rather than the ORM row so the rule stays a pure function a test can feed by hand;
    ``app/services/shema/eten_report.py`` maps the rows. The history is append-only in the
    database, so :attr:`id` is a reference that means the same thing for as long as it exists.
    """

    id: str
    entry_date: date
    approved_units: int
    total_units: int | None
    previous_approved: int | None
    initial: bool


class CreditSubject(NamedTuple):
    """The five facts of a project the credit rule reads, and nothing about where it is."""

    status: ShemaProjectStatus | None
    total_units: int
    approved_units: int
    approved_units_unverified: bool
    completed_date: date | None


class ReadingSource(enum.StrEnum):
    """Where a year-end reading came from: a history entry, or the record as it stands."""

    HISTORY = "history"
    LIVE = "live"


class CompletionSource(enum.StrEnum):
    """What decided :attr:`CreditAccount.completed_in_year`: the stamped date, or the readings."""

    COMPLETED_DATE = "completedDate"
    SNAPSHOTS = "snapshots"


@dataclass(frozen=True)
class YearEndReading:
    """The approved chapters at one cut, and the evidence of where the number was read."""

    source: ReadingSource
    approved_units: int
    total_units: int | None
    entry_id: str | None = None
    on: date | None = None


@dataclass(frozen=True)
class CreditAccount:
    """One project's account for one fiscal year — ``accountFor``'s answer, with its working.

    The first ten are FE-44 §5.6's frozen ``EtenYearSnapshot`` fields. The last four are the
    evidence the DoD asks for — *every total traceable to its contributing projects and
    events*: which history entry each reading came from and on what day, what decided the year,
    and whether the approved count still came from the export.
    """

    approved_at_start: int
    approved_at_end: int
    advanced: int
    scope_units: int
    concluded: bool
    completed_in_year: bool
    undated_completion: bool
    has_data: bool
    credits: int | None
    credits_source: ShemaEtenCreditSource | None
    start_reading: YearEndReading | None
    end_reading: YearEndReading | None
    completion_source: CompletionSource
    approved_unverified: bool


def trusted_history(
    subject: CreditSubject, history: Sequence[ProgressPoint]
) -> list[ProgressPoint]:
    """The entries whose approved count is a reading of approvals, oldest first.

    **A count copied from the export is not one.** The export's ``approvedUnits`` is a copy of
    ``translatedUnits`` on all 127 records, and BE-16 imported it as it stood with
    ``approved_units_unverified`` set (``docs/shema.md`` §10 item 7) so that this rule could
    tell the two apart. Nothing clears the flag, so reading it as *never count this project*
    would switch the calculation off for every migrated record for good, typed approvals
    included. What it marks is the **number**: an entry carries the export's copy forward until
    a save actually moves the approved count, and from that entry on the count is somebody's.
    So a flagged project's history counts from its first entry whose approved count moved, and
    not before. A project born in the product was never flagged and counts whole.
    """
    if not subject.approved_units_unverified:
        return list(history)
    for index, point in enumerate(history):
        if point.previous_approved is not None and point.approved_units != point.previous_approved:
            return list(history[index:])
    return []


def _reading(
    subject: CreditSubject, trusted: Sequence[ProgressPoint], year: int, today: date
) -> YearEndReading | None:
    """``approvedAtYearEnd``: the newest trusted entry on or before 31 July of ``year``.

    With no entry there, the year that is **still open** reads the record as it stands — the
    console's own fallback, which is what lets the current year say something before its first
    entry. A closed year with no entry has no reading at all, and ``None`` is that answer rather
    than a zero. The live count is never read for a flagged record: it is the export's copy.
    """
    cut = fiscal_year_end(year)
    upto = [point for point in trusted if point.entry_date <= cut]
    if upto:
        last = upto[-1]
        return YearEndReading(
            source=ReadingSource.HISTORY,
            approved_units=last.approved_units,
            total_units=last.total_units,
            entry_id=last.id,
            on=last.entry_date,
        )
    if year >= fiscal_year_of(today) and not subject.approved_units_unverified:
        return YearEndReading(
            source=ReadingSource.LIVE,
            approved_units=subject.approved_units,
            total_units=subject.total_units,
        )
    return None


def _arrived_complete(subject: CreditSubject, trusted: Sequence[ProgressPoint]) -> bool:
    """Whether the first trusted reading already met the scope — an arrival, not a completion.

    A record created with its counts writes an ``initial`` entry on the day it was filed, and a
    flagged record's first trusted entry sits on top of the export's copy. Either way there is
    no earlier reading the product trusts, so a scope already met there closed **before** the
    product could see it, and crediting the year of the filing would be the plausible number the
    issue warns about. The console's rule reads a missing start as zero and cannot tell.
    """
    if not trusted or subject.total_units <= 0:
        return False
    first = trusted[0]
    return (first.initial or subject.approved_units_unverified) and (
        first.approved_units >= subject.total_units
    )


def account_for(
    subject: CreditSubject,
    history: Sequence[ProgressPoint],
    year: int,
    *,
    manual_credits: int | None,
    today: date,
) -> CreditAccount:
    """FE-44 §7.8's ``accountFor`` over the fiscal year — one project, one year, its working.

    ``history`` is oldest first (``entry_date``, then the moment it was written). ``today`` is
    injected so a test moves the calendar rather than the machine.

    **Two sources for the year, FE-51's.** When the project is ``concluido`` with a
    ``completed_date`` and a defined scope, the stamp's fiscal year is the year it ended — the
    client chose the status over *scope covered*. Otherwise the readings decide, exactly as the
    console does: a credit when the approved count crosses the scope between the two cuts.

    **One exception to the stamp**, and it is what keeps a project from being counted twice
    across two reports that were both sent: if the trusted readings show the scope already met
    at the start of the stamp's year, the scope closed earlier and a report already credited
    that year from the readings; the status set afterwards is a late recording, and the
    readings keep deciding.

    **The credit.** A manual entry wins. A completion stamped inside the year earns 1 even with
    no reading of the year — the stamp is itself the fact. An undated completion — ``concluido``
    with the readings short of the scope, or a scope that was already met when the product first
    saw it — earns ``None``, as does a year with no reading at all: *a year with no data is not
    a year of zero credits*. Anything else is ``0`` or ``1``, whole, never a division, and whole
    for every partner.
    """
    trusted = trusted_history(subject, history)
    start = _reading(subject, trusted, year - 1, today)
    end = _reading(subject, trusted, year, today)
    start_units = start.approved_units if start is not None else 0
    end_units = end.approved_units if end is not None else 0

    scope = subject.total_units
    concluded = subject.status is ShemaProjectStatus.CONCLUIDO
    has_data = end is not None
    reached_end = scope > 0 and end_units >= scope
    reached_start = scope > 0 and start_units >= scope

    stamped = subject.completed_date if concluded and scope > 0 else None
    if stamped is not None:
        before = _reading(subject, trusted, fiscal_year_of(stamped) - 1, today)
        if before is not None and before.approved_units >= scope:
            stamped = None

    if stamped is not None:
        completed_in_year = fiscal_year_of(stamped) == year
        undated = False
        completion = CompletionSource.COMPLETED_DATE
    else:
        crossed = reached_end and not reached_start
        arrived = crossed and start is None and _arrived_complete(subject, trusted)
        completed_in_year = crossed and not arrived
        undated = (concluded and not reached_end) or arrived
        completion = CompletionSource.SNAPSHOTS

    credits: int | None
    source: ShemaEtenCreditSource | None
    if manual_credits is not None:
        credits, source = manual_credits, ShemaEtenCreditSource.MANUAL
    elif stamped is not None and completed_in_year:
        credits, source = 1, ShemaEtenCreditSource.CALCULATED
    elif undated or not has_data:
        credits, source = None, None
    else:
        credits, source = int(completed_in_year), ShemaEtenCreditSource.CALCULATED

    return CreditAccount(
        approved_at_start=start_units,
        approved_at_end=end_units,
        advanced=end_units - start_units,
        scope_units=scope,
        concluded=concluded,
        completed_in_year=completed_in_year,
        undated_completion=undated,
        has_data=has_data,
        credits=credits,
        credits_source=source,
        start_reading=start,
        end_reading=end,
        completion_source=completion,
        approved_unverified=subject.approved_units_unverified,
    )
