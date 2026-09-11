"""The roll-up and the history entry, as pure functions — FE-44 §7.2 without a database.

These are the two halves of ``applyProgressUpdate`` that a server must reproduce *exactly*,
and §7 is explicit about what that means: **a server that computes them differently is wrong,
not different.** Every case here is one of §7.2's own sentences.

The write path's own behaviour — the transaction, the version guard, the trail — is
``test_record_write.py``. This file is the arithmetic.
"""

from __future__ import annotations

from datetime import date

from app.services.shema._progress import (
    Aggregates,
    ProgressSource,
    record_progress,
    roll_up,
    with_rolled_aggregates,
)

DAY = date(2026, 9, 11)
NOTHING = Aggregates(0, 0, 0, 0)


def book(book_id: str, chapters: int, translated: int = 0, checked: int = 0, approved: int = 0):
    return {
        "id": book_id,
        "name": book_id,
        "chapters": chapters,
        "translated": translated,
        "communityChecked": checked,
        "mentorApproved": approved,
    }


def test_no_counted_rows_is_not_a_roll_of_zero() -> None:
    """``None`` and a zeroed roll are different answers, and the difference is the rule."""
    assert roll_up([]) is None


def test_the_roll_is_the_sum_of_the_rows() -> None:
    rolled = roll_up([book("mat", 28, 28, 10, 4), book("mrk", 16, 8, 0, 0)])
    assert rolled == Aggregates(translated=36, community=10, approved=4, total=44)


def test_a_story_only_table_leaves_the_aggregates_alone() -> None:
    """§7.2's deliberate divergence from the prototype: a story row has no counts to add.

    The prototype's roll included them and would overwrite the aggregates with zeros the form
    has no column to restore.
    """
    stated = Aggregates(translated=120, community=40, approved=12, total=260)
    assert with_rolled_aggregates(book_progress=[], other_progress=None, stated=stated) == stated


def test_the_tables_win_over_what_the_client_typed() -> None:
    stated = Aggregates(translated=999, community=999, approved=999, total=999)
    rolled = with_rolled_aggregates(
        book_progress=[book("mat", 28, 28, 10, 4)], other_progress=None, stated=stated
    )
    assert rolled == Aggregates(translated=28, community=10, approved=4, total=28)


def test_a_zero_scope_does_not_erase_the_records_own_total() -> None:
    """*The previous ``totalUnits`` survives when the roll is 0* — §7.2, step 1.

    A table of books nobody has scoped yet sums to zero chapters, and letting that overwrite a
    project's 260 is the one case where the tables know less than the record does.
    """
    stated = Aggregates(translated=0, community=0, approved=0, total=260)
    rolled = with_rolled_aggregates(
        book_progress=[book("mat", 0), book("mrk", 0)], other_progress=None, stated=stated
    )
    assert rolled.total == 260


def test_other_progress_rolls_beside_the_books() -> None:
    """``OtherProgressItem`` is the same shape without the id, and is counted for that reason."""
    rolled = with_rolled_aggregates(
        book_progress=[book("mat", 28, 28)],
        other_progress=[{"name": "Histórias de Gênesis", "chapters": 12, "translated": 5}],
        stated=NOTHING,
    )
    assert rolled == Aggregates(translated=33, community=0, approved=0, total=40)


def test_a_cell_that_is_not_a_number_counts_as_zero() -> None:
    """``Number(value) || 0`` — what the console does, so an import cannot fail on the sum."""
    rolled = roll_up([{"chapters": "28", "translated": None, "communityChecked": "", "x": 1}])
    assert rolled == Aggregates(translated=0, community=0, approved=0, total=28)


def test_an_entry_is_written_only_when_an_aggregate_moved() -> None:
    """A typo fixed in the status comments has not moved a count, and writes no entry."""
    standing = Aggregates(translated=36, community=10, approved=4, total=44)
    assert (
        record_progress(
            "x",
            previous=standing,
            current=standing,
            book_progress=[],
            story_progress=[],
            other_progress=None,
            day=DAY,
        )
        is None
    )


def test_the_entry_carries_the_servers_own_read_of_the_previous_values() -> None:
    """The previous side is never the client's — §7.2, and the reason the trail is trustworthy."""
    entry = record_progress(
        "afrikaans-kaaps",
        previous=Aggregates(10, 2, 1, 260),
        current=Aggregates(36, 10, 4, 260),
        book_progress=[book("mat", 28, 28, 10, 4)],
        story_progress=[{"name": "A criação"}],
        other_progress=None,
        day=DAY,
    )
    assert entry is not None
    assert (entry.previous_translated, entry.previous_community, entry.previous_approved) == (
        10,
        2,
        1,
    )
    assert entry.entry_date == DAY
    assert entry.initial is False


def test_the_entry_snapshots_all_three_tables_including_the_one_it_does_not_roll() -> None:
    """What makes ``progressAsOf`` a point-in-time reader rather than a guess."""
    entry = record_progress(
        "x",
        previous=NOTHING,
        current=Aggregates(28, 0, 0, 28),
        book_progress=[book("mat", 28, 28)],
        story_progress=[{"name": "A criação", "audioHours": "2 a 3"}],
        other_progress=None,
        day=DAY,
    )
    assert entry is not None
    assert entry.book_progress == [book("mat", 28, 28)]
    assert entry.story_progress == [{"name": "A criação", "audioHours": "2 a 3"}]
    assert entry.other_progress is None


def test_a_record_born_with_counts_gets_an_initial_entry() -> None:
    entry = record_progress(
        "x",
        previous=None,
        current=Aggregates(28, 0, 0, 28),
        book_progress=[book("mat", 28, 28)],
        story_progress=[],
        other_progress=None,
        day=DAY,
    )
    assert entry is not None and entry.initial is True
    assert entry.previous_translated is None


def test_a_record_born_at_zero_has_nothing_to_say() -> None:
    assert (
        record_progress(
            "x",
            previous=None,
            current=NOTHING,
            book_progress=[],
            story_progress=[],
            other_progress=None,
            day=DAY,
        )
        is None
    )


def test_a_decrease_is_recorded_and_never_swallowed() -> None:
    """*A decrease is never silent* — §7.2. The history renders the negative delta."""
    entry = record_progress(
        "x",
        previous=Aggregates(36, 10, 4, 44),
        current=Aggregates(20, 10, 4, 44),
        book_progress=[book("mat", 28, 20, 10, 4)],
        story_progress=[],
        other_progress=None,
        day=DAY,
    )
    assert entry is not None
    assert entry.translated_units - (entry.previous_translated or 0) == -16


def test_provenance_travels_when_the_update_came_from_a_form() -> None:
    """BE-12's half of the single writer: an imported update is indistinguishable afterwards."""
    entry = record_progress(
        "x",
        previous=NOTHING,
        current=Aggregates(5, 0, 0, 28),
        book_progress=[book("mat", 28, 5)],
        story_progress=[],
        other_progress=None,
        day=DAY,
        source=ProgressSource(from_field="Pati & Marcos", form_type="full"),
    )
    assert entry is not None
    assert entry.from_field == "Pati & Marcos"
    assert entry.form_type == "full"
