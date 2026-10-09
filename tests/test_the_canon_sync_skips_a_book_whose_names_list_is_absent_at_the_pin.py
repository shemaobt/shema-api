from __future__ import annotations

from pathlib import Path

import pytest

import scripts.sync_internalization_canon as canon
from tests.canon_sync_harness import SHA, Compiler, point_the_sync_at, what_is_vendored


@pytest.fixture
def a_compiler_that_lists_jonahs_names_and_does_not_hold_them() -> Compiler:
    compiler = Compiler()
    compiler.book("ruth")
    compiler.book("jonah", aliases=False)
    compiler.passage("P01-Ruth-1-1-5")
    compiler.passage("J01-Jonah-1-1-3")
    return compiler


def test_a_book_whose_names_list_is_not_at_the_pin_is_skipped_whole_and_reported(
    a_compiler_that_lists_jonahs_names_and_does_not_hold_them: Compiler,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    vendor = point_the_sync_at(
        monkeypatch, canon, a_compiler_that_lists_jonahs_names_and_does_not_hold_them, tmp_path
    )
    monkeypatch.setattr(canon, "SERVED_BOOKS", frozenset({"Ruth", "Jonah"}))

    exit_code = canon.sync(pin=SHA)

    assert exit_code == 0
    assert sorted(what_is_vendored(vendor)) == [
        "compilation-log/P01-Ruth-1-1-5-COMPILATION-LOG.md",
        "meaning-coordinates/P01-Ruth-1-1-5-MEANING-COORDINATES.md",
        "meaning-map/P01-Ruth-1-1-5.md",
        "registry/ruth.aliases.json",
    ]
    assert (
        "skipped book Jonah: its aliases list is not in the registry at the pin"
        in capsys.readouterr().err
    )
