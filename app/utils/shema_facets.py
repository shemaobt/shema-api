"""One pass that produces the visible list **and** every facet count — FE-44 §7.6.

``src/utils/search.ts``'s ``filterProjects``, read for its semantics. The rule it implements
is one sentence and the whole reason the sidebar's numbers can be trusted: **an option counts
a record when the record passes every filter group except, at most, that one.** So the count
beside *Crítica* is what you would see if you clicked it, and a count never promises results a
click will not return.

**Why this is one function and not sixteen queries.** The issue's own line is that counts and
results must agree, and that two queries which ought to match are how they stop. One pass over
one set is the strongest available spelling of *they agree by construction*: the same
:class:`~app.utils.shema_derivations.Derivations` object decides whether a record is in the
list and whether it is in each count, so a divergence has nowhere to live. FE-44 §9.1's
warning is against a **second owner** of the counting rule — a filtered list with counts
computed somewhere else — and this file is written to be the one owner rather than the second.

**Why it is in Python rather than in SQL, and which half is in SQL.** The region scope is a
``WHERE`` and stays one: ``app/services/shema/_scope.py`` holds the module's only
``select(ShemaProject)`` and every reader starts from it, so nothing here can page or count
past a scope. Everything above that is not expressible as an index on this schema, and
``app/db/models/shema.py`` says which and why: overall health is the worst of four nullable
dimensions, staleness is a function of the newest progress entry *and* a clock, status falls
back to progress, ``objective``/``translation_type``/``financial_resources`` are JSON arrays
in a repository with no JSONB and no GIN precedent, and the free-text search wants a
``tsvector`` that SQLite — which is what the suite runs on — cannot carry. Pushing the
expressible half down and leaving the rest here would split the rule across two languages,
which is exactly the two-owner defect the paragraph above is about.

**What it costs, and the trigger that changes the answer.** This is O(records in scope) per
request, over 127 records today. FE-44 §9.1 names the point where that stops being the right
trade — past roughly 2,000 projects — and when it comes, this file is the one to replace: the
service above it hands it a scoped set and reads back a result, so a materialised projection
or a search index slots in underneath without the endpoint, the filters or the counts changing
shape.

**It reads the payload, never a row.** The records handed in are already-redacted leaving
shapes (``app/models/shema_privacy.py``), so ``country`` here is the country the caller is
being shown — which for a project in a sensitive country is its region. That is what makes the
DoD's fourth line true of the counts and not only of the results: a facet cannot name a place
the payload beside it withholds, because it is reading that payload. It is also why this file
lives in ``app/utils/`` rather than in ``app/services/shema/``, where
``tests/test_shema/test_privacy_owners.py`` correctly refuses any second reader of the guarded
**columns**.
"""

from __future__ import annotations

import unicodedata
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import date
from typing import Final, Generic, Protocol, TypeVar

from app.db.models.shema_enums import ShemaNeedStatus, ShemaNeedUrgency, ShemaRegionKey
from app.utils.shema_derivations import (
    FALLBACK_REGION,
    Derivations,
    OverallHealth,
    ProjectPriority,
    Sortable,
    StaleStatus,
    derive,
    get_country,
    in_progress_range,
    is_recently_updated,
    sort_key,
    stale_filter_matches,
)

#: The sixteen groups the sidebar counts, in FE-44's own order.
FACET_GROUPS: Final[tuple[str, ...]] = (
    "status",
    "team",
    "health",
    "objective",
    "financial",
    "stale",
    "country",
    "continent",
    "vitality",
    "translationType",
    "needCategory",
    "eten",
    "sensitive",
    "progressRange",
    "hasMedia",
    "hasOpenNeeds",
)

#: The four presets. They are filter groups and are **not** facet groups: each is a single
#: toggle, so its count is one number rather than a dict of options.
PRESETS: Final[tuple[str, ...]] = ("attention", "prayer", "celebrate", "recent")

#: Every group a record can fail, free text included. The order does not decide anything —
#: a record that fails two is dropped whichever two they are — but it is the list this file
#: iterates, so a group missing from it would be a filter that silently never applies.
FILTER_GROUPS: Final[tuple[str, ...]] = ("search", *FACET_GROUPS, *PRESETS)

#: The progress bands, **inclusive at both ends**, so 50% counts under two of them. See
#: :func:`~app.utils.shema_derivations.in_progress_range`.
PROGRESS_RANGES: Final[tuple[tuple[str, int, int], ...]] = (
    ("0-25", 0, 25),
    ("25-50", 25, 50),
    ("50-75", 50, 75),
    ("75-100", 75, 100),
)

#: The groups whose whole vocabulary is short, closed and safe to publish as zeros. A key
#: present with ``0`` says *this option exists and matches nothing here*, which is what lets
#: the sidebar grey a checkbox out instead of hiding it.
#:
#: Every other group is counted **sparsely**, and for ``continent`` that is a privacy property
#: rather than a convenience: a zero beside a region the caller cannot reach would answer
#: *there is nothing in Africa* to somebody who may not know either way, which is the
#: existence answer arriving through the back door (``app/services/shema/count_projects.py``
#: makes the same call for the same reason).
DENSE_GROUPS: Final[dict[str, tuple[str, ...]]] = {
    "health": tuple(member.value for member in OverallHealth),
    "stale": tuple(member.value for member in StaleStatus),
    "eten": ("yes", "no"),
    "sensitive": ("yes", "no"),
    "hasMedia": ("yes", "no"),
    "hasOpenNeeds": ("yes", "no"),
    "progressRange": tuple(name for name, _low, _high in PROGRESS_RANGES),
}

#: The two need states that are still somebody's problem. ``dropped`` leaves the open list
#: without deleting the history a region is judged by (``docs/shema.md`` §5.4), so it is
#: closed here exactly like ``fulfilled`` — and a dropped need must not hold a project in the
#: ``attention`` preset any more than a fulfilled one does (FE-44 §7.7).
OPEN_NEED_STATUSES: Final[frozenset[ShemaNeedStatus]] = frozenset(
    {ShemaNeedStatus.OPEN, ShemaNeedStatus.IN_PROGRESS}
)

#: The three apostrophes a user may type or paste, folded to the plain one before matching:
#: U+2018 and U+2019, which every word processor and phone keyboard substitutes, and U+02BC,
#: which is a letter in several of the orthographies these language names are written in.
#: Spelled by code point because the glyphs are indistinguishable from ``'`` in most fonts,
#: which is the whole reason the fold is needed.
_APOSTROPHES: Final[dict[int, str]] = dict.fromkeys((0x2018, 0x2019, 0x02BC), "'")


class NeedLike(Protocol):
    """What the three need-shaped facets and two presets read off a need."""

    category: str
    urgency: ShemaNeedUrgency
    status: ShemaNeedStatus
    prayer_shared: bool
    prayer_answered: bool


class Facetable(Sortable, Protocol):
    """A record this pass can filter and count — a leaving shape, never a table row.

    Structural for the same reason :class:`~app.utils.shema_derivations.Derivable` is:
    ``app/utils/`` may not import ``app/models/``, which is where the one real implementation
    lives.

    :attr:`search_text` is supplied by ``app/services/shema/_redaction.py``, the only file
    allowed to decide what a search may match a project on. It arrives here already reduced,
    so this pass cannot widen a haystack by reading a column the owner left out.

    **The four collections are read-only properties and the scalars are not**, which is not a
    style choice: a protocol's variable member is invariant, so declaring ``needs`` as one
    would refuse a card whose own field is a ``list`` of a *narrower* need shape — which is
    every real implementation. A read-only member is covariant and accepts it, and saying
    read-only here is true anyway: nothing in this file writes to a record.
    """

    region_key: ShemaRegionKey | None
    location: str
    vitality_status: str
    in_eten: bool
    location_withheld: bool
    has_media: bool
    search_text: str

    @property
    def objective(self) -> Sequence[str]: ...

    @property
    def translation_type(self) -> Sequence[str]: ...

    @property
    def financial_resources(self) -> Sequence[str]: ...

    @property
    def needs(self) -> Sequence[NeedLike]: ...


class ProjectFilters(Protocol):
    """Every filter the Projetos screen offers, each ``None``/``False`` when not applied.

    FE-12 established the full set and FE-44 froze it; the server builds all of it rather than
    the subset the current UI happens to render, because a filter added to the sidebar later
    is then a frontend change instead of another endpoint.
    """

    search: str | None
    status: str | None
    team: str | None
    health: str | None
    objective: str | None
    financial: str | None
    stale: StaleStatus | None
    country: str | None
    continent: str | None
    vitality: str | None
    translation_type: str | None
    need_category: str | None
    eten: str | None
    sensitive: str | None
    progress_range: str | None
    has_media: str | None
    has_open_needs: str | None
    attention: bool
    prayer: bool
    celebrate: bool
    recent: bool


RecordT = TypeVar("RecordT", bound=Facetable)


@dataclass
class FacetCounts:
    """The sidebar's numbers, by group.

    :attr:`groups` is sparse or dense per :data:`DENSE_GROUPS`; :attr:`group_all` is what each
    group's count would be with *that group's* filter cleared, which is the number the *All*
    row of a group shows.
    """

    groups: dict[str, Counter[str]] = field(default_factory=dict)
    presets: Counter[str] = field(default_factory=Counter)
    group_all: Counter[str] = field(default_factory=Counter)


@dataclass(frozen=True)
class FacetResult(Generic[RecordT]):
    """What one pass answers: the list, its counts, and the size of the set it started from.

    :attr:`total` is the scoped collection's size — *of 127* — and :attr:`matched` is the
    filtered set's, which is what the header reads and what paging divides. They are both here
    because a screen that shows only one of them cannot tell an empty region from an
    over-narrow filter.
    """

    visible: list[tuple[RecordT, Derivations]]
    counts: FacetCounts
    total: int

    @property
    def matched(self) -> int:
        return len(self.visible)


def normalize_search_text(value: str) -> str:
    """Fold a string to what a search compares: unaccented, apostrophe-normalised, lowercase.

    ``src/utils/search.ts``'s ``normalizeSearchText``. Accents are stripped rather than
    respected because the haystack is a mix of Portuguese, English and language names typed by
    many hands — *Purépecha* and *Purepecha* are one language and a coordinator should not have
    to know which spelling the export used. This is the **search** rule only: nothing that
    stores or displays a name normalises it (``app/db/models/shema.py``).
    """
    decomposed = unicodedata.normalize("NFD", value)
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return " ".join(stripped.translate(_APOSTROPHES).split()).lower()


def is_open_need(need: NeedLike) -> bool:
    """Whether a need is still somebody's problem — see :data:`OPEN_NEED_STATUSES`."""
    return need.status in OPEN_NEED_STATUSES


def has_open_needs(needs: Iterable[NeedLike]) -> bool:
    return any(is_open_need(need) for need in needs)


def has_urgent_open_need(needs: Iterable[NeedLike]) -> bool:
    return any(need.urgency is ShemaNeedUrgency.HIGH and is_open_need(need) for need in needs)


def preset_matches(record: Facetable, derived: Derivations, now: date) -> dict[str, bool]:
    """The four presets, evaluated once — FE-44 §7.7.

    ``attention`` is deliberately three unrelated reasons rather than one score: a team can be
    in trouble for its health, for its silence, or because it asked for something urgent and
    nobody answered, and folding them into a number would make the screen unable to say which.
    """
    return {
        "attention": (
            derived.health is OverallHealth.CRITICA
            or derived.stale is StaleStatus.CRITICO
            or has_urgent_open_need(record.needs)
        ),
        "prayer": any(need.prayer_shared for need in record.needs),
        "celebrate": (
            derived.priority is ProjectPriority.COMPLETED
            or any(need.prayer_answered for need in record.needs)
        ),
        "recent": is_recently_updated(record, now),
    }


def _in_band(derived: Derivations, band: str) -> bool:
    for name, low, high in PROGRESS_RANGES:
        if name == band:
            return in_progress_range(derived, low, high)
    return False


def _passes(
    record: Facetable,
    derived: Derivations,
    filters: ProjectFilters,
    needle: str,
    presets: dict[str, bool],
) -> dict[str, bool]:
    """Whether the record satisfies each filter group, one entry per group.

    A group with nothing selected passes trivially, which is what makes the *at most one
    failure* rule mean *the one group you are hovering* rather than *the one group that
    happens to be set*.
    """
    country = get_country(record.location)
    need_categories = {need.category for need in record.needs}
    return {
        "search": not needle or needle in normalize_search_text(record.search_text),
        "status": not filters.status or derived.status.value == filters.status,
        "team": not filters.team or record.team == filters.team,
        "health": not filters.health or derived.health.value == filters.health,
        "objective": not filters.objective or filters.objective in record.objective,
        "financial": not filters.financial or filters.financial in record.financial_resources,
        "stale": filters.stale is None or stale_filter_matches(derived.stale, filters.stale),
        "country": not filters.country or country == filters.country,
        "continent": not filters.continent or derived.region.value == filters.continent,
        "vitality": not filters.vitality or record.vitality_status == filters.vitality,
        "translationType": (
            not filters.translation_type or filters.translation_type in record.translation_type
        ),
        "needCategory": not filters.need_category or filters.need_category in need_categories,
        "eten": not filters.eten or (filters.eten == "yes") == record.in_eten,
        "sensitive": (
            not filters.sensitive or (filters.sensitive == "yes") == record.location_withheld
        ),
        "progressRange": not filters.progress_range or _in_band(derived, filters.progress_range),
        "hasMedia": not filters.has_media or (filters.has_media == "yes") == record.has_media,
        "hasOpenNeeds": (
            not filters.has_open_needs
            or (filters.has_open_needs == "yes") == has_open_needs(record.needs)
        ),
        "attention": not filters.attention or presets["attention"],
        "prayer": not filters.prayer or presets["prayer"],
        "celebrate": not filters.celebrate or presets["celebrate"],
        "recent": not filters.recent or presets["recent"],
    }


def _empty_counts() -> FacetCounts:
    counts = FacetCounts(groups={group: Counter() for group in FACET_GROUPS})
    for group, options in DENSE_GROUPS.items():
        for option in options:
            counts.groups[group][option] = 0
    for preset in PRESETS:
        counts.presets[preset] = 0
    for group in FACET_GROUPS:
        counts.group_all[group] = 0
    return counts


def _count_record(
    counts: FacetCounts,
    record: Facetable,
    derived: Derivations,
    presets: dict[str, bool],
    only_failure: str | None,
) -> None:
    """Add one record to every group it is allowed to count in.

    ``only_failure`` is the single group this record fails, or ``None`` when it fails none —
    and a group counts the record when one of those two is true of it. That single line is the
    whole faceting rule; everything below is which key each group increments.

    Three shapes of group, and each is a decision rather than a style:

    * **Single-valued** (status, health, continent, eten, sensitive) — one key.
    * **Multi-valued** (objective, financial, translation type, need category) — each
      *distinct* value once, so a project with two ``equipment`` needs counts once. The count
      is projects, not items, which is FE-44 §7.6's *a count never promises results a click
      will not return*: clicking the option returns the project.
    * **Overlapping** (stale, progress range) — every band the record answers to, because
      ``atencao`` includes ``critico`` and the progress bands share their endpoints.

    ``team``, ``country`` and ``vitality`` skip the empty string: it is not an option in the
    sidebar, and counting it would put a nameless row at the top of a list ordered by count.
    """

    def counting(group: str) -> bool:
        return only_failure is None or only_failure == group

    if counting("status"):
        counts.groups["status"][derived.status.value] += 1
    if counting("team") and record.team:
        counts.groups["team"][record.team] += 1
    if counting("health"):
        counts.groups["health"][derived.health.value] += 1
    if counting("objective"):
        for value in set(record.objective):
            counts.groups["objective"][value] += 1
    if counting("financial"):
        for value in set(record.financial_resources):
            counts.groups["financial"][value] += 1
    if counting("stale") and derived.stale is not None:
        for member in StaleStatus:
            if stale_filter_matches(derived.stale, member):
                counts.groups["stale"][member.value] += 1
    if counting("country"):
        country = get_country(record.location)
        if country:
            counts.groups["country"][country] += 1
    if counting("continent"):
        counts.groups["continent"][derived.region.value] += 1
    if counting("vitality") and record.vitality_status:
        counts.groups["vitality"][record.vitality_status] += 1
    if counting("translationType"):
        for value in set(record.translation_type):
            counts.groups["translationType"][value] += 1
    if counting("needCategory"):
        for value in {need.category for need in record.needs if need.category}:
            counts.groups["needCategory"][value] += 1
    if counting("eten"):
        counts.groups["eten"]["yes" if record.in_eten else "no"] += 1
    if counting("sensitive"):
        counts.groups["sensitive"]["yes" if record.location_withheld else "no"] += 1
    if counting("progressRange"):
        for name, low, high in PROGRESS_RANGES:
            if in_progress_range(derived, low, high):
                counts.groups["progressRange"][name] += 1
    if counting("hasMedia"):
        counts.groups["hasMedia"]["yes" if record.has_media else "no"] += 1
    if counting("hasOpenNeeds"):
        counts.groups["hasOpenNeeds"]["yes" if has_open_needs(record.needs) else "no"] += 1

    for preset in PRESETS:
        if counting(preset) and presets[preset]:
            counts.presets[preset] += 1
    for group in FACET_GROUPS:
        if counting(group):
            counts.group_all[group] += 1


def filter_projects(
    records: Sequence[RecordT],
    filters: ProjectFilters,
    now: date,
) -> FacetResult[RecordT]:
    """The list and every facet count, from one pass over one set.

    The shape of the loop is the rule: a record that fails **two or more** groups is invisible
    to everything, a record that fails exactly one is counted **only in that group**, and a
    record that fails none is in the list and in every count. That is what makes the number
    beside an option the number of results clicking it returns — including when a filter in
    another group is already on.

    ``now`` is injected and there is no clock in this file, which is what lets the parity
    replay pin the reference date and lets a test move the calendar without moving the
    machine.
    """
    needle = normalize_search_text(filters.search.strip()) if filters.search else ""
    counts = _empty_counts()
    visible: list[tuple[RecordT, Derivations]] = []

    for record in records:
        derived = derive(record, now, region=record.region_key or FALLBACK_REGION)
        presets = preset_matches(record, derived, now)
        passes = _passes(record, derived, filters, needle, presets)

        failed = [group for group in FILTER_GROUPS if not passes[group]]
        if len(failed) > 1:
            continue
        if not failed:
            visible.append((record, derived))

        _count_record(counts, record, derived, presets, failed[0] if failed else None)

    return FacetResult(visible=visible, counts=counts, total=len(records))


def sort_records(
    visible: list[tuple[RecordT, Derivations]], key: str
) -> list[tuple[RecordT, Derivations]]:
    """Order the visible list by one of the screen's five sorts, blanks last.

    Sorting happens **after** the pass and before the page is cut, which is the order that
    makes a page mean something: a window over an unordered set is a window over an arbitrary
    page, and a window taken before the counts were computed would count a page rather than
    the set.
    """
    return sorted(visible, key=lambda pair: sort_key(pair[0], pair[1], key))
