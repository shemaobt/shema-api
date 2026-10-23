"""ENG-1753 — a canon sync never removes a kept canon.

The sync dropped every kept tree it was not told to keep, and the scheduled run tells it
nothing: the first re-pin after a deploy left every live session under the old pin with no
canon to read. A kept tree now leaves only through a prune told the pins live sessions hold.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

import scripts.sync_internalization_canon as canon
from tests.canon_sync_harness import SHA, Compiler, point_the_sync_at

LIVE = "a" * 40
STALE = "c" * 40
NEXT = "e" * 40


@pytest.fixture
def a_compiler_pinned_beside_two_kept_trees(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> Compiler:
    compiler = Compiler()
    compiler.book("ruth")
    compiler.passage("P01-Ruth-1-1-5")
    point_the_sync_at(monkeypatch, canon, compiler, tmp_path)
    (tmp_path / "element-labels").mkdir()
    (tmp_path / "element-labels" / "ruth.json").write_text("{}")
    (tmp_path / "ui-labels.pt.json").write_text("{}")
    assert canon.sync(pin=SHA) == 0
    for pin in (LIVE, STALE):
        (tmp_path / "kept" / pin / "vendor").mkdir(parents=True)
        (tmp_path / "kept" / pin / "vendor" / "VENDOR_PIN").write_text(f"pin_commit: {pin}\n")
    return compiler


def _kept_trees(canon_dir: Path) -> list[str]:
    return sorted(path.name for path in (canon_dir / "kept").iterdir())


def _files_under(tree: Path) -> dict[Path, bytes]:
    return {path: path.read_bytes() for path in tree.rglob("*") if path.is_file()}


def test_a_re_pin_keeps_the_pin_it_replaces_and_removes_no_other_kept_tree(
    a_compiler_pinned_beside_two_kept_trees: Compiler, tmp_path: Path
) -> None:
    before = {pin: _files_under(tmp_path / "kept" / pin) for pin in (LIVE, STALE)}
    a_compiler_pinned_beside_two_kept_trees.sha = NEXT

    assert canon.sync(pin=NEXT) == 0

    assert _kept_trees(tmp_path) == sorted([SHA, LIVE, STALE]), (
        "o re-pin apagou o canon que uma sessão viva ainda lê"
    )
    assert {pin: _files_under(tmp_path / "kept" / pin) for pin in (LIVE, STALE)} == before


def test_a_sync_on_the_pin_already_held_removes_no_kept_tree(
    a_compiler_pinned_beside_two_kept_trees: Compiler, tmp_path: Path
) -> None:
    assert canon.sync(pin=SHA) == 0

    assert _kept_trees(tmp_path) == [LIVE, STALE], (
        "um sync sem re-pin apagou o canon que as sessões vivas leem"
    )


def test_a_sync_with_nothing_new_published_removes_no_kept_tree(
    a_compiler_pinned_beside_two_kept_trees: Compiler,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert canon.sync() == 0

    assert capsys.readouterr().out.splitlines()[-1] == "UP_TO_DATE"
    assert _kept_trees(tmp_path) == [LIVE, STALE], (
        "um sync que não mudou nada apagou o canon que as sessões vivas leem"
    )


def _off_the_main_line(compiler: Compiler) -> None:
    compiler.relation = None


def _with_nothing_consumable(compiler: Compiler) -> None:
    compiler.files.clear()


def _with_a_names_list_pins_json_does_not_record(compiler: Compiler) -> None:
    compiler.fingerprints["ruth"] = "0" * 64


@pytest.mark.parametrize(
    "refused",
    [_off_the_main_line, _with_nothing_consumable, _with_a_names_list_pins_json_does_not_record],
)
def test_a_refused_sync_removes_no_kept_tree(
    a_compiler_pinned_beside_two_kept_trees: Compiler,
    tmp_path: Path,
    refused: Callable[[Compiler], None],
) -> None:
    a_compiler_pinned_beside_two_kept_trees.sha = NEXT
    refused(a_compiler_pinned_beside_two_kept_trees)

    assert canon.sync(pin=NEXT) == 1

    assert _kept_trees(tmp_path) == [LIVE, STALE], (
        "um sync recusado apagou o canon que as sessões vivas leem"
    )
