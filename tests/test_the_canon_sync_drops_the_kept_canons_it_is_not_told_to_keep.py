"""Every re-pin copied the canon it replaced to `canon/kept/<old pin>/`, and nothing ever removed
one: each kept tree stayed in the repo and in the image for good (ENG-1511). Which pins an open
session still names needs a production read, and while production carries only tests the sync
takes no such read: it keeps the pins it is told to keep and drops every other kept tree.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

import scripts.sync_internalization_canon as canon
from tests.canon_sync_harness import SHA, Compiler, point_the_sync_at, what_is_vendored

OLDER = "a" * 40
OLDEST = "b" * 40
NEXT = "c" * 40


@pytest.fixture
def a_compiler_pinned_beside_its_labels(
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
    return compiler


@pytest.fixture
def a_canon_pinned_beside_two_kept_trees(
    a_compiler_pinned_beside_its_labels: Compiler, tmp_path: Path
) -> Path:
    for pin in (OLDER, OLDEST):
        (tmp_path / "kept" / pin / "vendor").mkdir(parents=True)
        (tmp_path / "kept" / pin / "vendor" / "VENDOR_PIN").write_text(f"pin_commit: {pin}\n")
    return tmp_path


def test_a_sync_drops_every_kept_tree_and_leaves_the_pinned_canon_as_it_is(
    a_canon_pinned_beside_two_kept_trees: Path,
) -> None:
    canon_dir = a_canon_pinned_beside_two_kept_trees

    assert canon.sync(pin=SHA) == 0

    assert sorted(path.name for path in (canon_dir / "kept").iterdir()) == [], (
        "a kept tree no one asked to keep stayed in the repo and in the image"
    )
    assert what_is_vendored(canon_dir / "vendor") == {
        "compilation-log/P01-Ruth-1-1-5-COMPILATION-LOG.md": b"log P01-Ruth-1-1-5",
        "meaning-coordinates/P01-Ruth-1-1-5-MEANING-COORDINATES.md": b"coordinates P01-Ruth-1-1-5",
        "meaning-map/P01-Ruth-1-1-5.md": b"map P01-Ruth-1-1-5",
        "registry/ruth.aliases.json": b"aliases ruth",
    }


def test_a_sync_keeps_the_tree_of_a_pin_it_is_told_to_keep_and_drops_the_other(
    a_canon_pinned_beside_two_kept_trees: Path,
) -> None:
    canon_dir = a_canon_pinned_beside_two_kept_trees

    assert canon.sync(pin=SHA, keep=(OLDER,)) == 0

    assert sorted(path.name for path in (canon_dir / "kept").iterdir()) == [OLDER], (
        "the sync dropped the canon of a pin it was told a session still reads"
    )
    assert (canon_dir / "kept" / OLDER / "vendor" / "VENDOR_PIN").read_text() == (
        f"pin_commit: {OLDER}\n"
    )


def test_a_re_pin_drops_the_tree_it_keeps_for_the_pin_it_replaces_when_not_told_to_keep_it(
    a_compiler_pinned_beside_its_labels: Compiler, tmp_path: Path
) -> None:
    a_compiler_pinned_beside_its_labels.sha = NEXT

    assert canon.sync(pin=NEXT) == 0

    assert sorted(path.name for path in (tmp_path / "kept").iterdir()) == [], (
        "a re-pin left the canon it replaced under kept/ though no one asked to keep it"
    )


def test_a_sync_says_which_kept_trees_it_dropped_and_which_it_kept_before_its_pin(
    a_canon_pinned_beside_two_kept_trees: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    capsys.readouterr()

    assert canon.sync(pin=SHA, keep=(OLDER,)) == 0

    said = capsys.readouterr().out.splitlines()
    assert [line for line in said if "kept/" in line] == [
        "  kept kept/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        "  dropped kept/bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    ], "the sync dropped kept canons without a word"
    assert said[-1] == "pinned at 5b5c8d2b3ae7632279c07017224f861ae369b0d7"


def test_a_sync_with_nothing_new_published_drops_no_kept_tree(
    a_canon_pinned_beside_two_kept_trees: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    canon_dir = a_canon_pinned_beside_two_kept_trees

    assert canon.sync() == 0

    assert capsys.readouterr().out.splitlines()[-1] == "UP_TO_DATE"
    assert sorted(path.name for path in (canon_dir / "kept").iterdir()) == [OLDER, OLDEST], (
        "a sync that changed nothing dropped the canon open sessions read"
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
def test_a_refused_sync_drops_no_kept_tree(
    a_compiler_pinned_beside_its_labels: Compiler,
    a_canon_pinned_beside_two_kept_trees: Path,
    refused: Callable[[Compiler], None],
) -> None:
    a_compiler_pinned_beside_its_labels.sha = NEXT
    refused(a_compiler_pinned_beside_its_labels)

    assert canon.sync(pin=NEXT) == 1

    kept = a_canon_pinned_beside_two_kept_trees / "kept"
    assert sorted(path.name for path in kept.iterdir()) == [OLDER, OLDEST], (
        "a refused sync dropped the canon open sessions read"
    )
