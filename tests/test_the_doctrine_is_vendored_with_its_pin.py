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

from scripts.sync_doctrine import REPO_ROOT, VENDORED, drift, read_pin


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
