"""Marcia's doctrine and her prompts, carried in this repo at a commit we can name.

`docs/DOCTRINE.md` is "binding on every change to this repository", and §5.1 makes
`prompts/*.md`, the model ladder and its parameters her artifacts. Neither file was in this
repo, so the rule that governs the work lived somewhere a developer could not open and the
guard `scripts/check_doctrine.py` prints pointed at a document nobody here had.

Vendored, not forked: the bytes come from one commit of `Tripod-Internalization`, the pin
records which, and `scripts/sync_doctrine.py --check` is what notices an edit. Her prompts
sit where the room reads them, in `app/services/internalization_room/prompts/`, and are hers
byte for byte, so a prompt that differs from hers is a failed `--check` and not a different
Guide.

Everything here calls the script's functions directly, never the CLI: `main()`'s only job
beyond them is printing and an exit code.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts import sync_doctrine
from scripts.sync_doctrine import (
    FREEZE_FILE,
    FROZEN,
    REPO_ROOT,
    VENDORED,
    Pin,
    Ruling,
    check,
    digest,
    drift,
    read_pin,
    read_rulings,
    unruled,
    write_pin,
)


def test_every_vendored_artefact_is_in_the_repo_at_the_sha_the_pin_records() -> None:
    """Her golden reports of 2026-09-03 are here, and their bytes are the pinned ones.

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
    pin = _pinned(
        tmp_path, "a" * 40, {"golden/reports/2026-09-03/J01-frame-before-elicit.md": "hers\n"}
    )

    faults = drift(pin, root=tmp_path)

    assert faults, "a pin naming one of six vendored files was accepted as a complete pin"
    assert any("golden/reports/2026-09-03/README.md" in fault for fault in faults), (
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

    report = "golden/reports/2026-09-03/README.md"
    (tmp_path / VENDORED[report]).write_text("ours now\n", encoding="utf-8")
    faults = drift(pin, root=tmp_path)

    assert faults == [f"edited: {report}"], (
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


def test_one_character_changed_in_her_frozen_judge_is_named_by_the_check(tmp_path: Path) -> None:
    pin = _pinned(tmp_path, "c" * 40, dict.fromkeys(FROZEN.values(), "hers\n"))
    judge = "app/services/internalization_room/prompts/golden_judge_system_prompt.md"

    (tmp_path / judge).write_text("hers!\n", encoding="utf-8")

    assert drift(pin, root=tmp_path, vendored=FROZEN) == [f"edited: {judge}"]


def test_the_check_ci_runs_names_a_frozen_file_whose_bytes_moved(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    judge = "app/services/internalization_room/prompts/golden_judge_system_prompt.md"
    frozen = {path: digest((REPO_ROOT / path).read_bytes()) for path in FROZEN.values()}
    moved = tmp_path / "FREEZE_PIN"
    write_pin("d" * 40, {**frozen, judge: digest(b"one character apart")}, moved)
    monkeypatch.setattr(sync_doctrine, "FREEZE_FILE", moved)

    assert check() == 1
    assert f"edited: {judge}" in capsys.readouterr().err


APPENDIX_A = {
    "guide_system_prompt.md": "73940519b1967c777d0e0e822d6c944d44001f4a6797245f7dea806d47cf89d1",
    "validator_system_prompt.md": (
        "163853db0072f04fcecda919280522f5224e385f81f0d07329c3a5db7ddf2ae8"
    ),
    "classifier_system_prompt.md": (
        "336e1ec1d4146f9d95dd55b34834bf76b2b4a85db5b50a41bb71aec7fe6ea407"
    ),
    "book_overview_system_prompt.md": (
        "bba4cdbdd4c2ec2c675df4efa85a187693f3c980c57d1e9db6ea064a220f8fd3"
    ),
    "fail_safe_utterances.md": "f2c73db37abb34f03cd9999bdea0caadc9a13a908829774559227772c698fddb",
    "backtranslation_analysis_system_prompt.md": (
        "ae7659d7a8facd9f43d78fa4f4178164bc6a5611e22450fcc703f36d6e372f2b"
    ),
    "backtranslation_verdict_system_prompt.md": (
        "d253996dbbb60316de61d99806f065cdaeca432dd0814a7e5256de75f2fb2332"
    ),
    "golden_judge_system_prompt.md": (
        "394a36339a91ad7c3c1ab2da23d96a7b27a16a67e883b03efee1fa77f8b90dc1"
    ),
}


def test_her_eight_prompts_in_use_are_stored_at_the_fingerprints_appendix_a_lists() -> None:
    pinned = read_pin(FREEZE_FILE).digests

    for name, hers in APPENDIX_A.items():
        path = f"app/services/internalization_room/prompts/{name}"
        assert FROZEN[f"prompts/{name}"] == path, f"{name}: o arquivo dela não está sob o pin"
        assert pinned.get(path) == hers, f"{name}: o pin não registra a digital do apêndice A"
        assert digest((REPO_ROOT / path).read_bytes()) == hers, (
            f"{name}: os bytes guardados não são os do app congelado dela"
        )


HER_DOCTRINE = "a2a29782fcd58b39004e3c1e4be6db78a83868e260bb32bf8b6a11675b3bf79d"
HER_DOCTRINE_AT_THE_FREEZE = "docs/doctrine/vendor/DOCTRINE.md"


def test_her_doctrine_is_stored_at_the_freeze_by_its_fingerprint() -> None:
    pinned = read_pin(FREEZE_FILE).digests

    assert FROZEN.get("docs/DOCTRINE.md") == HER_DOCTRINE_AT_THE_FREEZE, (
        "a doutrina não está sob o mesmo pin dos prompts que a sala envia"
    )
    assert pinned.get(HER_DOCTRINE_AT_THE_FREEZE) == HER_DOCTRINE, (
        "o pin do congelamento não registra a digital da doutrina dela em 18fa7c4"
    )
    assert digest((REPO_ROOT / HER_DOCTRINE_AT_THE_FREEZE).read_bytes()) == HER_DOCTRINE, (
        "os bytes guardados não são os da doutrina do app congelado dela"
    )


def test_the_doctrine_has_one_pin_and_it_is_the_one_her_prompts_are_under() -> None:
    assert HER_DOCTRINE_AT_THE_FREEZE not in read_pin().digests, (
        "a doutrina continuava registrada também no pin de 533b6e3, com dois commits"
    )


def test_the_check_ci_runs_says_the_doctrine_matches_the_commit_of_her_freeze(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert check() == 0
    assert "the vendored doctrine matches pin 18fa7c41f037" in capsys.readouterr().out, (
        "a doutrina está no congelamento, e o check ainda dizia o commit dos relatórios de setembro"
    )


def test_a_report_of_hers_that_drifted_is_named_as_a_report_not_as_the_doctrine(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    report = "golden/reports/2026-09-03/README.md"
    monkeypatch.setitem(VENDORED, report, "golden/reports/2026-09-03/gone.md")

    assert check() == 1
    assert "her reports of 2026-09-03 drifted from pin 533b6e3f338f" in capsys.readouterr().err, (
        "o aviso de drift dos relatórios dizia que a doutrina tinha se movido"
    )
