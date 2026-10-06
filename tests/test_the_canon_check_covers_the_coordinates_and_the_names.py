"""`--check` is the one thing in CI that notices the vendored canon moving away from its pin. It
read two kinds of file; once the sync brings the Coordinates and the aliases lists too, a hand
edit to one of those would pass CI green (ENG-1201).

Never runs against the real vendor: the compiler is `tests/canon_sync_harness.Compiler`, answered
through `_get`, and `VENDOR`/`PIN_FILE` are redirected into `tmp_path`.
"""

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


def test_a_vendored_copy_that_matches_its_pin_passes(
    a_vendor_synced_from_a_compiler_holding_one_whole_passage_of_ruth: Path,
) -> None:
    assert canon.check() == 0


def test_a_hand_edited_coordinates_file_and_a_hand_edited_names_list_are_drift(
    a_vendor_synced_from_a_compiler_holding_one_whole_passage_of_ruth: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    vendor = a_vendor_synced_from_a_compiler_holding_one_whole_passage_of_ruth
    (vendor / "meaning-coordinates" / "P01-Ruth-1-1-5-MEANING-COORDINATES.md").write_bytes(
        b"edited"
    )
    (vendor / "registry" / "ruth.aliases.json").unlink()
    (vendor / "registry" / "jonah.aliases.json").write_bytes(b"stale")

    exit_code = canon.check()

    assert exit_code == 1
    err = capsys.readouterr().err
    assert "changed: meaning-coordinates/P01-Ruth-1-1-5-MEANING-COORDINATES.md" in err
    assert "missing: registry/ruth.aliases.json" in err
    assert "extra: registry/jonah.aliases.json" in err
