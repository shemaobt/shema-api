from __future__ import annotations

from pathlib import Path

import pytest

import scripts.sync_internalization_canon as canon
from tests.canon_sync_harness import SHA, Compiler, point_the_sync_at


@pytest.fixture
def a_vendor_synced_once_from_a_compiler_holding_one_whole_passage_of_ruth(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> Path:
    compiler = Compiler()
    compiler.book("ruth")
    compiler.passage("P01-Ruth-1-1-5")
    vendor = point_the_sync_at(monkeypatch, canon, compiler, tmp_path)
    canon.sync(pin=SHA)
    return vendor


def test_a_re_pin_keeps_the_provenance_note_beside_the_names_lists_and_drops_one_anywhere_else(
    a_vendor_synced_once_from_a_compiler_holding_one_whole_passage_of_ruth: Path,
) -> None:
    vendor = a_vendor_synced_once_from_a_compiler_holding_one_whole_passage_of_ruth
    (vendor / "registry" / "PROVENANCE.md").write_text("where these names lists came from")
    (vendor / "meaning-map" / "PROVENANCE.md").write_text("a note left among the maps")

    canon.sync(pin=SHA)

    assert (vendor / "registry" / "PROVENANCE.md").read_text() == (
        "where these names lists came from"
    )
    assert not (vendor / "meaning-map" / "PROVENANCE.md").exists()
    assert canon.check() == 0
