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


def test_her_thirty_seven_passages_of_three_books_and_their_names_are_vendored(
    a_compiler_publishing_her_three_books: Compiler,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    vendor = point_the_sync_at(monkeypatch, canon, a_compiler_publishing_her_three_books, tmp_path)

    canon.sync(pin=SHA)

    vendored = sorted(what_is_vendored(vendor))
    assert len(vendored) == 37 * 3 + 3
    assert [name for name in vendored if name.startswith("registry/")] == [
        "registry/esther.aliases.json",
        "registry/jonah.aliases.json",
        "registry/ruth.aliases.json",
    ]
    assert [name for name in vendored if name.startswith("meaning-map/")] == (
        [f"meaning-map/E{number:02d}-Esther-{number}.md" for number in range(1, 19)]
        + [f"meaning-map/J{number:02d}-Jonah-{number}.md" for number in range(1, 6)]
        + [f"meaning-map/P{number:02d}-Ruth-{number}.md" for number in range(1, 15)]
    )
