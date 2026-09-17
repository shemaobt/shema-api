"""The counting rule, swept over far more data than an endpoint test can afford.

``tests/test_shema/test_projects.py`` proves the property through HTTP, over nine records
chosen by hand — which is what proves the endpoint is wired to it, and is bounded by having to
rebuild a schema per test. This file proves the same property over sixty records of deliberately
awkward shape, in a second, because the pass is a pure function and needs no database at all.

**The property, in one sentence:** the number beside an option is the number of results
clicking it returns. Asserted for every option of every one of the sixteen groups and for each
of the four presets, first with nothing else selected and then with a filter already active in
another group — which is the half that separates real faceting from *count the visible rows*.

**The records are generated, not chosen**, from a fixed seed. Chosen records test the cases
their author thought of; sixty generated ones land on the combinations nobody writes down — a
project with no needs at all, one with three needs in one category, an empty ``location``, a
``location`` naming three countries, every health dimension null, a stored status that
contradicts the progress, a start date in the future. The seed is fixed so a failure is a
failure somebody can reproduce, rather than a flake that goes away on re-run.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date, timedelta

import pytest

from app.db.models.shema_enums import (
    ShemaHealthLevel,
    ShemaNeedStatus,
    ShemaNeedUrgency,
    ShemaProjectStatus,
    ShemaRegionKey,
)
from app.utils.shema_derivations import StaleStatus
from app.utils.shema_facets import FACET_GROUPS, PRESETS, filter_projects

#: The parity artifact's own day, so a staleness band here means what it means there.
TODAY = date(2026, 5, 14)

#: Which field of :class:`Filters` each facet group is filtered by. Written out rather than
#: derived: a group whose field is misspelled would otherwise count forever and filter never.
GROUP_FIELD = {
    "status": "status",
    "team": "team",
    "health": "health",
    "objective": "objective",
    "financial": "financial",
    "stale": "stale",
    "country": "country",
    "continent": "continent",
    "vitality": "vitality",
    "translationType": "translation_type",
    "needCategory": "need_category",
    "eten": "eten",
    "sensitive": "sensitive",
    "progressRange": "progress_range",
    "hasMedia": "has_media",
    "hasOpenNeeds": "has_open_needs",
}


@dataclass
class Need:
    """The five fields the pass reads off a need, satisfying ``NeedLike`` structurally."""

    category: str = "financial"
    urgency: ShemaNeedUrgency = ShemaNeedUrgency.LOW
    status: ShemaNeedStatus = ShemaNeedStatus.OPEN
    prayer_shared: bool = False
    prayer_answered: bool = False


@dataclass
class Record:
    """A leaving shape's worth of fields, satisfying ``Facetable`` structurally.

    A dataclass and not ``ShemaProjectCard``, deliberately: what is under test here is the
    counting rule, and building the real response model would drag in the redaction boundary
    whose own tests live in ``test_privacy.py`` and ``test_projects.py``. ``location_withheld``
    is a plain field here for the same reason — this file asks what the pass does with a
    payload, not how the payload came to be reduced.
    """

    id: str
    language_name: str = ""
    team: str = ""
    location: str = ""
    region_key: ShemaRegionKey = ShemaRegionKey.OTHER
    vitality_status: str = ""
    objective: list[str] = field(default_factory=list)
    translation_type: list[str] = field(default_factory=list)
    financial_resources: list[str] = field(default_factory=list)
    in_eten: bool = False
    location_withheld: bool = False
    has_media: bool = False
    needs: list[Need] = field(default_factory=list)
    search_text: str = ""
    status: ShemaProjectStatus | None = None
    total_units: int = 0
    translated_units: int = 0
    health_emotional: ShemaHealthLevel | None = None
    health_relational: ShemaHealthLevel | None = None
    health_spiritual: ShemaHealthLevel | None = None
    health_physical: ShemaHealthLevel | None = None
    start_date: date | None = None
    last_progress_date: date | None = None
    last_updated: date | None = None
    deadline: date | None = None


@dataclass
class Filters:
    """Every filter the screen offers, satisfying ``ProjectFilters`` structurally."""

    search: str | None = None
    status: str | None = None
    team: str | None = None
    health: str | None = None
    objective: str | None = None
    financial: str | None = None
    stale: StaleStatus | None = None
    country: str | None = None
    continent: str | None = None
    vitality: str | None = None
    translation_type: str | None = None
    need_category: str | None = None
    eten: str | None = None
    sensitive: str | None = None
    progress_range: str | None = None
    has_media: str | None = None
    has_open_needs: str | None = None
    attention: bool = False
    prayer: bool = False
    celebrate: bool = False
    recent: bool = False


def _ago(rng: random.Random, most: int) -> date:
    return TODAY - timedelta(days=rng.randint(1, most))


def make_records(count: int = 60, seed: int = 7) -> list[Record]:
    """Awkward records, reproducibly.

    The value ranges are chosen to straddle every boundary the pass has: ``total_units`` of
    zero (progress is 0, not a division by zero), ``translated_units`` above ``total_units``
    (three real export records do this), a ``location`` that is empty and one that names three
    countries, a start date in the future (``days_since_update`` goes negative), and a stored
    status drawn from the whole vocabulary including ``None`` — so the derivation and the
    stored value disagree often rather than never.
    """
    rng = random.Random(seed)
    levels: list[ShemaHealthLevel | None] = [None, *ShemaHealthLevel]
    statuses: list[ShemaProjectStatus | None] = [None, *ShemaProjectStatus]
    records = []
    for index in range(count):
        record = Record(
            id=f"p{index}",
            language_name=f"lang{index}",
            team=rng.choice(["YWAM A", "YWAM B", "YWAM C", ""]),
            location=rng.choice(["Brazil", "Egypt", "India", "", "Fiji, Tonga, Samoa"]),
            region_key=rng.choice(list(ShemaRegionKey)),
            vitality_status=rng.choice(["Vital", "", "Ameaçada"]),
            objective=rng.sample(["NT", "AT", "Histórias"], rng.randint(0, 2)),
            translation_type=rng.sample(["OBT", "OMT"], rng.randint(0, 2)),
            financial_resources=rng.sample(["Seed Company", "Innovation Lab"], rng.randint(0, 2)),
            in_eten=rng.random() < 0.3,
            location_withheld=rng.random() < 0.2,
            has_media=rng.random() < 0.4,
            needs=[
                Need(
                    category=rng.choice(["financial", "training", "security", ""]),
                    urgency=rng.choice(list(ShemaNeedUrgency)),
                    status=rng.choice(list(ShemaNeedStatus)),
                    prayer_shared=rng.random() < 0.3,
                    prayer_answered=rng.random() < 0.3,
                )
                for _ in range(rng.randint(0, 3))
            ],
            status=rng.choice(statuses),
            total_units=rng.choice([0, 10, 100]),
            translated_units=rng.choice([0, 5, 10, 80, 100]),
            health_emotional=rng.choice(levels),
            health_relational=rng.choice(levels),
            health_spiritual=rng.choice(levels),
            health_physical=rng.choice(levels),
            start_date=rng.choice([None, _ago(rng, 500), TODAY + timedelta(days=40)]),
            last_progress_date=rng.choice([None, _ago(rng, 500)]),
            last_updated=rng.choice([None, _ago(rng, 90)]),
        )
        record.search_text = f"{record.language_name} {record.team}"
        records.append(record)
    return records


RECORDS = make_records()


def _filters(group: str, option: str, **others: object) -> Filters:
    value: object = StaleStatus(option) if group == "stale" else option
    return Filters(**{GROUP_FIELD[group]: value, **others})  # type: ignore[arg-type]


@pytest.mark.parametrize("group", FACET_GROUPS)
def test_every_option_of_every_group_counts_what_selecting_it_returns(group: str) -> None:
    """**The counting rule**, per group, over sixty records.

    Parametrised by group so a failure names the one that moved, rather than reporting *one of
    sixteen* and leaving the reader to bisect.
    """
    counts = filter_projects(RECORDS, Filters(), TODAY).counts.groups[group]
    assert counts, f"{group} counted nothing over sixty records, so it is not being exercised"

    for option, promised in counts.items():
        matched = filter_projects(RECORDS, _filters(group, option), TODAY).matched
        assert matched == promised, f"{group}={option} promised {promised}, returned {matched}"


@pytest.mark.parametrize("preset", PRESETS)
def test_every_preset_counts_what_toggling_it_returns(preset: str) -> None:
    counts = filter_projects(RECORDS, Filters(), TODAY).counts
    matched = filter_projects(RECORDS, Filters(**{preset: True}), TODAY).matched
    assert matched == counts.presets[preset]


@pytest.mark.parametrize("region", [member.value for member in ShemaRegionKey])
def test_the_rule_holds_with_a_filter_already_active_in_another_group(region: str) -> None:
    """**The half that separates faceting from counting the visible rows.**

    With a continent already selected, the counts in the other fifteen groups must describe
    that narrowed set — and the counts in the continent group itself must **not**, or every
    other region would read zero and nobody could leave the region they are in. Both halves are
    asserted here, once per region, including the ones with no projects.
    """
    page = filter_projects(RECORDS, Filters(continent=region), TODAY)
    for group, options in page.counts.groups.items():
        for option, promised in options.items():
            others = {} if group == "continent" else {"continent": region}
            matched = filter_projects(RECORDS, _filters(group, option, **others), TODAY).matched
            assert matched == promised, (
                f"with continent={region} active, {group}={option} promised {promised} and "
                f"returned {matched}"
            )


@pytest.mark.parametrize("group", ["eten", "sensitive", "hasMedia", "hasOpenNeeds"])
def test_an_unrecognised_value_on_a_yes_no_group_answers_nothing(group: str) -> None:
    """``?eten=true`` once read as *no* and returned the half the sidebar never promised.

    The sidebar publishes ``yes`` and ``no`` and nothing else, so any other value is the
    ``objective=Xyz`` case and gets its answer: an empty list — and, because every record
    then fails exactly this one group, counts for it that still describe the two real
    options, so the checkboxes a user can click stay right while the list says *nothing*.
    """
    page = filter_projects(RECORDS, _filters(group, "true"), TODAY)
    unfiltered = filter_projects(RECORDS, Filters(), TODAY)
    assert page.matched == 0
    assert page.counts.groups[group] == unfiltered.counts.groups[group]
    assert page.counts.groups[group]["yes"] > 0 and page.counts.groups[group]["no"] > 0


def test_the_group_all_row_is_the_count_with_that_group_cleared() -> None:
    """``groupAll`` is the *All* row of a group: the count with that group's filter removed."""
    page = filter_projects(RECORDS, Filters(continent="africa", eten="yes"), TODAY)
    assert (
        page.counts.group_all["continent"]
        == filter_projects(RECORDS, Filters(eten="yes"), TODAY).matched
    )
    assert (
        page.counts.group_all["eten"]
        == filter_projects(RECORDS, Filters(continent="africa"), TODAY).matched
    )


def test_a_record_failing_two_groups_is_counted_in_neither() -> None:
    """The other edge of the rule, and the one a naïve implementation gets backwards.

    *At most one* failure is what keeps a count honest: a record that misses on two groups is
    not one click away from visible, so counting it under either would promise a result that
    two clicks still do not return.
    """
    only = [
        Record(
            id="two-misses",
            region_key=ShemaRegionKey.AFRICA,
            in_eten=False,
            status=ShemaProjectStatus.PAUSADO,
        )
    ]
    page = filter_projects(only, Filters(continent="asia", eten="yes"), TODAY)
    assert page.matched == 0
    assert page.counts.groups["continent"] == {}
    assert page.counts.groups["eten"] == {"yes": 0, "no": 0}
    assert page.counts.group_all["continent"] == 0

    one_miss = filter_projects(only, Filters(continent="asia"), TODAY)
    assert one_miss.matched == 0
    assert one_miss.counts.groups["continent"] == {"africa": 1}


def test_the_totals_are_the_scope_and_the_match_is_the_filter() -> None:
    """``total`` never moves with a filter; ``matched`` never exceeds it."""
    whole = filter_projects(RECORDS, Filters(), TODAY)
    narrow = filter_projects(RECORDS, Filters(eten="yes", continent="africa"), TODAY)
    assert whole.total == narrow.total == len(RECORDS)
    assert narrow.matched <= whole.matched == len(RECORDS)
