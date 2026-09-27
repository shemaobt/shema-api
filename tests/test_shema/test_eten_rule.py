"""The ETEN credit rule, case by case — ``account_for`` with no database and no clock.

GATE-01 closed on 25/sep/2026 (OBT-387): a credit is one completed defined scope, counted in
**approved** chapters, never a divisor, in ETEN's fiscal year that closes on 31 July. The
console's ``src/utils/__tests__/etenCredits.test.ts`` is the reference and most of these are its
cases moved to the fiscal year; the rest are the facts only the server can see — the stamped
completion date, the export's copied approved count, the ``initial`` entry — each named by the
guarantee it gives.

``TODAY`` sits in fiscal year 2028, so 2026 and 2027 are closed years and read history only.
"""

from __future__ import annotations

from datetime import date

from app.db.models.shema_enums import ShemaEtenCreditSource, ShemaProjectStatus
from app.utils.shema_derivations import (
    CompletionSource,
    CreditSubject,
    ProgressPoint,
    ReadingSource,
    account_for,
    completion_date_after,
    fiscal_year_end,
    fiscal_year_of,
    fiscal_year_start,
)

TODAY = date(2027, 9, 27)
NT = 260


def point(
    day: str,
    approved: int,
    *,
    previous: int | None = None,
    initial: bool = False,
    total: int | None = NT,
) -> ProgressPoint:
    return ProgressPoint(
        id=f"entry-{day}-{approved}",
        entry_date=date.fromisoformat(day),
        approved_units=approved,
        total_units=total,
        previous_approved=previous,
        initial=initial,
    )


def subject(
    *,
    status: ShemaProjectStatus | None = ShemaProjectStatus.EM_ANDAMENTO,
    total: int = NT,
    approved: int = 0,
    unverified: bool = False,
    completed: str | None = None,
) -> CreditSubject:
    return CreditSubject(
        status=status,
        total_units=total,
        approved_units=approved,
        approved_units_unverified=unverified,
        completed_date=None if completed is None else date.fromisoformat(completed),
    )


def account(project: CreditSubject, history: list[ProgressPoint], year: int, manual=None):
    return account_for(project, history, year, manual_credits=manual, today=TODAY)


# --- the fiscal year -------------------------------------------------------------------------


def test_the_fiscal_year_closes_on_31_july_and_1_august_opens_the_next() -> None:
    assert fiscal_year_of(date(2026, 7, 31)) == 2026
    assert fiscal_year_of(date(2026, 8, 1)) == 2027
    assert fiscal_year_of(date(2027, 1, 15)) == 2027
    assert (fiscal_year_start(2026), fiscal_year_end(2026)) == (date(2025, 8, 1), date(2026, 7, 31))


def test_a_reading_on_31_july_counts_for_the_year_that_closes() -> None:
    """The boundary by calendar fields: 31/07 closes the year, 01/08 belongs to the next."""
    closing = [point("2025-07-31", 100), point("2026-07-31", 200), point("2026-08-01", 250)]

    this_year = account(subject(), closing, 2026)
    next_year = account(subject(), closing, 2027)

    assert (this_year.approved_at_start, this_year.approved_at_end) == (100, 200)
    assert (next_year.approved_at_start, next_year.approved_at_end) == (200, 250)


def test_the_reading_is_the_newest_entry_up_to_the_cut() -> None:
    history = [point("2025-09-01", 8), point("2026-05-02", 30), point("2026-09-01", 99)]
    result = account(subject(), history, 2026)

    assert result.approved_at_end == 30
    assert result.end_reading is not None
    assert result.end_reading.entry_id == "entry-2026-05-02-30"
    assert result.end_reading.on == date(2026, 5, 2)
    assert result.end_reading.source is ReadingSource.HISTORY


# --- the unit and the credit -----------------------------------------------------------------


def test_the_unit_is_approved_chapters_not_translated() -> None:
    """Only ``approved_units`` is read; the entry carries no other count for the rule to take."""
    result = account(subject(), [point("2025-07-01", 12), point("2026-07-01", 40)], 2026)
    assert (result.approved_at_start, result.approved_at_end, result.advanced) == (12, 40, 28)


def test_closing_the_scope_inside_the_year_earns_one_credit() -> None:
    result = account(subject(), [point("2025-07-31", 240), point("2026-03-02", 260)], 2026)

    assert result.completed_in_year is True
    assert result.credits == 1
    assert result.credits_source is ShemaEtenCreditSource.CALCULATED


def test_a_25_chapter_scope_and_a_new_testament_earn_one_credit_each() -> None:
    """Not a divisor: 260 approved chapters are one closed scope, not 260 / 25."""
    small = account(
        subject(total=25),
        [point("2025-07-31", 0, total=25), point("2026-04-01", 25, total=25)],
        2026,
    )
    nt = account(subject(), [point("2025-07-31", 0), point("2026-04-01", 260)], 2026)

    assert (small.credits, nt.credits) == (1, 1)
    assert nt.advanced == 260


def test_a_scope_closed_in_an_earlier_year_does_not_earn_again() -> None:
    result = account(subject(), [point("2025-07-31", 260), point("2026-07-31", 260)], 2026)
    assert (result.completed_in_year, result.credits) == (False, 0)


def test_partial_scope_earns_zero() -> None:
    """Zero and not null: the year has data and the answer is *no credit* — no carry-over."""
    result = account(subject(), [point("2025-07-31", 0), point("2026-07-31", 240)], 2026)
    assert (result.advanced, result.credits, result.has_data) == (240, 0, True)


def test_a_project_with_no_declared_scope_closes_nothing() -> None:
    result = account(subject(total=0), [point("2026-07-31", 40, total=0)], 2026)
    assert (result.completed_in_year, result.credits) == (False, 0)


def test_the_credit_belongs_to_the_fiscal_year_the_project_ended() -> None:
    """Almost all the work in 2026 and the last chapters approved on 1 August: it is 2027's."""
    history = [point("2025-07-31", 0), point("2026-07-31", 255), point("2026-08-01", 260)]

    assert account(subject(), history, 2026).credits == 0
    assert account(subject(), history, 2027).credits == 1


def test_a_drop_in_approved_chapters_is_a_negative_advance() -> None:
    result = account(subject(), [point("2025-07-31", 40), point("2026-07-31", 28)], 2026)
    assert result.advanced == -12


# --- the stamped completion date -------------------------------------------------------------


def test_the_completion_date_decides_the_year_when_it_exists() -> None:
    """31/07 and 01/08 land in different years; a January completion is that January's year."""
    history = [point("2025-07-31", 100), point("2026-07-31", 200)]
    concluded = ShemaProjectStatus.CONCLUIDO

    on_the_31st = subject(status=concluded, completed="2026-07-31")
    on_the_1st = subject(status=concluded, completed="2026-08-01")
    in_january = subject(status=concluded, completed="2027-01-10")

    assert account(on_the_31st, history, 2026).credits == 1
    assert account(on_the_1st, history, 2026).credits == 0
    assert account(on_the_1st, history, 2027).credits == 1
    assert account(in_january, history, 2027).credits == 1
    assert account(on_the_31st, history, 2026).completion_source is CompletionSource.COMPLETED_DATE


def test_a_dated_completion_is_credited_once() -> None:
    """The stamp moves the credit to its year; the readings do not credit another one."""
    project = subject(status=ShemaProjectStatus.CONCLUIDO, completed="2027-03-01")
    history = [point("2025-07-31", 0), point("2026-07-31", 150), point("2027-02-01", 200)]

    credits = [account(project, history, year).credits for year in (2026, 2027)]
    assert credits == [0, 1]


def test_a_dated_completion_is_credited_even_without_a_reading() -> None:
    """The stamp is itself the fact: no history, a closed year, and still one credit."""
    project = subject(status=ShemaProjectStatus.CONCLUIDO, completed="2026-10-05")
    result = account(project, [], 2027)

    assert (result.has_data, result.credits) == (False, 1)
    assert result.credits_source is ShemaEtenCreditSource.CALCULATED


def test_a_status_recorded_after_the_scope_closed_does_not_move_the_credit() -> None:
    """Closed in July, marked concluded in August: the July report's credit stays with July.

    Otherwise the report sent in July 2026 and the one sent in July 2027 would both carry it.
    """
    project = subject(status=ShemaProjectStatus.CONCLUIDO, completed="2026-08-03")
    history = [point("2025-07-31", 200), point("2026-07-20", 260)]

    assert account(project, history, 2026).credits == 1
    assert account(project, history, 2027).credits == 0
    assert account(project, history, 2027).completion_source is CompletionSource.SNAPSHOTS


def test_a_concluded_project_nothing_dates_earns_null() -> None:
    """Concluded before the stamp existed, and the readings never reach the scope: no year."""
    result = account(subject(status=ShemaProjectStatus.CONCLUIDO), [point("2026-07-31", 100)], 2026)
    assert (result.undated_completion, result.credits, result.credits_source) == (True, None, None)


def test_a_concluded_project_with_no_scope_earns_null() -> None:
    project = subject(status=ShemaProjectStatus.CONCLUIDO, total=0, completed="2026-03-01")
    result = account(project, [point("2026-03-01", 0, total=0)], 2026)
    assert (result.undated_completion, result.credits) == (True, None)


def test_completion_date_after_stamps_only_the_move_into_concluido() -> None:
    day = date(2026, 7, 31)
    old = date(2020, 1, 1)
    concluded, going = ShemaProjectStatus.CONCLUIDO, ShemaProjectStatus.EM_ANDAMENTO

    assert completion_date_after(going, concluded, None, day) == day
    assert completion_date_after(None, concluded, None, day) == day
    assert completion_date_after(concluded, concluded, None, day) is None
    assert completion_date_after(concluded, concluded, old, day) == old
    assert completion_date_after(concluded, going, old, day) is None


# --- what is not a reading -------------------------------------------------------------------


def test_an_approved_count_copied_from_the_export_is_not_a_reading() -> None:
    """Flagged, and the copy only carried forward by a save that moved something else: null."""
    copied = subject(approved=260, unverified=True)
    carried = [point("2026-05-01", 260, previous=260)]

    result = account(copied, carried, 2026)
    assert (result.start_reading, result.end_reading) == (None, None)
    assert (result.has_data, result.credits) == (False, None)
    assert result.approved_unverified is True


def test_the_open_year_never_reads_a_copied_count_as_it_stands() -> None:
    assert account(subject(approved=260, unverified=True), [], 2028).end_reading is None
    live = account(subject(approved=7), [], 2028).end_reading
    assert live is not None and (live.source, live.approved_units) == (ReadingSource.LIVE, 7)


def test_a_flagged_project_with_typed_approvals_crossing_the_scope_earns_one() -> None:
    """From the first save that moved the approved count, the count is somebody's."""
    project = subject(approved=260, unverified=True)
    history = [
        point("2025-05-01", 100, previous=100),
        point("2025-06-01", 120, previous=100),
        point("2026-06-01", 260, previous=120),
    ]

    result = account(project, history, 2026)
    assert (result.approved_at_start, result.approved_at_end, result.credits) == (120, 260, 1)


def test_a_record_that_arrived_complete_is_undated_not_credited() -> None:
    """Filed with its scope already met: the year it was filed is not the year it closed."""
    arrived = [point("2026-02-01", 260, initial=True)]

    filed = account(subject(), arrived, 2026)
    after = account(subject(), [*arrived, point("2026-09-01", 260, previous=260)], 2027)

    assert (filed.undated_completion, filed.credits) == (True, None)
    assert after.credits == 0


def test_the_open_year_with_no_reading_at_all_is_no_data_not_zero() -> None:
    result = account(subject(), [], 2026)
    assert (result.has_data, result.credits) == (False, None)


# --- the manual valve ------------------------------------------------------------------------


def test_a_manual_entry_beats_the_calculated_value() -> None:
    result = account(subject(), [point("2025-07-31", 240), point("2026-07-31", 260)], 2026, 0)
    assert (result.credits, result.credits_source) == (0, ShemaEtenCreditSource.MANUAL)


def test_a_manual_entry_rescues_an_undated_completion() -> None:
    project = subject(status=ShemaProjectStatus.CONCLUIDO)
    result = account(project, [point("2026-07-31", 100)], 2026, 1)
    assert (result.credits, result.credits_source) == (1, ShemaEtenCreditSource.MANUAL)
