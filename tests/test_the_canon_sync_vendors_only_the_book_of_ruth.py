from __future__ import annotations

import json

import pytest

import scripts.sync_internalization_canon as canon

SHA = "5b5c8d2b3ae7632279c07017224f861ae369b0d7"

UPSTREAM_MAPS = (
    [f"E{n:02d}-Esther-{n}.md" for n in range(1, 19)]
    + [f"J{n:02d}-Jonah-{n}.md" for n in range(1, 6)]
    + [f"P{n:02d}-Ruth-{n}.md" for n in range(1, 15)]
    + ["T13-Psalm-13.md"]
)


@pytest.fixture
def an_upstream_listing_with_her_three_books_and_a_psalm(monkeypatch: pytest.MonkeyPatch) -> None:
    listing = json.dumps([{"name": name} for name in UPSTREAM_MAPS]).encode()
    monkeypatch.setattr(canon, "_get", lambda url: listing)


def test_only_the_fourteen_passages_of_ruth_are_listed_and_the_other_books_are_not(
    an_upstream_listing_with_her_three_books_and_a_psalm: None,
) -> None:
    names = canon._listing("meaning-map", SHA)

    assert names == [f"P{n:02d}-Ruth-{n}.md" for n in range(1, 15)]
