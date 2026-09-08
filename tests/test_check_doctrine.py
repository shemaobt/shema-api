"""The Python half of Marcia's ban on six mechanisms returning to the voice path's code.

`scripts/check_doctrine.py` translates `check-doctrine.mjs` — the guard already blocking
`Tripod-Internalization`'s build — into the Python spellings `app/services/internalization_room`
and `app/api/internalization_room` actually use. Two claims have to hold for the translation to
be worth anything: it has to be looking where the six mechanisms actually live, not passing on
an empty scan, and it has to catch one coming back.

Everything here calls `scan()`/`evaluate()` directly, never the CLI — `main()`'s only job beyond
these two is printing and an exit code, neither of which this file needs to observe.
"""

from __future__ import annotations

from pathlib import Path

from scripts.check_doctrine import SCAN_ROOTS, evaluate, scan
from scripts.doctrine_allowlist import ALLOWLIST, AllowlistEntry, Rule


def test_the_guard_finds_every_site_the_allowlist_already_names() -> None:
    """Looking where the six mechanisms live, not passing on an empty scan.

    A scanner that walked the wrong directories, or whose patterns stopped matching the
    repo's actual spellings, would report no hits at all — and an empty allowlist would
    then agree with it for the wrong reason. Comparing against the real allowlist instead
    of asserting `scan()` is merely non-empty is what would have caught that.
    """
    hits = scan(SCAN_ROOTS)

    assert hits, "the scan found nothing at all — it is not looking where the six mechanisms live"

    _violations, stale = evaluate(hits, ALLOWLIST)
    assert not stale, (
        "the allowlist names sites the scan no longer confirms: "
        f"{[(e.file, e.rule, e.text) for e in stale]}"
    )


def test_a_mechanism_reintroduced_outside_the_allowlist_fails_with_its_doctrine_sentence(
    tmp_path: Path,
) -> None:
    """A file re-adding a ceiling, isolated from the real allowlist, is reported as a violation.

    `evaluate` is what `main()` uses to decide the exit code — this is the same call, on a
    fixture instead of the live tree, so the assertion is about the guard's own logic and
    not about which files happen to be in `app/` today.
    """
    room = tmp_path / "room"
    room.mkdir()
    (room / "reintroduced.py").write_text(
        'def fits(text: str) -> bool:\n    return True\n\nSpeechBudget = "the ceiling came back"\n'
    )

    hits = scan((room,), base=tmp_path)
    violations, _stale = evaluate(hits, ALLOWLIST)

    assert len(violations) == 1, f"expected exactly one violation, got {violations}"
    violation = violations[0]
    assert (violation.file, violation.line, violation.rule) == (
        "room/reintroduced.py",
        4,
        Rule.CEILING,
    )
    assert (
        violation.message == "no speech ceilings in code — length is prompt style, never a reject"
    )


def test_an_allowlist_entry_the_scan_can_no_longer_confirm_is_reported_stale(
    tmp_path: Path,
) -> None:
    """A row whose text no longer matches any hit is stale — even when the file and rule still do.

    Keying on the offending text, not just `(file, rule)`, is what makes a rewritten line
    visible: a row surviving unchanged for a site whose wording moved would otherwise absorb
    a fresh violation silently instead of reporting either half honestly. This is also the
    other half of the ladder's promise — a removal ticket that deletes the code but forgets
    the matching allowlist row must not go green by accident.
    """
    room = tmp_path / "room"
    room.mkdir()
    (room / "reworded.py").write_text(
        'def fits(text: str) -> bool:\n    return True\n\nSpeechBudget = "reworded since"\n'
    )

    hits = scan((room,), base=tmp_path)
    stale_entry = AllowlistEntry(
        "room/reworded.py", Rule.CEILING, 'SpeechBudget = "the old wording"'
    )
    violations, stale = evaluate(hits, [stale_entry])

    assert stale == [stale_entry]
    assert len(violations) == 1
    assert violations[0].text == 'SpeechBudget = "reworded since"'
