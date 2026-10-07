from __future__ import annotations

from pathlib import Path

import pytest

import scripts.sync_internalization_canon as canon
from tests.canon_sync_harness import SHA, Compiler, point_the_sync_at, what_is_vendored


@pytest.fixture
def a_compiler_whose_second_passage_has_no_coordinates() -> Compiler:
    compiler = Compiler()
    compiler.book("ruth")
    compiler.passage("P01-Ruth-1-1-5")
    compiler.passage("P05-Ruth-2-1-7", coordinates=False)
    return compiler


def test_a_passage_without_its_coordinates_is_skipped_by_name_and_the_others_arrive(
    a_compiler_whose_second_passage_has_no_coordinates: Compiler,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    vendor = point_the_sync_at(
        monkeypatch, canon, a_compiler_whose_second_passage_has_no_coordinates, tmp_path
    )

    exit_code = canon.sync(pin=SHA)

    assert exit_code == 0
    assert sorted(what_is_vendored(vendor)) == [
        "compilation-log/P01-Ruth-1-1-5-COMPILATION-LOG.md",
        "meaning-coordinates/P01-Ruth-1-1-5-MEANING-COORDINATES.md",
        "meaning-map/P01-Ruth-1-1-5.md",
        "registry/ruth.aliases.json",
    ]
    assert "skipped P05-Ruth-2-1-7: missing meaning-coordinates" in capsys.readouterr().err
