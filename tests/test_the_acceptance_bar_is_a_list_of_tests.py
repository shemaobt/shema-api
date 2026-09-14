"""§4 read out of the vendored doctrine, and every line of it claimed by a named test.

"What must not regress" was a paragraph in a document neither repo carried. `ACCEPTANCE_BAR`
is the same paragraph as rows: a fragment of each line of §4, and the tests that hold it. The
lines are parsed from the vendored `DOCTRINE.md` rather than copied into the record, so the one
thing nobody has to remember is to re-read §4 after a re-sync — a line she adds arrives as a
red build with the line printed.

`PENDING` is the honest second column for a line this repo does not hold today, and the check
counts them out loud instead of hiding them. The circle alive at `done` is the one: the ledger
closes the session here, and ENG-835 adds no behaviour to the room.

The fragment is the key, and it is matched against the parsed line rather than compared to it.
A guard on her wording would go red for a rename that leaves the ruling untouched — the same
trap `test_internalization_room_back_translation.py` was cut back from on 10 September.
"""

from __future__ import annotations

from pathlib import Path

from scripts.sync_doctrine import (
    PENDING,
    REPO_ROOT,
    acceptance_bar,
    bar_faults,
    read_bar_record,
)


def test_every_line_of_the_acceptance_bar_is_claimed_by_a_named_test() -> None:
    """The live §4 against the live record, which is what CI runs.

    Seventeen lines, parsed from the doctrine at the pin. A record compared against nothing
    would agree with any paragraph, so the parse is asserted to have found the bar at all
    before the claims are read.
    """
    lines = acceptance_bar()
    record = read_bar_record()

    assert len(lines) == 17, f"§4 no longer parses to the bar this record was written for: {lines}"
    assert not bar_faults(lines, record, REPO_ROOT), (
        f"the acceptance bar and its tests disagree: {bar_faults(lines, record, REPO_ROOT)}"
    )

    pending = [fragment for fragment, tests in record.items() if tests == [PENDING]]
    assert pending == ["the circle is alive at `done`"], (
        f"a line of the bar went unheld without anyone recording it: {pending}"
    )


def test_a_line_she_adds_on_the_next_re_sync_is_not_silently_unprotected() -> None:
    """A re-pin can widen the bar, and the record cannot notice that by itself.

    This is the whole reason the lines are parsed instead of transcribed. The control is the
    same record against the line it does claim: a check that reported everything would pass the
    second half of this while seeing nothing.
    """
    record = {"no blessings": ["tests/x.py::test_a"]}

    assert not bar_faults(["no blessings"], record, REPO_ROOT, tests_exist=False)

    faults = bar_faults(["no blessings", 'never "o mapa"'], record, REPO_ROOT, tests_exist=False)

    assert faults == ['unclaimed: never "o mapa"'], (
        f"a line of §4 no row claims was accepted: {faults}"
    )


def test_a_row_naming_a_test_that_was_renamed_or_deleted_is_refused() -> None:
    """A claim is only worth the test being there, and a rename is how one stops being there.

    Ten of this repo's `test(ir)` commits rename tests. A row pointing at a name nobody kept is
    a line of the bar that reads as held and is not, which is strictly worse than `PENDING`.
    """
    record = {"no blessings": ["tests/test_the_acceptance_bar_is_a_list_of_tests.py::test_gone"]}

    faults = bar_faults(["no blessings"], record, REPO_ROOT)

    assert faults == [
        "no such test: tests/test_the_acceptance_bar_is_a_list_of_tests.py::test_gone"
    ], f"a row claiming a test nobody kept was accepted: {faults}"


def test_a_fragment_her_rewording_left_behind_is_reported_rather_than_ignored() -> None:
    """A row matching no line of §4 is a rule that moved, and a human has to read the move.

    The opposite failure of the one above: not a missing test but a missing line. Matching on a
    fragment keeps a rename from going red, and that same looseness is why a fragment that
    matches nothing at all has to be loud.
    """
    faults = bar_faults(
        ["no blessings"],
        {"no ceilings on speech": ["tests/x.py::test_a"]},
        REPO_ROOT,
        tests_exist=False,
    )

    assert faults == [
        "unclaimed: no blessings",
        "stale: no ceilings on speech",
    ], f"a fragment §4 no longer contains was accepted: {faults}"


def test_the_bar_is_parsed_from_the_vendored_doctrine_and_not_from_a_copy(tmp_path: Path) -> None:
    """The parse takes the five bullets of §4 and splits them on the semicolon she uses.

    Her first bullet is one sentence carrying twelve rules, so a parse that stopped at the
    bullet would call the bar five lines long and the record would agree with it.
    """
    doctrine = tmp_path / "DOCTRINE.md"
    doctrine.write_text(
        "## 3. Forbidden\n\n- nothing\n\n"
        "## 4. What must not regress (the acceptance bar)\n\n"
        "- one; two; three\n- four.\n\n"
        "## 5. How a change ships\n\n- nothing\n",
        encoding="utf-8",
    )

    assert acceptance_bar(doctrine) == ["one", "two", "three", "four."]


def test_a_row_that_claims_a_line_and_holds_nothing_is_refused() -> None:
    """A fragment with no second column matched its line, was not stale, and held nothing.

    `THE_BAR` says a line nobody claims is a line nobody is holding, and an empty claim list was
    the one way to write a row that passes both halves of that sentence without a test behind it
    — invisible in the `PENDING` count too, so the summary still said one.
    """
    faults = bar_faults(["no blessings"], {"no blessings": []}, REPO_ROOT)

    assert faults == ["claims nothing: no blessings"], (
        f"a row with no test and no PENDING was accepted: {faults}"
    )
