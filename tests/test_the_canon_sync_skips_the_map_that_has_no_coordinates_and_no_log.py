"""At her freeze pin the compiler holds the Psalm 13 map and neither its Coordinates nor its Log.
The listing kept only the names that carried a served book, so that map was dropped without a
word: a passage that never made it in was indistinguishable from one nobody sent (ENG-1201).

Never runs against the real vendor: the compiler is `tests/canon_sync_harness.Compiler`, answered
through `_get`, and `VENDOR`/`PIN_FILE` are redirected into `tmp_path`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import scripts.sync_internalization_canon as canon
from tests.canon_sync_harness import SHA, Compiler, point_the_sync_at, what_is_vendored


@pytest.fixture
def a_compiler_holding_a_bare_psalm_map_beside_a_whole_ruth() -> Compiler:
    compiler = Compiler()
    compiler.book("ruth")
    compiler.book("psalms")
    compiler.passage("P01-Ruth-1-1-5")
    compiler.passage("T13-Psalm-13", coordinates=False, log=False)
    return compiler


def test_the_psalm_13_map_is_skipped_by_name_and_the_run_goes_on(
    a_compiler_holding_a_bare_psalm_map_beside_a_whole_ruth: Compiler,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    vendor = point_the_sync_at(
        monkeypatch, canon, a_compiler_holding_a_bare_psalm_map_beside_a_whole_ruth, tmp_path
    )

    exit_code = canon.sync(pin=SHA)

    assert exit_code == 0
    assert sorted(what_is_vendored(vendor)) == [
        "compilation-log/P01-Ruth-1-1-5-COMPILATION-LOG.md",
        "meaning-coordinates/P01-Ruth-1-1-5-MEANING-COORDINATES.md",
        "meaning-map/P01-Ruth-1-1-5.md",
        "registry/ruth.aliases.json",
    ]
    assert (
        "skipped T13-Psalm-13: missing meaning-coordinates, compilation-log"
        in capsys.readouterr().err
    )
