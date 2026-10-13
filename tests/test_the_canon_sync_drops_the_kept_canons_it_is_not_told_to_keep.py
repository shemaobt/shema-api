"""Every re-pin copied the canon it replaced to `canon/kept/<old pin>/`, and nothing ever removed
one: each kept tree stayed in the repo and in the image for good (ENG-1511). Which pins an open
session still names needs a production read, and while production carries only tests the sync
takes no such read: it keeps the pins it is told to keep and drops every other kept tree.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import scripts.sync_internalization_canon as canon
from tests.canon_sync_harness import SHA, Compiler, point_the_sync_at, what_is_vendored

OLDER = "a" * 40
OLDEST = "b" * 40


@pytest.fixture
def a_canon_pinned_beside_two_kept_trees(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    compiler = Compiler()
    compiler.book("ruth")
    compiler.passage("P01-Ruth-1-1-5")
    point_the_sync_at(monkeypatch, canon, compiler, tmp_path)
    assert canon.sync(pin=SHA) == 0
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
