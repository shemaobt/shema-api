from __future__ import annotations

from pathlib import Path

import pytest

import scripts.sync_internalization_canon as canon
from tests.canon_sync_harness import SHA, Compiler, point_the_sync_at


@pytest.fixture
def a_vendor_synced_from_a_compiler_holding_one_whole_passage_of_ruth(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> Path:
    compiler = Compiler()
    compiler.book("ruth")
    compiler.passage("P01-Ruth-1-1-5")
    vendor = point_the_sync_at(monkeypatch, canon, compiler, tmp_path)
    canon.sync(pin=SHA)
    return vendor


def test_a_file_dropped_into_the_registry_fails_the_guard_and_is_named(
    a_vendor_synced_from_a_compiler_holding_one_whole_passage_of_ruth: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    registry = a_vendor_synced_from_a_compiler_holding_one_whole_passage_of_ruth / "registry"
    (registry / "notes.md").write_text("a note someone left")

    exit_code = canon.check()

    assert exit_code == 1
    assert "extra: registry/notes.md" in capsys.readouterr().err


def test_the_provenance_note_is_the_one_other_file_the_registry_may_hold(
    a_vendor_synced_from_a_compiler_holding_one_whole_passage_of_ruth: Path,
) -> None:
    registry = a_vendor_synced_from_a_compiler_holding_one_whole_passage_of_ruth / "registry"
    (registry / "PROVENANCE.md").write_text("where these names lists came from")

    assert canon.check() == 0
