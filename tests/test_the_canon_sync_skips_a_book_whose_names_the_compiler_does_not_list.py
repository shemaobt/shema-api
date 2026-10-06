"""A book reaches the room only when its names list is published at her pin, and the compiler
says which books those are in `_spec/pins.json`. The sync took every book with passages, so a
book whose aliases list the compiler does not list would have arrived with no names for its
beings (ENG-1201).

Never runs against the real vendor: the compiler is `tests/canon_sync_harness.Compiler`, answered
through `_get`, and `VENDOR`/`PIN_FILE` are redirected into `tmp_path`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import scripts.sync_internalization_canon as canon
from tests.canon_sync_harness import SHA, Compiler, point_the_sync_at, what_is_vendored


@pytest.fixture
def a_compiler_whose_pins_list_ruth_and_not_jonah() -> Compiler:
    compiler = Compiler()
    compiler.book("ruth")
    compiler.book("jonah", listed=False)
    compiler.passage("P01-Ruth-1-1-5")
    compiler.passage("J01-Jonah-1-1-3")
    return compiler


def test_a_book_the_compiler_does_not_list_is_skipped_whole_and_reported(
    a_compiler_whose_pins_list_ruth_and_not_jonah: Compiler,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    vendor = point_the_sync_at(
        monkeypatch, canon, a_compiler_whose_pins_list_ruth_and_not_jonah, tmp_path
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
        "skipped book Jonah: its aliases list is not listed by the compiler at the pin"
        in capsys.readouterr().err
    )
