"""The Rhythm's period, read off the calendar and never off an instant.

What is tested is the trap FE-44 §7.5 records the console already fell into: a period built from
``new Date(iso)`` - UTC midnight - and read back in local time filed the 1st of a month under the
previous month, and 1 January under the previous year, in every zone behind UTC. The server's
answer is to have no instant at all, and these tests are arranged so that an implementation
that did reach for one goes red:

- the process timezone is **moved**, to UTC-3 and to UTC+14, the two signs the console's own
  ``cadenceTimezone.test.ts`` checks (Sao Paulo and Fiji), and each fixture first proves the trap
  is armed - an instant read locally really does land on the wrong day - so a test that passes
  under it is not passing because the zone did not take;
- the keys are checked for every day of a leap and a common year, against ``period_start`` and
  ``period_end`` as the oracle, so a boundary that moved by one day anywhere fails;
- and the period functions are read as source, where a call to ``datetime``, ``astimezone`` or
  ``now`` is a failure before any day is tried.

The zone is restored by hand in a ``finally`` and not through ``monkeypatch``: monkeypatch undoes
its environment *after* this fixture's teardown, so a ``tzset()`` there would re-read the moved
zone and every later file on the worker would run in it.
"""

from __future__ import annotations

import ast
import os
import time
from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

from app.utils.shema_derivations import (
    PERIOD_MONTHS,
    Cadence,
    parse_iso_date,
    period_end,
    period_key,
    period_start,
)
from tests.test_shema.conftest import auth_header, make_scoped_user

MEETINGS_LOG = "/api/shema/meetings/log"

#: POSIX zone strings, which need no zone database: ``<-03>3`` is three hours **behind** UTC and
#: ``<+14>-14`` fourteen hours ahead (POSIX writes the offset with the opposite sign).
BEHIND_UTC = "<-03>3"
AHEAD_OF_UTC = "<+14>-14"


def _trap_is_armed(zone: str) -> bool:
    """Whether reading an instant in this process lands on the wrong calendar day.

    Behind UTC the console's own bug: UTC midnight of 1 March, read locally, is 28 February.
    Ahead of UTC its mirror: local midnight of 1 March, read in UTC, is 28 February.
    """
    if zone == BEHIND_UTC:
        return datetime(2026, 3, 1, tzinfo=UTC).astimezone().date() == date(2026, 2, 28)
    return datetime(2026, 3, 1).astimezone(UTC).date() == date(2026, 2, 28)


@pytest.fixture(params=[BEHIND_UTC, AHEAD_OF_UTC], ids=["utc-3", "utc+14"])
def moved_zone(request: pytest.FixtureRequest) -> Iterator[str]:
    """The process timezone moved for one test, and put back whatever the test did."""
    saved = os.environ.get("TZ")
    os.environ["TZ"] = request.param
    time.tzset()
    try:
        assert _trap_is_armed(request.param), f"TZ={request.param} did not take"
        yield request.param
    finally:
        if saved is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = saved
        time.tzset()


#: FE-44 §7.5's keys and GATE-02's two new ones, for the days the trap is about.
FIRST_DAYS: dict[str, dict[Cadence, str]] = {
    "2026-01-01": {
        Cadence.MONTHLY: "2026-01",
        Cadence.BIMONTHLY: "2026-B1",
        Cadence.QUARTERLY: "2026-Q1",
        Cadence.SEMIANNUAL: "2026-H1",
        Cadence.ANNUAL: "2026",
    },
    "2026-03-01": {
        Cadence.MONTHLY: "2026-03",
        Cadence.BIMONTHLY: "2026-B2",
        Cadence.QUARTERLY: "2026-Q1",
        Cadence.SEMIANNUAL: "2026-H1",
        Cadence.ANNUAL: "2026",
    },
    "2026-07-01": {
        Cadence.MONTHLY: "2026-07",
        Cadence.BIMONTHLY: "2026-B4",
        Cadence.QUARTERLY: "2026-Q3",
        Cadence.SEMIANNUAL: "2026-H2",
        Cadence.ANNUAL: "2026",
    },
    "2026-12-31": {
        Cadence.MONTHLY: "2026-12",
        Cadence.BIMONTHLY: "2026-B6",
        Cadence.QUARTERLY: "2026-Q4",
        Cadence.SEMIANNUAL: "2026-H2",
        Cadence.ANNUAL: "2026",
    },
}


def test_the_first_of_a_month_and_new_years_day_keep_their_period(moved_zone: str) -> None:
    """**The DoD's second line.** 1 January is 2026 and 1 March is March, in either zone."""
    for text, keys in FIRST_DAYS.items():
        day = parse_iso_date(text)
        for cadence, expected in keys.items():
            assert period_key(cadence, day) == expected, (moved_zone, text, cadence)


def test_every_cadence_keys_a_day_by_its_calendar_fields() -> None:
    """The spelling is a contract with the console, which compares ``period`` as text: a
    four-digit year, a two-digit month, and a one-digit period number after its letter."""
    assert period_key(Cadence.MONTHLY, date(2026, 5, 14)) == "2026-05"
    assert period_key(Cadence.BIMONTHLY, date(2026, 5, 14)) == "2026-B3"
    assert period_key(Cadence.QUARTERLY, date(2026, 5, 14)) == "2026-Q2"
    assert period_key(Cadence.SEMIANNUAL, date(2026, 5, 14)) == "2026-H1"
    assert period_key(Cadence.ANNUAL, date(2026, 5, 14)) == "2026"
    assert period_key(Cadence.BIMONTHLY, date(2026, 11, 1)) == "2026-B6"
    assert period_key(Cadence.BIMONTHLY, date(2026, 2, 28)) == "2026-B1"
    assert period_key(Cadence.SEMIANNUAL, date(2026, 6, 30)) == "2026-H1"
    assert period_key(Cadence.MONTHLY, date(987, 1, 9)) == "0987-01"


def _days_of(year: int) -> Iterator[date]:
    day = date(year, 1, 1)
    while day.year == year:
        yield day
        day += timedelta(days=1)


@pytest.mark.parametrize("year", [2024, 2026], ids=["leap", "common"])
def test_a_key_changes_exactly_at_the_period_boundary(moved_zone: str, year: int) -> None:
    """Every day of a year, every cadence: a key is shared by exactly the days between its
    period's first and last day, and the day after the last starts the next key.

    ``period_start`` and ``period_end`` are the oracle, and ``period_end`` is anchored to the
    boundary rather than to *the same day next period* - so a period holding the 31st closes on
    the last day of its month and a February in a leap year has 29 days.
    """
    for cadence in Cadence:
        keys: list[str] = []
        for day in _days_of(year):
            key = period_key(cadence, day)
            start, end = period_start(cadence, day), period_end(cadence, day)
            assert start <= day <= end
            assert period_key(cadence, start) == key == period_key(cadence, end)
            assert period_key(cadence, start - timedelta(days=1)) != key
            assert period_key(cadence, end + timedelta(days=1)) != key
            if not keys or keys[-1] != key:
                keys.append(key)
        assert len(keys) == 12 // PERIOD_MONTHS[cadence], (cadence, keys)


def test_the_period_end_is_anchored_to_the_boundary() -> None:
    """``cadence.test.ts``'s own cases: the awkward dates need no special case."""
    assert period_end(Cadence.MONTHLY, date(2026, 1, 31)) == date(2026, 1, 31)
    next_after_january = period_end(Cadence.MONTHLY, date(2026, 1, 31) + timedelta(days=1))
    assert next_after_january == date(2026, 2, 28)
    assert period_end(Cadence.MONTHLY, date(2024, 2, 1)) == date(2024, 2, 29)
    assert period_end(Cadence.QUARTERLY, date(2026, 11, 30)) == date(2026, 12, 31)
    assert period_end(Cadence.QUARTERLY, date(2027, 1, 1)) == date(2027, 3, 31)
    assert period_end(Cadence.BIMONTHLY, date(2024, 1, 15)) == date(2024, 2, 29)
    assert period_end(Cadence.SEMIANNUAL, date(2026, 7, 1)) == date(2026, 12, 31)
    assert period_start(Cadence.SEMIANNUAL, date(2026, 12, 31)) == date(2026, 7, 1)


@pytest.mark.parametrize(
    "text",
    [
        "",
        "2026-13-01",
        "2026-02-30",
        "2026-02-29",
        "14/05/2026",
        "2026-2-1",
        "20260301",
        "2026-W09-7",
        "2026-03-01T00:00:00-03:00",
        "2026-03-01T00:00:00Z",
        "٢٠٢٦-03-01",
    ],
)
def test_a_wire_date_that_is_not_a_calendar_day_is_refused(text: str) -> None:
    """``parseIsoDate``'s refusals, plus the forms Pydantic and ``date.fromisoformat`` accept
    and the console never sends: an offset, a compact date, an ISO week, other scripts' digits."""
    with pytest.raises(ValueError):
        parse_iso_date(text)


@pytest.mark.parametrize("value", [1772323200, 20260301, None, ["2026-03-01"]])
def test_a_wire_date_that_is_not_text_is_a_value_error_and_not_a_crash(value: object) -> None:
    """Pydantic turns a ``ValueError`` into a 422 and anything else into a 500."""
    with pytest.raises(ValueError):
        parse_iso_date(value)


def test_a_real_calendar_day_is_read_as_written() -> None:
    assert parse_iso_date("2024-02-29") == date(2024, 2, 29)
    assert parse_iso_date(" 2026-03-01 ") == date(2026, 3, 1)
    with pytest.raises(ValueError):
        parse_iso_date(datetime(2026, 3, 1, tzinfo=UTC))


#: What reaching for an instant looks like, by name.
_INSTANT_NAMES = frozenset(
    {
        "datetime",
        "now",
        "today",
        "utcnow",
        "astimezone",
        "timestamp",
        "fromtimestamp",
        "utcfromtimestamp",
        "localtime",
        "gmtime",
        "mktime",
    }
)

#: The period functions, by name - the file is shared with other derivations, so the scan is
#: scoped to these rather than to the module.
_PERIOD_FUNCTIONS = frozenset(
    {"parse_iso_date", "_period_index", "period_key", "period_start", "period_end"}
)


def test_the_period_functions_never_reach_for_an_instant() -> None:
    """The rule as a property of the source: none of the period functions calls anything that
    produces or converts an instant. ``parse_iso_date`` names ``datetime`` once, in an
    ``isinstance`` that refuses one, and that is the one mention allowed."""
    source = Path(__file__).resolve().parents[2] / "app" / "utils" / "shema_derivations.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    functions = {
        node.name: node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in _PERIOD_FUNCTIONS
    }
    assert set(functions) == _PERIOD_FUNCTIONS

    reached: dict[str, list[str]] = {}
    for name, function in functions.items():
        for node in ast.walk(function):
            if not isinstance(node, ast.Call):
                continue
            called = node.func.attr if isinstance(node.func, ast.Attribute) else None
            called = called or (node.func.id if isinstance(node.func, ast.Name) else None)
            if called in _INSTANT_NAMES:
                reached.setdefault(name, []).append(called)
    assert reached == {}, f"a period function reaches for an instant: {reached}"


async def test_the_period_is_derived_by_field_through_the_wire(
    moved_zone: str, db_session, client, shema_app
) -> None:
    """The same days, through ``POST``: the period in the answer is the server's, read by field,
    whichever side of UTC the process stands on."""
    from app.db.models.shema_enums import ShemaRegionKey

    user = await make_scoped_user(
        db_session,
        shema_app,
        email="zone@shema.test",
        role_key="coordinator",
        regions=[ShemaRegionKey.AFRICA],
    )
    headers = await auth_header(db_session, user)
    cases = [
        ("bimestral_pi_campo", "2026-01-01", "2026-B1"),
        ("bimestral_pi_campo", "2026-03-01", "2026-B2"),
        ("semestral_member_care", "2026-07-01", "2026-H2"),
        ("trimestral_pi_pontes", "2026-01-01", "2026-Q1"),
    ]
    for meeting_id, day, expected in cases:
        res = await client.post(
            MEETINGS_LOG,
            headers=headers,
            json={"meetingId": meeting_id, "scopeKey": "africa", "date": day, "notes": ""},
        )
        assert res.status_code == 201, res.text
        assert res.json()["period"] == expected
        assert res.json()["date"] == day
