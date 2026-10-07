from __future__ import annotations

from pathlib import Path

import pytest

import scripts.sync_internalization_canon as canon
from tests.canon_sync_harness import SHA, Compiler, point_the_sync_at, what_is_vendored


@pytest.fixture
def a_vendor_holding_ruth_and_jonah_and_a_compiler_that_stops_listing_jonah(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> tuple[Path, Compiler]:
    compiler = Compiler()
    compiler.book("ruth")
    compiler.book("jonah")
    compiler.passage("P01-Ruth-1-1-5")
    compiler.passage("J01-Jonah-1-1-3")
    vendor = point_the_sync_at(monkeypatch, canon, compiler, tmp_path)
    monkeypatch.setattr(canon, "SERVED_BOOKS", frozenset({"Ruth", "Jonah"}))
    canon.sync(pin=SHA)
    compiler.listed.remove("jonah")
    return vendor, compiler


def test_a_book_that_is_no_longer_published_loses_its_names_list_and_its_passages(
    a_vendor_holding_ruth_and_jonah_and_a_compiler_that_stops_listing_jonah: tuple[Path, Compiler],
) -> None:
    vendor, _ = a_vendor_holding_ruth_and_jonah_and_a_compiler_that_stops_listing_jonah

    exit_code = canon.sync(pin=SHA)

    assert exit_code == 0
    assert sorted(what_is_vendored(vendor)) == [
        "compilation-log/P01-Ruth-1-1-5-COMPILATION-LOG.md",
        "meaning-coordinates/P01-Ruth-1-1-5-MEANING-COORDINATES.md",
        "meaning-map/P01-Ruth-1-1-5.md",
        "registry/ruth.aliases.json",
    ]
