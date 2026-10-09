from __future__ import annotations

from pathlib import Path

import pytest

import scripts.sync_internalization_canon as canon
from tests.canon_sync_harness import SHA, Compiler, point_the_sync_at, what_is_vendored


@pytest.fixture
def a_compiler_publishing_her_three_books() -> Compiler:
    compiler = Compiler()
    for book in ("esther", "jonah", "ruth"):
        compiler.book(book)
    for number in range(1, 19):
        compiler.passage(f"E{number:02d}-Esther-{number}")
    for number in range(1, 6):
        compiler.passage(f"J{number:02d}-Jonah-{number}")
    for number in range(1, 15):
        compiler.passage(f"P{number:02d}-Ruth-{number}")
    return compiler


def test_only_the_fourteen_passages_of_ruth_and_her_names_are_vendored_and_the_other_books_are_not(
    a_compiler_publishing_her_three_books: Compiler,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    vendor = point_the_sync_at(monkeypatch, canon, a_compiler_publishing_her_three_books, tmp_path)

    canon.sync(pin=SHA)

    vendored = sorted(what_is_vendored(vendor))
    assert len(vendored) == 14 * 3 + 1
    assert [name for name in vendored if "Esther" in name or "Jonah" in name] == []
    assert [name for name in vendored if name.startswith("registry/")] == [
        "registry/ruth.aliases.json"
    ]
    assert [name for name in vendored if name.startswith("meaning-map/")] == [
        f"meaning-map/P{number:02d}-Ruth-{number}.md" for number in range(1, 15)
    ]
