"""The tally over two folders of runs: rows per script, both totals and her bar."""

from __future__ import annotations

import json
from pathlib import Path

from scripts import golden_tally


def _folder(
    root: Path, name: str, scripts: dict[str, int], *, of: int = 5, commit: str = "c0"
) -> Path:
    folder = root / name
    folder.mkdir()
    (folder / "JUDGED.1.md").write_text(f"backend commit: {commit}\nher pin: p1n\n")
    for script, passes in scripts.items():
        for run in range(of):
            stamp = f"run{run + 1}.2026-10-30T10-00-0{run}"
            if script.startswith("P0") and "-bt" in script:
                failing = [] if run < passes else ["a check"]
                (folder / f"{script}.{stamp}.json").write_text(
                    json.dumps({"name": script, "rounds": [{"checks": failing}]})
                )
            else:
                verdict = "PASS" if run < passes else "FAIL"
                (folder / f"{script}.{stamp}.md").write_text(f"## Judge\n\n**{verdict}**\n")
    return folder


def test_a_row_per_script_with_passes_per_app_the_totals_the_pins_and_the_date(tmp_path) -> None:
    hers = _folder(tmp_path, "2026-10-30-hers", {"S01": 5, "P02-bt": 4}, commit="h3rs")
    ours = _folder(tmp_path, "2026-10-30-ours", {"S01": 5, "P02-bt": 5}, commit="0urs")

    report = golden_tally.tally([hers], [ours])

    assert "| S01 | 5/5 | 5/5 |" in report
    assert "| P02-bt | 4/5 | 5/5 |" in report
    assert "hers 9 · ours 10" in report
    assert "2026-10-30-hers · backend commit: h3rs · her pin: p1n" in report
    assert "2026-10-30-ours · backend commit: 0urs · her pin: p1n" in report


def test_a_script_trailing_by_two_is_listed_for_a_re_run_until_the_re_run_replaces_its_row(
    tmp_path,
) -> None:
    hers = _folder(tmp_path, "hers", {"S01": 5})
    ours = _folder(tmp_path, "ours", {"S01": 3})
    rerun = _folder(tmp_path, "ours-rerun", {"S01": 4})

    before = golden_tally.tally([hers], [ours])
    after = golden_tally.tally([hers], [ours, rerun])

    assert "| S01 | 5/5 | 3/5 | re-run before reading |" in before
    assert "| S01 | 5/5 | 4/5 |  |" in after


def test_a_script_trailing_by_one_is_not_listed(tmp_path) -> None:
    hers = _folder(tmp_path, "hers", {"S01": 5})
    ours = _folder(tmp_path, "ours", {"S01": 4})

    assert "re-run before reading" not in golden_tally.tally([hers], [ours])


def test_ten_passes_fewer_than_hers_is_the_bar_and_eleven_is_not(tmp_path) -> None:
    every = {f"S{i:02}": 5 for i in range(33)}
    hers = _folder(tmp_path, "hers", every)
    ten = _folder(tmp_path, "ten", {**every, "S00": 0, "S01": 0})
    eleven = _folder(tmp_path, "eleven", {**every, "S00": 0, "S01": 0, "S02": 4})

    assert "hers 165 · ours 155 · at most 10 passes fewer: the copy passes" in golden_tally.tally(
        [hers], [ten]
    )
    assert "ours 154 · at most 10 passes fewer: the copy does not pass" in golden_tally.tally(
        [hers], [eleven]
    )
