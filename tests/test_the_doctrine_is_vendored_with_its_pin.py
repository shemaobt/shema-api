"""Marcia's doctrine and her prompts, carried in this repo at a commit we can name.

`docs/DOCTRINE.md` is "binding on every change to this repository", and §5.1 makes
`prompts/*.md`, the model ladder and its parameters her artifacts. Neither file was in this
repo, so the rule that governs the work lived somewhere a developer could not open and the
guard `scripts/check_doctrine.py` prints pointed at a document nobody here had.

Vendored, not forked: the bytes come from one commit of `Tripod-Internalization`, the pin
records which, and `scripts/sync_doctrine.py --check` is what notices an edit. Her prompts
sit beside ours rather than replacing them — ours are derived from hers and have diverged,
and the whole point is that "how does our Guide prompt differ from hers" is a `diff`.

Everything here calls the script's functions directly, never the CLI: `main()`'s only job
beyond them is printing and an exit code.
"""

from __future__ import annotations

from pathlib import Path

from scripts.sync_doctrine import (
    REPO_ROOT,
    VENDORED,
    Pin,
    Ruling,
    digest,
    drift,
    read_pin,
    read_rulings,
    unruled,
    write_pin,
)


def test_every_vendored_artefact_is_in_the_repo_at_the_sha_the_pin_records() -> None:
    """The doctrine and the five prompts are here, and their bytes are the pinned ones.

    A pin file naming a commit proves nothing on its own — the canon vendor drifted once
    already — so this compares the recorded sha256 of every vendored path against the bytes
    on disk, and reports the same list the CI check reports.
    """
    pin = read_pin()

    assert pin.commit, "the pin records no commit — there is nothing to be vendored at"
    assert set(pin.digests) == set(VENDORED.values()), (
        "the pin and the vendoring disagree about which files are vendored: "
        f"{sorted(set(pin.digests) ^ set(VENDORED.values()))}"
    )

    assert not drift(pin), f"a vendored artefact no longer matches the pin: {drift(pin)}"


def test_her_guide_prompt_is_vendored_beside_ours_and_not_over_it() -> None:
    """Ours stays where it is, and hers lands next to it, so the difference is one command.

    Substituting hers for ours would throw away the work of every ticket that ported her
    text — and would be an edit to a file §5.1 reserves to her either way. The two live in
    the same directory at different paths; `diff` is the whole mechanism.
    """
    ours = REPO_ROOT / "app/services/internalization_room/prompts/guide_system_prompt.md"
    hers = REPO_ROOT / "app/services/internalization_room/prompts/vendor/guide_system_prompt.md"

    assert ours.exists(), "our Guide prompt was moved or replaced, which no ruling asked for"
    assert hers.exists(), "her Guide prompt is not vendored, so the divergence cannot be read"
    assert hers.read_text(encoding="utf-8") != ours.read_text(encoding="utf-8"), (
        "hers and ours read identically, which means one of them was overwritten by the other"
    )


def _pinned(tmp_path: Path, commit: str, bodies: dict[str, str]) -> Pin:
    for path, body in bodies.items():
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")
    pin_file = tmp_path / "DOCTRINE_PIN"
    write_pin(commit, {p: digest(b.encode()) for p, b in bodies.items()}, pin_file)
    return read_pin(pin_file)


def _ruling(tmp_path: Path, slug: str, body: str) -> list[Ruling]:
    rulings = tmp_path / "rulings"
    rulings.mkdir(exist_ok=True)
    (rulings / f"{slug}.md").write_text(body, encoding="utf-8")
    return read_rulings(rulings)


def test_a_vendored_path_dropped_from_the_pin_is_still_a_vendored_path(tmp_path: Path) -> None:
    """Deleting the row and the file together is the one way drift could be made to agree.

    `drift` walks what the pin records, so a pin with a row removed has nothing to compare —
    and the artefact it stopped naming is then simply gone, with the check green. The list of
    vendored paths is the script's own, not the pin's, and the check reads it.
    """
    pin = _pinned(tmp_path, "a" * 40, {"docs/doctrine/vendor/DOCTRINE.md": "hers\n"})

    faults = drift(pin, root=tmp_path)

    assert faults, "a pin naming one of six vendored files was accepted as a complete pin"
    assert any("fail_safe_utterances.md" in fault for fault in faults), (
        f"the check does not say which vendored artefacts the pin stopped naming: {faults}"
    )


def test_a_vendored_artefact_edited_in_place_is_reported_rather_than_accepted(
    tmp_path: Path,
) -> None:
    """An edit to hers is a merge conflict, not a decision, and the check is what says so.

    Isolated from the live tree so the assertion is about the comparison and not about which
    bytes happen to be vendored today. The untouched twin is the control: a comparison that
    reported everything would pass the first half of this test while testing nothing.
    """
    bodies = dict.fromkeys(VENDORED.values(), "hers\n")
    pin = _pinned(tmp_path, "b" * 40, bodies)

    assert not drift(pin, root=tmp_path), "the pin did not agree with the bytes it was written from"

    (tmp_path / VENDORED["docs/DOCTRINE.md"]).write_text("ours now\n", encoding="utf-8")
    faults = drift(pin, root=tmp_path)

    assert faults == ["edited: docs/doctrine/vendor/DOCTRINE.md"], (
        f"the one edited artefact was not the one reported: {faults}"
    )


def test_a_pin_moved_with_no_ruling_beside_it_is_refused(tmp_path: Path) -> None:
    """A re-sync rewrites every sha, so only the commit can catch one nobody recorded.

    The bytes and their record move together under `--sync`: drift is green the instant the
    pin is rewritten. What is left to check is whether her word arrived with it.
    """
    pin = _pinned(tmp_path, "c" * 40, {"docs/doctrine/vendor/DOCTRINE.md": "hers\n"})
    recorded = _ruling(
        tmp_path,
        "2026-09-03-the-doctrine-names-an-owner",
        'pin: {}\nword: "any change is a ruling with her word"\nwritten: DOCTRINE.md §5.1\n'.format(
            "c" * 40
        ),
    )

    assert not unruled(pin, recorded), "a pin its own ruling names was called unrecorded"

    moved = _pinned(tmp_path, "d" * 40, {"docs/doctrine/vendor/DOCTRINE.md": "hers\n"})
    faults = unruled(moved, recorded)

    assert faults == [f"no ruling records the pin {'d' * 12}"], (
        f"the moved pin was accepted with the old commit's ruling: {faults}"
    )


def test_a_ruling_that_carries_no_sentence_of_hers_is_not_a_ruling(tmp_path: Path) -> None:
    """Her word and where it is written are the two things a ruling is, and both are required.

    Seventy-seven tickets tuned prompts in good faith against a branch she had abandoned. A
    ruling file that records a decision without quoting her is the same move with a filename
    on it, so the check refuses it rather than counting it.
    """
    pin = _pinned(tmp_path, "e" * 40, {"docs/doctrine/vendor/DOCTRINE.md": "hers\n"})
    unsourced = _ruling(
        tmp_path, "2026-09-09-the-budget-went-up", f"pin: {'e' * 40}\ngoverns: a token budget\n"
    )

    faults = unruled(pin, unsourced)

    assert faults == [
        "2026-09-09-the-budget-went-up: a ruling carries her sentence and where it is written"
    ], f"a ruling quoting nobody was counted as a ruling: {faults}"
