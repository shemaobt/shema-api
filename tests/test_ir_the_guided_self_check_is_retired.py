from __future__ import annotations

from pathlib import Path

import pytest

from scripts import sync_doctrine
from scripts.sync_doctrine import (
    FREEZE_FILE,
    FROZEN,
    HER_PROMPTS,
    REPO_ROOT,
    RETIRED_PROMPTS,
    Pin,
    Ruling,
    check,
    read_pin,
    read_rulings,
    retired_faults,
)

SELF_CHECK = "draft_check_system_prompt.md"
SELF_CHECK_PATH = f"app/services/internalization_room/prompts/{SELF_CHECK}"
HER_SENTENCE = (
    "Production scope. Yours, with two lines that stay mine: nothing the team or a listener "
    "recorded is deleted without my word, and the listeners' consent (ch. 18). Backup, and "
    "how long things are kept, are yours."
)
RULING = "2026-10-08-the-guided-self-check-is-retired"


def _pin(digests: dict[str, str]) -> Pin:
    return Pin(repo="", branch="", commit="f" * 40, digests=digests)


def _ruled(slug: str = RULING) -> list[Ruling]:
    return [Ruling(slug=slug, pin="", governs="", word="hers", written="2026-10-01")]


def test_a_retired_prompt_that_comes_back_to_the_prompts_directory_is_named_as_returned(
    tmp_path: Path,
) -> None:
    retired = {SELF_CHECK: RULING}

    assert retired_faults(_pin({}), retired, _ruled(), root=tmp_path) == []

    (tmp_path / SELF_CHECK_PATH).parent.mkdir(parents=True)
    (tmp_path / SELF_CHECK_PATH).write_text("hers\n", encoding="utf-8")

    assert retired_faults(_pin({}), retired, _ruled(), root=tmp_path) == [
        f"returned: {SELF_CHECK_PATH} — retired by docs/doctrine/rulings/{RULING}.md"
    ], "whoever put the retired prompt back was not told why it had left"


def test_a_retired_prompt_whose_ruling_is_missing_or_carries_no_word_of_hers_is_named_as_unruled(
    tmp_path: Path,
) -> None:
    retired = {SELF_CHECK: RULING}
    fault = f"unruled: {SELF_CHECK} — {RULING} carries no word of hers and where it is written"
    wordless = [Ruling(slug=RULING, pin="", governs="", word="", written="2026-10-01")]
    unwritten = [Ruling(slug=RULING, pin="", governs="", word="hers", written="")]

    assert retired_faults(_pin({}), retired, [], root=tmp_path) == [fault]
    assert retired_faults(_pin({}), retired, wordless, root=tmp_path) == [fault]
    assert retired_faults(_pin({}), retired, unwritten, root=tmp_path) == [fault], (
        "a prompt of hers was retired on a ruling that quotes nobody"
    )
    assert retired_faults(_pin({}), retired, _ruled(), root=tmp_path) == []


def test_a_pin_that_still_records_a_retired_prompt_is_named_as_pinned(tmp_path: Path) -> None:
    pin = _pin({SELF_CHECK_PATH: "7" * 64})

    assert retired_faults(pin, {SELF_CHECK: RULING}, _ruled(), root=tmp_path) == [
        f"pinned: {SELF_CHECK_PATH}"
    ], "the freeze pin kept vouching for bytes the room no longer carries"


def test_the_check_ci_runs_fails_on_a_retired_prompt_that_is_back_on_disk(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    on_disk = "guide_system_prompt.md"
    monkeypatch.setattr(sync_doctrine, "RETIRED_PROMPTS", {on_disk: RULING})

    assert check() == 1
    assert f"returned: app/services/internalization_room/prompts/{on_disk}" in (
        capsys.readouterr().err
    ), "the doctrine check went green with a retired prompt on disk"


def test_her_prompts_are_eight_in_use_and_the_self_check_is_the_one_retired() -> None:
    assert sorted(HER_PROMPTS) == [
        "backtranslation_analysis_system_prompt.md",
        "backtranslation_verdict_system_prompt.md",
        "book_overview_system_prompt.md",
        "classifier_system_prompt.md",
        "fail_safe_utterances.md",
        "golden_judge_system_prompt.md",
        "guide_system_prompt.md",
        "validator_system_prompt.md",
    ], "her set of prompts is not the eight in use"
    assert RETIRED_PROMPTS == {SELF_CHECK: RULING}, (
        "the retired prompt does not name the ruling that retired it"
    )
    assert SELF_CHECK_PATH not in FROZEN.values(), (
        "a re-sync would copy the retired prompt back from her checkout"
    )


def test_the_ruling_that_retires_the_self_check_quotes_her_delegation_of_1_october() -> None:
    (ruling,) = [ruling for ruling in read_rulings() if ruling.slug == RULING]

    assert ruling.word == f'"{HER_SENTENCE}"', "the ruling does not carry her sentence verbatim"
    assert ruling.written.startswith("2026-10-01"), "the ruling does not say where she wrote it"


def test_the_room_keeps_no_file_of_the_self_check_in_app() -> None:
    kept = sorted(
        path.relative_to(REPO_ROOT).as_posix()
        for path in (REPO_ROOT / "app").rglob("*")
        if "draft_check" in path.name
    )

    assert kept == [], f"her self-check instructions are still kept on the server: {kept}"


def test_the_freeze_pin_no_longer_vouches_for_the_self_check() -> None:
    assert retired_faults(read_pin(FREEZE_FILE), RETIRED_PROMPTS, read_rulings()) == [], (
        "the freeze pin kept a row for the prompt the team retired"
    )


def test_no_source_in_app_names_the_self_check_to_load_it() -> None:
    naming = sorted(
        path.relative_to(REPO_ROOT).as_posix()
        for path in (REPO_ROOT / "app").rglob("*.py")
        if "draft_check" in (text := path.read_text(encoding="utf-8")) or "DRAFT_SELF_CHECK" in text
    )

    assert naming == [], f"a path in app/ still names her self-check: {naming}"


def test_the_check_ci_runs_says_eight_prompts_are_in_use_and_one_is_retired(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert check() == 0

    assert (
        f"her prompts: 8 in use, 1 retired — draft_check_system_prompt.md, ruling {RULING}"
    ) in capsys.readouterr().out, "the check did not say which of her prompts is no longer live"
