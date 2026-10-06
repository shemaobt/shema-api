"""Jonah and Esther, when she sends them through the compiler with an SC and a pin, arrive with no
change to a fixed list of books. Today the only edit that serves a book is naming it in
`SERVED_BOOKS`; nothing else in the sync knows a book by name (ENG-1201).

Never runs against the real vendor: the compiler is `tests/canon_sync_harness.Compiler`, answered
through `_get`, and `VENDOR`/`PIN_FILE` are redirected into `tmp_path`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import scripts.sync_internalization_canon as canon
from tests.canon_sync_harness import SHA, Compiler, point_the_sync_at, what_is_vendored


@pytest.fixture
def a_compiler_publishing_ruth_and_jonah_in_full() -> Compiler:
    compiler = Compiler()
    compiler.book("ruth")
    compiler.book("jonah")
    compiler.passage("P01-Ruth-1-1-5")
    compiler.passage("J01-Jonah-1-1-3")
    compiler.passage("J02-Jonah-1-4-2-1")
    return compiler


def test_a_book_named_in_the_served_set_arrives_with_its_passages_and_its_names(
    a_compiler_publishing_ruth_and_jonah_in_full: Compiler,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    vendor = point_the_sync_at(
        monkeypatch, canon, a_compiler_publishing_ruth_and_jonah_in_full, tmp_path
    )
    monkeypatch.setattr(canon, "SERVED_BOOKS", frozenset({"Ruth", "Jonah"}))

    canon.sync(pin=SHA)

    assert sorted(what_is_vendored(vendor)) == [
        "compilation-log/J01-Jonah-1-1-3-COMPILATION-LOG.md",
        "compilation-log/J02-Jonah-1-4-2-1-COMPILATION-LOG.md",
        "compilation-log/P01-Ruth-1-1-5-COMPILATION-LOG.md",
        "meaning-coordinates/J01-Jonah-1-1-3-MEANING-COORDINATES.md",
        "meaning-coordinates/J02-Jonah-1-4-2-1-MEANING-COORDINATES.md",
        "meaning-coordinates/P01-Ruth-1-1-5-MEANING-COORDINATES.md",
        "meaning-map/J01-Jonah-1-1-3.md",
        "meaning-map/J02-Jonah-1-4-2-1.md",
        "meaning-map/P01-Ruth-1-1-5.md",
        "registry/jonah.aliases.json",
        "registry/ruth.aliases.json",
    ]
