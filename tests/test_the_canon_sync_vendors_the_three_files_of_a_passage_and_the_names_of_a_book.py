"""The canon sync took the map and the Compilation Log of each passage and nothing else, so
what her app draws from the Meaning Coordinates and from the book's aliases list reached ours
missing or rebuilt from the prose (ENG-1201).

Never runs against the real vendor: the compiler is `tests/canon_sync_harness.Compiler`, answered
through `_get`, and `VENDOR`/`PIN_FILE` are redirected into `tmp_path`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import scripts.sync_internalization_canon as canon
from tests.canon_sync_harness import SHA, Compiler, point_the_sync_at, what_is_vendored


@pytest.fixture
def a_compiler_holding_two_whole_passages_of_ruth() -> Compiler:
    compiler = Compiler()
    compiler.book("ruth")
    compiler.passage("P01-Ruth-1-1-5")
    compiler.passage("P05-Ruth-2-1-7")
    return compiler


def test_each_passage_arrives_with_its_map_its_coordinates_and_its_log_and_the_book_with_its_names(
    a_compiler_holding_two_whole_passages_of_ruth: Compiler,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    vendor = point_the_sync_at(
        monkeypatch, canon, a_compiler_holding_two_whole_passages_of_ruth, tmp_path
    )

    exit_code = canon.sync(pin=SHA)

    assert exit_code == 0
    assert what_is_vendored(vendor) == {
        "meaning-map/P01-Ruth-1-1-5.md": b"map P01-Ruth-1-1-5",
        "meaning-map/P05-Ruth-2-1-7.md": b"map P05-Ruth-2-1-7",
        "meaning-coordinates/P01-Ruth-1-1-5-MEANING-COORDINATES.md": b"coordinates P01-Ruth-1-1-5",
        "meaning-coordinates/P05-Ruth-2-1-7-MEANING-COORDINATES.md": b"coordinates P05-Ruth-2-1-7",
        "compilation-log/P01-Ruth-1-1-5-COMPILATION-LOG.md": b"log P01-Ruth-1-1-5",
        "compilation-log/P05-Ruth-2-1-7-COMPILATION-LOG.md": b"log P05-Ruth-2-1-7",
        "registry/ruth.aliases.json": b"aliases ruth",
    }
